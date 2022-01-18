import os
import glob
import logging
import json
import datetime
import requests
from pygazpar.enum import Frequency
from pygazpar.datafileparser import DataFileParser

LOGIN_URL = "https://login.monespace.grdf.fr/sofit-account-api/api/v1/auth"
LOGIN_PAYLOAD = """{{
    "email": "{0}",
    "password": "{1}",
    "capp": "meg",
    "goto": "https://sofa-connexion.grdf.fr:443/openam/oauth2/externeGrdf/authorize?response_type=code&scope=openid%20profile%20email%20infotravaux%20%2Fv1%2Faccreditation%20%2Fv1%2Faccreditations%20%2Fdigiconso%2Fv1%20%2Fdigiconso%2Fv1%2Fconsommations%20new_meg&client_id=prod_espaceclient&state=0&redirect_uri=https%3A%2F%2Fmonespace.grdf.fr%2F_codexch&nonce=skywsNPCVa-AeKo1Rps0HjMVRNbUqA46j7XYA4tImeI&by_pass_okta=1&capp=meg"}}"""
DATA_URL = "https://monespace.grdf.fr/api/e-conso/pce/consommation/informatives/telecharger?dateDebut={1}&dateFin={2}&frequence={0}&pceList%5B%5D={3}"
DATA_FILENAME = 'Donnees_informatives_*.xlsx'

DEFAULT_TMP_DIRECTORY = '/tmp'
DEFAULT_METER_READING_FREQUENCY = Frequency.DAILY
DEFAULT_LAST_N_DAYS = 365


Logger = logging.getLogger(__name__)


# ------------------------------------------------------------------------------------------------------------
class LoginError(Exception):
    """ Client has failed to login in GrDF Web site (check username/password)"""
    pass


# ------------------------------------------------------------------------------------------------------------
class Client:

    # ------------------------------------------------------
    def __init__(self, username: str, password: str, pceIdentifier: str, meterReadingFrequency: Frequency = DEFAULT_METER_READING_FREQUENCY, lastNDays: int = DEFAULT_LAST_N_DAYS, tmpDirectory: str = DEFAULT_TMP_DIRECTORY, testMode: bool = False):
        self.__username = username
        self.__password = password
        self.__pceIdentifier = pceIdentifier
        self.__tmpDirectory = tmpDirectory
        self.__data = []
        self.__meterReadingFrequency = meterReadingFrequency
        self.__lastNDays = lastNDays
        self.__testMode = testMode

    # ------------------------------------------------------
    def data(self) -> dict:
        return self.__data

    # ------------------------------------------------------
    def update(self):

        if self.__testMode:
            self.__updateTestMode()
        else:
            self.__updateLiveMode()

    # ------------------------------------------------------
    def __updateTestMode(self):

        dataSampleFilenameByFrequency = {
            Frequency.HOURLY: "hourly_data_sample.json",
            Frequency.DAILY: "daily_data_sample.json",
            Frequency.WEEKLY: "weekly_data_sample.json",
            Frequency.MONTHLY: "monthly_data_sample.json"
        }

        try:
            dataSampleFilename = f"{os.path.dirname(os.path.abspath(__file__))}/resources/{dataSampleFilenameByFrequency[self.__meterReadingFrequency]}"

            with open(dataSampleFilename) as jsonFile:
                data = json.load(jsonFile)
                self.__data = data
        except Exception:
            Logger.error("An unexpected error occured while loading sample data", exc_info=True)
            raise

    # ------------------------------------------------------
    def __updateLiveMode(self):

        Logger.debug("Start updating the data...")

        # XLSX is in the TMP directory
        data_file_path_pattern = self.__tmpDirectory + '/' + DATA_FILENAME

        # We remove an eventual existing data file (from a previous run that has not deleted it).
        file_list = glob.glob(data_file_path_pattern)
        for filename in file_list:
            if os.path.isfile(filename):
                os.remove(filename)

        try:

            session = requests.Session()

            self.__login(session)

            # Build URL to get the data from.
            frequencies = {
                Frequency.HOURLY: "Horaire",
                Frequency.DAILY: "Journalier",
                Frequency.WEEKLY: "Hebdomadaire",
                Frequency.MONTHLY: "Mensuel"
            }
            dateFormat = "%Y-%m-%d"
            endDate = datetime.date.today()
            startDate = endDate + datetime.timedelta(days=-self.__lastNDays)

            downloadUrl = DATA_URL.format(frequencies[self.__meterReadingFrequency], startDate.strftime(dateFormat), endDate.strftime(dateFormat), self.__pceIdentifier)

            session.get(downloadUrl)  # First request does not return anything : strange...

            Logger.debug(f"Loading data of frequency {frequencies[self.__meterReadingFrequency]} from {startDate.strftime(dateFormat)} to {endDate.strftime(dateFormat)}")
            self.__downloadFile(session, downloadUrl, self.__tmpDirectory)

            # Load the XLSX file into the data structure
            file_list = glob.glob(data_file_path_pattern)

            if len(file_list) == 0:
                Logger.warning(f"Not any data file has been found in '{self.__tmpDirectory}' directory")

            for filename in file_list:

                self.__data = DataFileParser.parse(filename, self.__meterReadingFrequency)

                os.remove(filename)

            Logger.debug("The data update terminates normally")
        except Exception:
            Logger.error("An unexpected error occured while updating the data", exc_info=True)
            raise

    # ------------------------------------------------------
    def __login(self, session: requests.Session):

        payload = LOGIN_PAYLOAD.format(self.__username, self.__password)

        data = json.loads(payload)

        response = session.post('https://login.monespace.grdf.fr/sofit-account-api/api/v1/auth', data=data)

        response.raise_for_status()

        loginData = response.json()

        if loginData["state"] != "SUCCESS":
            raise LoginError()

    # ------------------------------------------------------
    def __downloadFile(self, session: requests.Session, url: str, path: str):

        response = session.get(url)

        response.raise_for_status()

        filename = response.headers["Content-Disposition"].split("filename=")[1]

        open(f"{path}/{filename}", "wb").write(response.content)
