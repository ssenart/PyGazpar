import logging
import glob
import os
import json
import pandas as pd
from abc import ABC, abstractmethod
from typing import Any, List, Dict, cast, Optional
from requests import Session
from datetime import date, timedelta
from pygazpar.enum import Frequency, PropertyName
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

MeterReading = Dict[str, Any]

MeterReadings = List[MeterReading]

MeterReadingsByFrequency = Dict[str, MeterReadings]


# ------------------------------------------------------------------------------------------------------------
class IDataSource(ABC):

    @abstractmethod
    def load(self, pceIdentifier: str, startDate: date, endDate: date, frequencies: Optional[List[Frequency]] = None) -> MeterReadingsByFrequency:
        pass


# ------------------------------------------------------------------------------------------------------------
class WebDataSource(IDataSource):

    # ------------------------------------------------------
    def __init__(self, username: str, password: str):

        self.__username = username
        self.__password = password

    # ------------------------------------------------------
    def load(self, pceIdentifier: str, startDate: date, endDate: date, frequencies: Optional[List[Frequency]] = None) -> MeterReadingsByFrequency:

        session = Session()

        session.headers.update(LOGIN_HEADER)

        self._login(session, self.__username, self.__password)

        res = self._loadFromSession(session, pceIdentifier, startDate, endDate, frequencies)

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
    def _loadFromSession(self, session: Session, pceIdentifier: str, startDate: date, endDate: date, frequencies: Optional[List[Frequency]] = None) -> MeterReadingsByFrequency:
        pass


# ------------------------------------------------------------------------------------------------------------
class ExcelWebDataSource(WebDataSource):

    DATA_URL = "https://monespace.grdf.fr/api/e-conso/pce/consommation/informatives/telecharger?dateDebut={0}&dateFin={1}&frequence={3}&pceList%5B%5D={2}"

    DATE_FORMAT = "%Y-%m-%d"

    FREQUENCY_VALUES = {
        Frequency.HOURLY: "Horaire",
        Frequency.DAILY: "Journalier",
        Frequency.WEEKLY: "Hebdomadaire",
        Frequency.MONTHLY: "Mensuel",
        Frequency.YEARLY: "Journalier"
    }

    DATA_FILENAME = 'Donnees_informatives_*.xlsx'

    # ------------------------------------------------------
    def __init__(self, username: str, password: str, tmpDirectory: str):

        super().__init__(username, password)

        self.__tmpDirectory = tmpDirectory

    # ------------------------------------------------------
    def _loadFromSession(self, session: Session, pceIdentifier: str, startDate: date, endDate: date, frequencies: Optional[List[Frequency]] = None) -> MeterReadingsByFrequency:

        res = {}

        # XLSX is in the TMP directory
        data_file_path_pattern = self.__tmpDirectory + '/' + ExcelWebDataSource.DATA_FILENAME

        # We remove an eventual existing data file (from a previous run that has not deleted it).
        file_list = glob.glob(data_file_path_pattern)
        for filename in file_list:
            if os.path.isfile(filename):
                os.remove(filename)

        if frequencies is None:
            # Transform Enum in List.
            frequencyList = [frequency for frequency in Frequency]
        else:
            # Get unique values.
            frequencyList = set(frequencies)

        for frequency in frequencyList:
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
                res[frequency.value] = ExcelParser.parse(filename, frequency if frequency != Frequency.YEARLY else Frequency.DAILY)
                os.remove(filename)

            # We compute yearly from daily data.
            if frequency == Frequency.YEARLY:
                res[frequency.value] = FrequencyConverter.computeYearly(res[frequency.value])

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

    def load(self, pceIdentifier: str, startDate: date, endDate: date, frequencies: Optional[List[Frequency]] = None) -> MeterReadingsByFrequency:

        res = {}

        if frequencies is None:
            # Transform Enum in List.
            frequencyList = [frequency for frequency in Frequency]
        else:
            # Get unique values.
            frequencyList = set(frequencies)

        for frequency in frequencyList:
            if frequency != Frequency.YEARLY:
                res[frequency.value] = ExcelParser.parse(self.__excelFile, frequency)
            else:
                daily = ExcelParser.parse(self.__excelFile, Frequency.DAILY)
                res[frequency.value] = FrequencyConverter.computeYearly(daily)

        return res


# ------------------------------------------------------------------------------------------------------------
class JsonWebDataSource(WebDataSource):

    DATA_URL = "https://monespace.grdf.fr/api/e-conso/pce/consommation/informatives?dateDebut={0}&dateFin={1}&pceList%5B%5D={2}"

    TEMPERATURES_URL = "https://monespace.grdf.fr/api/e-conso/pce/{0}/meteo?dateFinPeriode={1}&nbJours={2}"

    INPUT_DATE_FORMAT = "%Y-%m-%d"

    OUTPUT_DATE_FORMAT = "%d/%m/%Y"

    def __init__(self, username: str, password: str):

        super().__init__(username, password)

    def _loadFromSession(self, session: Session, pceIdentifier: str, startDate: date, endDate: date, frequencies: Optional[List[Frequency]] = None) -> MeterReadingsByFrequency:

        res = {}

        computeByFrequency = {
            Frequency.HOURLY: FrequencyConverter.computeHourly,
            Frequency.DAILY: FrequencyConverter.computeDaily,
            Frequency.WEEKLY: FrequencyConverter.computeWeekly,
            Frequency.MONTHLY: FrequencyConverter.computeMonthly,
            Frequency.YEARLY: FrequencyConverter.computeYearly
        }

        # Data URL: Inject parameters.
        downloadUrl = JsonWebDataSource.DATA_URL.format(startDate.strftime(JsonWebDataSource.INPUT_DATE_FORMAT), endDate.strftime(JsonWebDataSource.INPUT_DATE_FORMAT), pceIdentifier)

        # First request never returns data.
        session.get(downloadUrl)

        # Get consumption data.
        data = session.get(downloadUrl).text

        # Temperatures URL: Inject parameters.
        endDate = date.today() - timedelta(days=1) if endDate >= date.today() else endDate
        days = min((endDate - startDate).days, 730)
        temperaturesUrl = JsonWebDataSource.TEMPERATURES_URL.format(pceIdentifier, endDate.strftime(JsonWebDataSource.INPUT_DATE_FORMAT), days)

        # Get weather data.
        temperatures = session.get(temperaturesUrl).text

        # Transform all the data into the target structure.
        daily = JsonParser.parse(data, temperatures, pceIdentifier)

        if frequencies is None:
            # Transform Enum in List.
            frequencyList = [frequency for frequency in Frequency]
        else:
            # Get unique values.
            frequencyList = set(frequencies)

        for frequency in frequencyList:
            res[frequency.value] = computeByFrequency[frequency](daily)

        return res


# ------------------------------------------------------------------------------------------------------------
class JsonFileDataSource(IDataSource):

    def __init__(self, consumptionJsonFile: str, temperatureJsonFile):

        self.__consumptionJsonFile = consumptionJsonFile
        self.__temperatureJsonFile = temperatureJsonFile

    def load(self, pceIdentifier: str, startDate: date, endDate: date, frequencies: Optional[List[Frequency]] = None) -> MeterReadingsByFrequency:

        res = {}

        with open(self.__consumptionJsonFile) as consumptionJsonFile:
            with open(self.__temperatureJsonFile) as temperatureJsonFile:
                daily = JsonParser.parse(consumptionJsonFile.read(), temperatureJsonFile.read(), pceIdentifier)

        computeByFrequency = {
            Frequency.HOURLY: FrequencyConverter.computeHourly,
            Frequency.DAILY: FrequencyConverter.computeDaily,
            Frequency.WEEKLY: FrequencyConverter.computeWeekly,
            Frequency.MONTHLY: FrequencyConverter.computeMonthly,
            Frequency.YEARLY: FrequencyConverter.computeYearly
        }

        if frequencies is None:
            # Transform Enum in List.
            frequencyList = [frequency for frequency in Frequency]
        else:
            # Get unique values.
            frequencyList = set(frequencies)

        for frequency in frequencyList:
            res[frequency.value] = computeByFrequency[frequency](daily)

        return res


# ------------------------------------------------------------------------------------------------------------
class TestDataSource(IDataSource):

    def __init__(self):

        pass

    def load(self, pceIdentifier: str, startDate: date, endDate: date, frequencies: Optional[List[Frequency]] = None) -> MeterReadingsByFrequency:

        res = {}

        dataSampleFilenameByFrequency = {
            Frequency.HOURLY: "hourly_data_sample.json",
            Frequency.DAILY: "daily_data_sample.json",
            Frequency.WEEKLY: "weekly_data_sample.json",
            Frequency.MONTHLY: "monthly_data_sample.json",
            Frequency.YEARLY: "yearly_data_sample.json"
        }

        if frequencies is None:
            # Transform Enum in List.
            frequencyList = [frequency for frequency in Frequency]
        else:
            # Get unique values.
            frequencyList = set(frequencies)

        for frequency in frequencyList:
            dataSampleFilename = f"{os.path.dirname(os.path.abspath(__file__))}/resources/{dataSampleFilenameByFrequency[frequency]}"

            with open(dataSampleFilename) as jsonFile:
                res[frequency.value] = cast(List[Dict[PropertyName, Any]], json.load(jsonFile))

        return res


# ------------------------------------------------------------------------------------------------------------
class FrequencyConverter:

    MONTHS = [
        "Janvier",
        "Février",
        "Mars",
        "Avril",
        "Mai",
        "Juin",
        "Juillet",
        "Août",
        "Septembre",
        "Octobre",
        "Novembre",
        "Décembre"
    ]

    # ------------------------------------------------------
    @staticmethod
    def computeHourly(daily: List[Dict[str, Any]]) -> List[Dict[str, Any]]:

        return []

    # ------------------------------------------------------
    @staticmethod
    def computeDaily(daily: List[Dict[str, Any]]) -> List[Dict[str, Any]]:

        return daily

    # ------------------------------------------------------
    @staticmethod
    def computeWeekly(daily: List[Dict[str, Any]]) -> List[Dict[str, Any]]:

        df = pd.DataFrame(daily)

        # Trimming head and trailing spaces and convert to datetime.
        df["date_time"] = pd.to_datetime(df["time_period"].str.strip(), format=JsonWebDataSource.OUTPUT_DATE_FORMAT)

        # Get the first day of week.
        df["first_day_of_week"] = pd.to_datetime(df["date_time"].dt.strftime("%W %Y 1"), format="%W %Y %w")

        # Get the last day of week.
        df["last_day_of_week"] = pd.to_datetime(df["date_time"].dt.strftime("%W %Y 0"), format="%W %Y %w")

        # Reformat the time period.
        df["time_period"] = "Du " + df["first_day_of_week"].dt.strftime(JsonWebDataSource.OUTPUT_DATE_FORMAT).astype(str) + " au " + df["last_day_of_week"].dt.strftime(JsonWebDataSource.OUTPUT_DATE_FORMAT).astype(str)

        # Aggregate rows by month_year.
        df = df[["first_day_of_week", "time_period", "start_index_m3", "end_index_m3", "volume_m3", "energy_kwh", "timestamp"]].groupby("time_period").agg(first_day_of_week=('first_day_of_week', 'min'), start_index_m3=('start_index_m3', 'min'), end_index_m3=('end_index_m3', 'max'), volume_m3=('volume_m3', 'sum'), energy_kwh=('energy_kwh', 'sum'), timestamp=('timestamp', 'min'), count=('energy_kwh', 'count')).reset_index()

        # Sort rows by month ascending.
        df = df.sort_values(by=['first_day_of_week'])

        # Select rows where we have a full week (7 days) except for the current week.
        df = pd.concat([df[(df["count"] == 7)], df.tail(1)])

        # Select target columns.
        df = df[["time_period", "start_index_m3", "end_index_m3", "volume_m3", "energy_kwh", "timestamp"]]

        res = cast(List[Dict[str, Any]], df.to_dict('records'))

        return res

    # ------------------------------------------------------
    @staticmethod
    def computeMonthly(daily: List[Dict[str, Any]]) -> List[Dict[str, Any]]:

        df = pd.DataFrame(daily)

        # Trimming head and trailing spaces and convert to datetime.
        df["date_time"] = pd.to_datetime(df["time_period"].str.strip(), format=JsonWebDataSource.OUTPUT_DATE_FORMAT)

        # Get the corresponding month-year.
        df["month_year"] = df["date_time"].apply(lambda x: FrequencyConverter.MONTHS[x.month - 1]).astype(str) + " " + df["date_time"].dt.strftime("%Y").astype(str)

        # Aggregate rows by month_year.
        df = df[["date_time", "month_year", "start_index_m3", "end_index_m3", "volume_m3", "energy_kwh", "timestamp"]].groupby("month_year").agg(first_day_of_month=('date_time', 'min'), start_index_m3=('start_index_m3', 'min'), end_index_m3=('end_index_m3', 'max'), volume_m3=('volume_m3', 'sum'), energy_kwh=('energy_kwh', 'sum'), timestamp=('timestamp', 'min'), count=('energy_kwh', 'count')).reset_index()

        # Sort rows by month ascending.
        df = df.sort_values(by=['first_day_of_month'])

        # Select rows where we have a full month (more than 27 days) except for the current month.
        df = pd.concat([df[(df["count"] >= 28)], df.tail(1)])

        # Rename columns for their target names.
        df = df.rename(columns={"month_year": "time_period"})

        # Select target columns.
        df = df[["time_period", "start_index_m3", "end_index_m3", "volume_m3", "energy_kwh", "timestamp"]]

        res = cast(List[Dict[str, Any]], df.to_dict('records'))

        return res

    # ------------------------------------------------------
    @staticmethod
    def computeYearly(daily: List[Dict[str, Any]]) -> List[Dict[str, Any]]:

        df = pd.DataFrame(daily)

        # Trimming head and trailing spaces and convert to datetime.
        df["date_time"] = pd.to_datetime(df["time_period"].str.strip(), format=JsonWebDataSource.OUTPUT_DATE_FORMAT)

        # Get the corresponding year.
        df["year"] = df["date_time"].dt.strftime("%Y")

        # Aggregate rows by month_year.
        df = df[["year", "start_index_m3", "end_index_m3", "volume_m3", "energy_kwh", "timestamp"]].groupby("year").agg(start_index_m3=('start_index_m3', 'min'), end_index_m3=('end_index_m3', 'max'), volume_m3=('volume_m3', 'sum'), energy_kwh=('energy_kwh', 'sum'), timestamp=('timestamp', 'min'), count=('energy_kwh', 'count')).reset_index()

        # Sort rows by month ascending.
        df = df.sort_values(by=['year'])

        # Select rows where we have almost a full year (more than 360) except for the current month.
        df = pd.concat([df[(df["count"] >= 360)], df.tail(1)])

        # Rename columns for their target names.
        df = df.rename(columns={"year": "time_period"})

        # Select target columns.
        df = df[["time_period", "start_index_m3", "end_index_m3", "volume_m3", "energy_kwh", "timestamp"]]

        res = cast(List[Dict[str, Any]], df.to_dict('records'))

        return res
