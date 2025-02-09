import glob
import json
import logging
import os
from abc import ABC, abstractmethod
from datetime import date, timedelta
from typing import Any, Optional, cast

import pandas as pd

from pygazpar.api_client import APIClient, ConsumptionType
from pygazpar.api_client import Frequency as APIClientFrequency
from pygazpar.enum import Frequency, PropertyName
from pygazpar.excelparser import ExcelParser
from pygazpar.jsonparser import JsonParser

Logger = logging.getLogger(__name__)

MeterReading = dict[str, Any]

MeterReadings = list[MeterReading]

MeterReadingsByFrequency = dict[str, MeterReadings]


# ------------------------------------------------------------------------------------------------------------
class IDataSource(ABC):  # pylint: disable=too-few-public-methods

    @abstractmethod
    def login(self):
        pass

    @abstractmethod
    def logout(self):
        pass

    @abstractmethod
    def get_pce_identifiers(self) -> list[str]:
        pass

    @abstractmethod
    def load(
        self, pceIdentifier: str, startDate: date, endDate: date, frequencies: Optional[list[Frequency]] = None
    ) -> MeterReadingsByFrequency:
        pass


# ------------------------------------------------------------------------------------------------------------
class WebDataSource(IDataSource):  # pylint: disable=too-few-public-methods

    # ------------------------------------------------------
    def __init__(self, username: str, password: str):

        self._api_client = APIClient(username, password)

    # ------------------------------------------------------
    def login(self):

        if not self._api_client.is_logged_in():
            self._api_client.login()

    # ------------------------------------------------------
    def logout(self):

        if self._api_client.is_logged_in():
            self._api_client.logout()

    # ------------------------------------------------------
    def get_pce_identifiers(self) -> list[str]:

        if not self._api_client.is_logged_in():
            self._api_client.login()

        pce_list = self._api_client.get_pce_list()

        if pce_list is None:
            return []

        return [pce["idObject"] for pce in pce_list]

    # ------------------------------------------------------
    def load(
        self, pceIdentifier: str, startDate: date, endDate: date, frequencies: Optional[list[Frequency]] = None
    ) -> MeterReadingsByFrequency:

        if not self._api_client.is_logged_in():
            self._api_client.login()

        res = self._loadFromSession(pceIdentifier, startDate, endDate, frequencies)

        Logger.debug("The data update terminates normally")

        return res

    @abstractmethod
    def _loadFromSession(
        self, pceIdentifier: str, startDate: date, endDate: date, frequencies: Optional[list[Frequency]] = None
    ) -> MeterReadingsByFrequency:
        pass


# ------------------------------------------------------------------------------------------------------------
class ExcelWebDataSource(WebDataSource):  # pylint: disable=too-few-public-methods

    DATE_FORMAT = "%Y-%m-%d"

    FREQUENCY_VALUES = {
        Frequency.HOURLY: "Horaire",
        Frequency.DAILY: "Journalier",
        Frequency.WEEKLY: "Hebdomadaire",
        Frequency.MONTHLY: "Mensuel",
        Frequency.YEARLY: "Journalier",
    }

    DATA_FILENAME = "Donnees_informatives_*.xlsx"

    # ------------------------------------------------------
    def __init__(self, username: str, password: str, tmpDirectory: str):

        super().__init__(username, password)

        self.__tmpDirectory = tmpDirectory

    # ------------------------------------------------------
    def _loadFromSession(  # pylint: disable=too-many-branches
        self, pceIdentifier: str, startDate: date, endDate: date, frequencies: Optional[list[Frequency]] = None
    ) -> MeterReadingsByFrequency:  # pylint: disable=too-many-branches

        res = {}

        # XLSX is in the TMP directory
        data_file_path_pattern = self.__tmpDirectory + "/" + ExcelWebDataSource.DATA_FILENAME

        # We remove an eventual existing data file (from a previous run that has not deleted it).
        file_list = glob.glob(data_file_path_pattern)
        for filename in file_list:
            if os.path.isfile(filename):
                try:
                    os.remove(filename)
                except PermissionError:
                    pass

        if frequencies is None:
            # Transform Enum in List.
            frequencyList = list(Frequency)
        else:
            # Get distinct values.
            frequencyList = list(set(frequencies))

        for frequency in frequencyList:

            Logger.debug(
                f"Loading data of frequency {ExcelWebDataSource.FREQUENCY_VALUES[frequency]} from {startDate.strftime(ExcelWebDataSource.DATE_FORMAT)} to {endDate.strftime(ExcelWebDataSource.DATE_FORMAT)}"
            )

            response = self._api_client.get_pce_consumption_excelsheet(
                ConsumptionType.INFORMATIVE,
                startDate,
                endDate,
                APIClientFrequency(ExcelWebDataSource.FREQUENCY_VALUES[frequency]),
                [pceIdentifier],
            )

            filename = response["filename"]
            content = response["content"]

            with open(f"{self.__tmpDirectory}/{filename}", "wb") as file:
                file.write(content)

            # Load the XLSX file into the data structure
            file_list = glob.glob(data_file_path_pattern)

            if len(file_list) == 0:
                Logger.warning(f"Not any data file has been found in '{self.__tmpDirectory}' directory")

            for filename in file_list:
                res[frequency.value] = ExcelParser.parse(
                    filename, frequency if frequency != Frequency.YEARLY else Frequency.DAILY
                )
                try:
                    # openpyxl does not close the file properly.
                    os.remove(filename)
                except PermissionError:
                    pass

            # We compute yearly from daily data.
            if frequency == Frequency.YEARLY:
                res[frequency.value] = FrequencyConverter.computeYearly(res[frequency.value])

        return res


# ------------------------------------------------------------------------------------------------------------
class ExcelFileDataSource(IDataSource):  # pylint: disable=too-few-public-methods

    def __init__(self, excelFile: str):

        self.__excelFile = excelFile

    # ------------------------------------------------------
    def login(self):
        pass

    # ------------------------------------------------------
    def logout(self):
        pass

    # ------------------------------------------------------
    def get_pce_identifiers(self) -> list[str]:

        return ["0123456789"]

    # ------------------------------------------------------
    def load(
        self, pceIdentifier: str, startDate: date, endDate: date, frequencies: Optional[list[Frequency]] = None
    ) -> MeterReadingsByFrequency:

        res = {}

        if frequencies is None:
            # Transform Enum in List.
            frequencyList = list(Frequency)
        else:
            # Get unique values.
            frequencyList = list(set(frequencies))

        for frequency in frequencyList:
            if frequency != Frequency.YEARLY:
                res[frequency.value] = ExcelParser.parse(self.__excelFile, frequency)
            else:
                daily = ExcelParser.parse(self.__excelFile, Frequency.DAILY)
                res[frequency.value] = FrequencyConverter.computeYearly(daily)

        return res


# ------------------------------------------------------------------------------------------------------------
class JsonWebDataSource(WebDataSource):  # pylint: disable=too-few-public-methods

    INPUT_DATE_FORMAT = "%Y-%m-%d"

    OUTPUT_DATE_FORMAT = "%d/%m/%Y"

    # ------------------------------------------------------
    def _loadFromSession(
        self, pceIdentifier: str, startDate: date, endDate: date, frequencies: Optional[list[Frequency]] = None
    ) -> MeterReadingsByFrequency:

        res = dict[str, Any]()

        computeByFrequency = {
            Frequency.HOURLY: FrequencyConverter.computeHourly,
            Frequency.DAILY: FrequencyConverter.computeDaily,
            Frequency.WEEKLY: FrequencyConverter.computeWeekly,
            Frequency.MONTHLY: FrequencyConverter.computeMonthly,
            Frequency.YEARLY: FrequencyConverter.computeYearly,
        }

        data = self._api_client.get_pce_consumption(ConsumptionType.INFORMATIVE, startDate, endDate, [pceIdentifier])

        Logger.debug("Json meter data: %s", data)

        # Temperatures URL: Inject parameters.
        endDate = date.today() - timedelta(days=1) if endDate >= date.today() else endDate
        days = max(
            min((endDate - startDate).days, 730), 10
        )  # At least 10 days, at most 730 days, to avoid HTTP 500 error.

        # Get weather data.
        try:
            temperatures = self._api_client.get_pce_meteo(endDate, days, pceIdentifier)
        except Exception:  # pylint: disable=broad-except
            # Not a blocking error.
            temperatures = None

        Logger.debug("Json temperature data: %s", temperatures)

        # Transform all the data into the target structure.
        if data is None or len(data) == 0:
            return res

        daily = JsonParser.parse(json.dumps(data), json.dumps(temperatures), pceIdentifier)

        Logger.debug("Processed daily data: %s", daily)

        if frequencies is None:
            # Transform Enum in List.
            frequencyList = list(Frequency)
        else:
            # Get unique values.
            frequencyList = list(set(frequencies))

        for frequency in frequencyList:
            res[frequency.value] = computeByFrequency[frequency](daily)

        return res


# ------------------------------------------------------------------------------------------------------------
class JsonFileDataSource(IDataSource):  # pylint: disable=too-few-public-methods

    # ------------------------------------------------------
    def __init__(self, consumptionJsonFile: str, temperatureJsonFile):

        self.__consumptionJsonFile = consumptionJsonFile
        self.__temperatureJsonFile = temperatureJsonFile

    # ------------------------------------------------------
    def login(self):
        pass

    # ------------------------------------------------------
    def logout(self):
        pass

    # ------------------------------------------------------
    def get_pce_identifiers(self) -> list[str]:

        return ["0123456789"]

    # ------------------------------------------------------
    def load(
        self, pceIdentifier: str, startDate: date, endDate: date, frequencies: Optional[list[Frequency]] = None
    ) -> MeterReadingsByFrequency:

        res = {}

        with open(self.__consumptionJsonFile, mode="r", encoding="utf-8") as consumptionJsonFile:
            with open(self.__temperatureJsonFile, mode="r", encoding="utf-8") as temperatureJsonFile:
                daily = JsonParser.parse(consumptionJsonFile.read(), temperatureJsonFile.read(), pceIdentifier)

        computeByFrequency = {
            Frequency.HOURLY: FrequencyConverter.computeHourly,
            Frequency.DAILY: FrequencyConverter.computeDaily,
            Frequency.WEEKLY: FrequencyConverter.computeWeekly,
            Frequency.MONTHLY: FrequencyConverter.computeMonthly,
            Frequency.YEARLY: FrequencyConverter.computeYearly,
        }

        if frequencies is None:
            # Transform Enum in List.
            frequencyList = list(Frequency)
        else:
            # Get unique values.
            frequencyList = list(set(frequencies))

        for frequency in frequencyList:
            res[frequency.value] = computeByFrequency[frequency](daily)

        return res


# ------------------------------------------------------------------------------------------------------------
class TestDataSource(IDataSource):  # pylint: disable=too-few-public-methods

    __test__ = False  # Will not be discovered as a test

    # ------------------------------------------------------
    def __init__(self):

        pass

    # ------------------------------------------------------
    def login(self):
        pass

    # ------------------------------------------------------
    def logout(self):
        pass

    # ------------------------------------------------------
    def get_pce_identifiers(self) -> list[str]:

        return ["0123456789"]

    # ------------------------------------------------------
    def load(
        self, pceIdentifier: str, startDate: date, endDate: date, frequencies: Optional[list[Frequency]] = None
    ) -> MeterReadingsByFrequency:

        res = dict[str, Any]()

        dataSampleFilenameByFrequency = {
            Frequency.HOURLY: "hourly_data_sample.json",
            Frequency.DAILY: "daily_data_sample.json",
            Frequency.WEEKLY: "weekly_data_sample.json",
            Frequency.MONTHLY: "monthly_data_sample.json",
            Frequency.YEARLY: "yearly_data_sample.json",
        }

        if frequencies is None:
            # Transform Enum in List.
            frequencyList = list(Frequency)
        else:
            # Get unique values.
            frequencyList = list(set(frequencies))

        for frequency in frequencyList:
            dataSampleFilename = (
                f"{os.path.dirname(os.path.abspath(__file__))}/resources/{dataSampleFilenameByFrequency[frequency]}"
            )

            with open(dataSampleFilename, mode="r", encoding="utf-8") as jsonFile:
                res[frequency.value] = cast(list[dict[PropertyName, Any]], json.load(jsonFile))

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
        "Décembre",
    ]

    # ------------------------------------------------------
    @staticmethod
    def computeHourly(daily: list[dict[str, Any]]) -> list[dict[str, Any]]:  # pylint: disable=unused-argument

        return []

    # ------------------------------------------------------
    @staticmethod
    def computeDaily(daily: list[dict[str, Any]]) -> list[dict[str, Any]]:

        return daily

    # ------------------------------------------------------
    @staticmethod
    def computeWeekly(daily: list[dict[str, Any]]) -> list[dict[str, Any]]:

        df = pd.DataFrame(daily)

        # Trimming head and trailing spaces and convert to datetime.
        df["date_time"] = pd.to_datetime(df["time_period"].str.strip(), format=JsonWebDataSource.OUTPUT_DATE_FORMAT)

        # Get the first day of week.
        df["first_day_of_week"] = pd.to_datetime(df["date_time"].dt.strftime("%W %Y 1"), format="%W %Y %w")

        # Get the last day of week.
        df["last_day_of_week"] = pd.to_datetime(df["date_time"].dt.strftime("%W %Y 0"), format="%W %Y %w")

        # Reformat the time period.
        df["time_period"] = (
            "Du "
            + df["first_day_of_week"].dt.strftime(JsonWebDataSource.OUTPUT_DATE_FORMAT).astype(str)
            + " au "
            + df["last_day_of_week"].dt.strftime(JsonWebDataSource.OUTPUT_DATE_FORMAT).astype(str)
        )

        # Aggregate rows by month_year.
        df = (
            df[
                [
                    "first_day_of_week",
                    "time_period",
                    "start_index_m3",
                    "end_index_m3",
                    "volume_m3",
                    "energy_kwh",
                    "timestamp",
                ]
            ]
            .groupby("time_period")
            .agg(
                first_day_of_week=("first_day_of_week", "min"),
                start_index_m3=("start_index_m3", "min"),
                end_index_m3=("end_index_m3", "max"),
                volume_m3=("volume_m3", "sum"),
                energy_kwh=("energy_kwh", "sum"),
                timestamp=("timestamp", "min"),
                count=("energy_kwh", "count"),
            )
            .reset_index()
        )

        # Sort rows by month ascending.
        df = df.sort_values(by=["first_day_of_week"])

        # Select rows where we have a full week (7 days) except for the current week.
        df = pd.concat([df[(df["count"] >= 7)], df.tail(1)[df.tail(1)["count"] < 7]])

        # Select target columns.
        df = df[["time_period", "start_index_m3", "end_index_m3", "volume_m3", "energy_kwh", "timestamp"]]

        res = cast(list[dict[str, Any]], df.to_dict("records"))

        return res

    # ------------------------------------------------------
    @staticmethod
    def computeMonthly(daily: list[dict[str, Any]]) -> list[dict[str, Any]]:

        df = pd.DataFrame(daily)

        # Trimming head and trailing spaces and convert to datetime.
        df["date_time"] = pd.to_datetime(df["time_period"].str.strip(), format=JsonWebDataSource.OUTPUT_DATE_FORMAT)

        # Get the corresponding month-year.
        df["month_year"] = (
            df["date_time"].apply(lambda x: FrequencyConverter.MONTHS[x.month - 1]).astype(str)
            + " "
            + df["date_time"].dt.strftime("%Y").astype(str)
        )

        # Aggregate rows by month_year.
        df = (
            df[["date_time", "month_year", "start_index_m3", "end_index_m3", "volume_m3", "energy_kwh", "timestamp"]]
            .groupby("month_year")
            .agg(
                first_day_of_month=("date_time", "min"),
                start_index_m3=("start_index_m3", "min"),
                end_index_m3=("end_index_m3", "max"),
                volume_m3=("volume_m3", "sum"),
                energy_kwh=("energy_kwh", "sum"),
                timestamp=("timestamp", "min"),
                count=("energy_kwh", "count"),
            )
            .reset_index()
        )

        # Sort rows by month ascending.
        df = df.sort_values(by=["first_day_of_month"])

        # Select rows where we have a full month (more than 27 days) except for the current month.
        df = pd.concat([df[(df["count"] >= 28)], df.tail(1)[df.tail(1)["count"] < 28]])

        # Rename columns for their target names.
        df = df.rename(columns={"month_year": "time_period"})

        # Select target columns.
        df = df[["time_period", "start_index_m3", "end_index_m3", "volume_m3", "energy_kwh", "timestamp"]]

        res = cast(list[dict[str, Any]], df.to_dict("records"))

        return res

    # ------------------------------------------------------
    @staticmethod
    def computeYearly(daily: list[dict[str, Any]]) -> list[dict[str, Any]]:

        df = pd.DataFrame(daily)

        # Trimming head and trailing spaces and convert to datetime.
        df["date_time"] = pd.to_datetime(df["time_period"].str.strip(), format=JsonWebDataSource.OUTPUT_DATE_FORMAT)

        # Get the corresponding year.
        df["year"] = df["date_time"].dt.strftime("%Y")

        # Aggregate rows by month_year.
        df = (
            df[["year", "start_index_m3", "end_index_m3", "volume_m3", "energy_kwh", "timestamp"]]
            .groupby("year")
            .agg(
                start_index_m3=("start_index_m3", "min"),
                end_index_m3=("end_index_m3", "max"),
                volume_m3=("volume_m3", "sum"),
                energy_kwh=("energy_kwh", "sum"),
                timestamp=("timestamp", "min"),
                count=("energy_kwh", "count"),
            )
            .reset_index()
        )

        # Sort rows by month ascending.
        df = df.sort_values(by=["year"])

        # Select rows where we have almost a full year (more than 360) except for the current year.
        df = pd.concat([df[(df["count"] >= 360)], df.tail(1)[df.tail(1)["count"] < 360]])

        # Rename columns for their target names.
        df = df.rename(columns={"year": "time_period"})

        # Select target columns.
        df = df[["time_period", "start_index_m3", "end_index_m3", "volume_m3", "energy_kwh", "timestamp"]]

        res = cast(list[dict[str, Any]], df.to_dict("records"))

        return res
