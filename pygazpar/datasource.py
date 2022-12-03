import logging
import glob
import os
import json
from abc import ABC, abstractmethod
from typing import Any, List, Dict, cast
from requests import Session
from datetime import date
from pygazpar.enum import Frequency
from pygazpar.excelparser import ExcelParser
from pygazpar.jsonparser import JsonParser

AUTH_NONCE_URL = "https://monespace.grdf.fr/client/particulier/accueil"
LOGIN_URL = "https://login.monespace.grdf.fr/sofit-account-api/api/v1/auth"
LOGIN_HEADER = {"domain": "grdf.fr"}
LOGIN_PAYLOAD = """{{
    "email": "{0}",
    "password": "{1}",
    "capp": "meg",
    "goto": "https://sofa-connexion.grdf.fr:443/openam/oauth2/externeGrdf/authorize?response_type=code&scope=openid%20profile%20email%20infotravaux%20%2Fv1%2Faccreditation%20%2Fv1%2Faccreditations%20%2Fdigiconso%2Fv1%20%2Fdigiconso%2Fv1%2Fconsommations%20new_meg&client_id=prod_espaceclient&state=0&redirect_uri=https%3A%2F%2Fmonespace.grdf.fr%2F_codexch&nonce={2}&by_pass_okta=1&capp=meg"}}"""


Logger = logging.getLogger(__name__)


# ------------------------------------------------------------------------------------------------------------
class IDataSource(ABC):

    @abstractmethod
    def load(self, pceIdentifier: str, startDate: date, endDate: date, frequency: Frequency) -> List[Dict[str, Any]]:
        pass


# ------------------------------------------------------------------------------------------------------------
class WebDataSource(IDataSource):

    # ------------------------------------------------------
    def __init__(self, username: str, password: str):

        self.__username = username
        self.__password = password

    # ------------------------------------------------------
    def load(self, pceIdentifier: str, startDate: date, endDate: date, frequency: Frequency) -> List[Dict[str, Any]]:

        session = Session()

        session.headers.update(LOGIN_HEADER)

        self._login(session, self.__username, self.__password)

        res = self._loadFromSession(session, pceIdentifier, startDate, endDate, frequency)

        Logger.debug("The data update terminates normally")

        return res

    # ------------------------------------------------------
    def _login(self, session: Session, username: str, password: str):

        # Get auth_nonce token.
        session.get(AUTH_NONCE_URL)
        if "auth_nonce" not in session.cookies:
            raise Exception("Login error: Cannot get auth_nonce token")
        auth_nonce = session.cookies.get("auth_nonce")

        # Build the login payload as a json string.
        payload = LOGIN_PAYLOAD.format(username, password, auth_nonce)

        # Build the login payload as a python object.
        data = json.loads(payload)

        # Send the login command.
        response = session.post(LOGIN_URL, data=data)

        # Check login result.
        loginData = response.json()

        response.raise_for_status()

        if "status" in loginData and "error" in loginData and loginData["status"] >= 400:
            raise Exception(f"{loginData['error']} ({loginData['status']})")

        if "state" in loginData and loginData["state"] != "SUCCESS":
            raise Exception(loginData["error"])

    @abstractmethod
    def _loadFromSession(self, session: Session, pceIdentifier: str, startDate: date, endDate: date, frequency: Frequency) -> List[Dict[str, Any]]:
        pass


# ------------------------------------------------------------------------------------------------------------
class ExcelWebDataSource(WebDataSource):

    DATA_URL = "https://monespace.grdf.fr/api/e-conso/pce/consommation/informatives/telecharger?dateDebut={0}&dateFin={1}&frequence={3}&pceList%5B%5D={2}"

    DATE_FORMAT = "%Y-%m-%d"

    FREQUENCY_VALUES = {
        Frequency.HOURLY: "Horaire",
        Frequency.DAILY: "Journalier",
        Frequency.WEEKLY: "Hebdomadaire",
        Frequency.MONTHLY: "Mensuel"
    }

    DATA_FILENAME = 'Donnees_informatives_*.xlsx'

    # ------------------------------------------------------
    def __init__(self, username: str, password: str, tmpDirectory: str):

        super().__init__(username, password)

        self.__tmpDirectory = tmpDirectory

    # ------------------------------------------------------
    def _loadFromSession(self, session: Session, pceIdentifier: str, startDate: date, endDate: date, frequency: Frequency) -> List[Dict[str, Any]]:

        res = []

        # XLSX is in the TMP directory
        data_file_path_pattern = self.__tmpDirectory + '/' + ExcelWebDataSource.DATA_FILENAME

        # We remove an eventual existing data file (from a previous run that has not deleted it).
        file_list = glob.glob(data_file_path_pattern)
        for filename in file_list:
            if os.path.isfile(filename):
                os.remove(filename)

        # Inject parameters.
        downloadUrl = ExcelWebDataSource.DATA_URL.format(startDate.strftime(ExcelWebDataSource.DATE_FORMAT), endDate.strftime(ExcelWebDataSource.DATE_FORMAT), pceIdentifier, ExcelWebDataSource.FREQUENCY_VALUES[frequency])

        session.get(downloadUrl)  # First request does not return anything : strange...

        Logger.debug(f"Loading data of frequency {ExcelWebDataSource.FREQUENCY_VALUES[frequency]} from {startDate.strftime(ExcelWebDataSource.DATE_FORMAT)} to {endDate.strftime(ExcelWebDataSource.DATE_FORMAT)}")

        self.__downloadFile(session, downloadUrl, self.__tmpDirectory)

        # Load the XLSX file into the data structure
        file_list = glob.glob(data_file_path_pattern)

        if len(file_list) == 0:
            Logger.warning(f"Not any data file has been found in '{self.__tmpDirectory}' directory")

        for filename in file_list:

            res = ExcelParser.parse(filename, frequency)

            os.remove(filename)

        return res

    # ------------------------------------------------------
    def __downloadFile(self, session: Session, url: str, path: str):

        response = session.get(url)

        response.raise_for_status()

        filename = response.headers["Content-Disposition"].split("filename=")[1]

        open(f"{path}/{filename}", "wb").write(response.content)


# ------------------------------------------------------------------------------------------------------------
class ExcelFileDataSource(IDataSource):

    def __init__(self, excelFile: str):

        self.__excelFile = excelFile

    def load(self, pceIdentifier: str, startDate: date, endDate: date, frequency: Frequency) -> List[Dict[str, Any]]:

        res = ExcelParser.parse(self.__excelFile, frequency)

        return res


# ------------------------------------------------------------------------------------------------------------
class JsonWebDataSource(WebDataSource):

    DATA_URL = "https://monespace.grdf.fr/api/e-conso/pce/consommation/informatives?dateDebut={0}&dateFin={1}&pceList%5B%5D={2}"

    DATE_FORMAT = "%Y-%m-%d"

    def __init__(self, username: str, password: str):

        super().__init__(username, password)

    def _loadFromSession(self, session: Session, pceIdentifier: str, startDate: date, endDate: date, frequency: Frequency) -> List[Dict[str, Any]]:

        # For the moment, only daily is supported.
        if frequency != Frequency.DAILY:
            raise Exception("Only daily data are supported with JsonWebDataSource")

        # Inject parameters.
        downloadUrl = JsonWebDataSource.DATA_URL.format(startDate.strftime(JsonWebDataSource.DATE_FORMAT), endDate.strftime(JsonWebDataSource.DATE_FORMAT), pceIdentifier)

        # First request never returns data.
        session.get(downloadUrl)

        # Get data
        data = session.get(downloadUrl).text

        res = JsonParser.parse(data, pceIdentifier)

        return res


# ------------------------------------------------------------------------------------------------------------
class JsonFileDataSource(IDataSource):

    def __init__(self, jsonFile: str):

        self.__jsonFile = jsonFile

    def load(self, pceIdentifier: str, startDate: date, endDate: date, frequency: Frequency) -> List[Dict[str, Any]]:

        res = []

        with open(self.__jsonFile) as jsonFile:
            res = JsonParser.parse(jsonFile.read(), pceIdentifier)

        return res


# ------------------------------------------------------------------------------------------------------------
class TestDataSource(IDataSource):

    def __init__(self):

        pass

    def load(self, pceIdentifier: str, startDate: date, endDate: date, frequency: Frequency) -> List[Dict[str, Any]]:

        res = []

        dataSampleFilenameByFrequency = {
            Frequency.HOURLY: "hourly_data_sample.json",
            Frequency.DAILY: "daily_data_sample.json",
            Frequency.WEEKLY: "weekly_data_sample.json",
            Frequency.MONTHLY: "monthly_data_sample.json",
            Frequency.YEARLY: "yearly_data_sample.json"
        }

        dataSampleFilename = f"{os.path.dirname(os.path.abspath(__file__))}/resources/{dataSampleFilenameByFrequency[frequency]}"

        with open(dataSampleFilename) as jsonFile:
            res = cast(List[Dict[str, Any]], json.load(jsonFile))

        return res
