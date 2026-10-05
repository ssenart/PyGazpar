import glob
import json
import logging
import os
from abc import ABC, abstractmethod
from collections.abc import Callable, Sequence
from datetime import date, timedelta
from typing import Any, cast

from pygazpar.api_client import APIClient, ConsumptionType, ServerError
from pygazpar.api_client import Frequency as APIClientFrequency
from pygazpar.excelparser import ExcelParser
from pygazpar.jsonparser import JsonParser
from pygazpar.model import MONTHS as MONTH_NAMES
from pygazpar.model import (
    DailyReading,
    Frequency,
    PeriodReading,
    PropertyName,
    next_month_start,
    parse_period_label,
)

Logger = logging.getLogger(__name__)

MeterReading = dict[str, Any]

MeterReadings = list[MeterReading]

MeterReadingsByFrequency = dict[str, MeterReadings]

ReadingsByFrequency = dict[str, Sequence[PeriodReading]]


def as_dicts(readings: Sequence[PeriodReading]) -> MeterReadings:
    """Returns the readings as dicts, the form the datasources give to their users."""

    return [reading.model_dump(by_alias=True) for reading in readings]


def readings_from_samples(frequency: Frequency, rows: list[dict[str, Any]]) -> list[PeriodReading]:
    """Returns the readings of a sample file. The dates of each reading come from its label."""

    model = DailyReading if frequency == Frequency.DAILY else PeriodReading
    res: list[PeriodReading] = []
    for row in rows:
        start_date, end_date = parse_period_label(frequency, row[PropertyName.TIME_PERIOD.value])
        res.append(
            model.model_validate(
                {
                    **row,
                    PropertyName.START_DATE.value: start_date,
                    PropertyName.END_DATE.value: end_date,
                    PropertyName.FREQUENCY.value: frequency,
                }
            )
        )

    return res


# ------------------------------------------------------------------------------------------------------------
def meteo_window(start_date: date, end_date: date) -> tuple[date, int]:
    """Returns the end date and the number of days to request temperatures for a consumption period.

    The end date is capped at yesterday, and the number of days is kept between 10 and 730 to avoid HTTP 500 errors.
    """

    meteo_end_date = date.today() - timedelta(days=1) if end_date >= date.today() else end_date
    meteo_days = max(min((meteo_end_date - start_date).days, 730), 10)

    return meteo_end_date, meteo_days


# ------------------------------------------------------------------------------------------------------------
class UnknownPceError(ServerError):
    """Raised when the PCE identifier is not one of the PCEs of the account.

    The status code is the one GrDF sends when it refuses an unknown PCE for the temperatures.
    """

    def __init__(self, pceIdentifier: str):
        super().__init__(f"The PCE {pceIdentifier} does not exist in this account.", 400)


# ------------------------------------------------------------------------------------------------------------
class IDataSource(ABC):
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
    def readings(
        self, pceIdentifier: str, startDate: date, endDate: date, frequencies: list[Frequency] | None = None
    ) -> ReadingsByFrequency:
        pass

    # ------------------------------------------------------
    def load(
        self, pceIdentifier: str, startDate: date, endDate: date, frequencies: list[Frequency] | None = None
    ) -> MeterReadingsByFrequency:
        """Returns the readings as dicts, the form the datasources give to their users."""

        return {
            key: as_dicts(value) for key, value in self.readings(pceIdentifier, startDate, endDate, frequencies).items()
        }


# ------------------------------------------------------------------------------------------------------------
class WebDataSource(IDataSource):
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

        return [pce.idObject for pce in pce_list]

    # ------------------------------------------------------
    def readings(
        self, pceIdentifier: str, startDate: date, endDate: date, frequencies: list[Frequency] | None = None
    ) -> ReadingsByFrequency:

        if not self._api_client.is_logged_in():
            self._api_client.login()

        if pceIdentifier not in self.get_pce_identifiers():
            raise UnknownPceError(pceIdentifier)

        res = self._loadFromSession(pceIdentifier, startDate, endDate, frequencies)

        Logger.debug("The data update terminates normally")

        return res

    @abstractmethod
    def _loadFromSession(
        self, pceIdentifier: str, startDate: date, endDate: date, frequencies: list[Frequency] | None = None
    ) -> ReadingsByFrequency:
        pass


# ------------------------------------------------------------------------------------------------------------
class ExcelWebDataSource(WebDataSource):
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
    def _loadFromSession(
        self, pceIdentifier: str, startDate: date, endDate: date, frequencies: list[Frequency] | None = None
    ) -> ReadingsByFrequency:

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

            filename = response.filename
            content = response.content

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
class ExcelFileDataSource(IDataSource):
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
    def readings(
        self,
        pceIdentifier: str,  # noqa: ARG002
        startDate: date,  # noqa: ARG002
        endDate: date,  # noqa: ARG002
        frequencies: list[Frequency] | None = None,
    ) -> ReadingsByFrequency:

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
class JsonWebDataSource(WebDataSource):
    INPUT_DATE_FORMAT = "%Y-%m-%d"

    OUTPUT_DATE_FORMAT = "%d/%m/%Y"

    # ------------------------------------------------------
    def __init__(
        self,
        username: str,
        password: str,
        consumption_type: ConsumptionType = ConsumptionType.INFORMATIVE,
    ):
        super().__init__(username, password)
        self.__consumption_type = consumption_type

    # ------------------------------------------------------
    def _loadFromSession(
        self, pceIdentifier: str, startDate: date, endDate: date, frequencies: list[Frequency] | None = None
    ) -> ReadingsByFrequency:

        res = dict[str, Any]()

        computeByFrequency = {
            Frequency.HOURLY: FrequencyConverter.computeHourly,
            Frequency.DAILY: FrequencyConverter.computeDaily,
            Frequency.WEEKLY: FrequencyConverter.computeWeekly,
            Frequency.MONTHLY: FrequencyConverter.computeMonthly,
            Frequency.YEARLY: FrequencyConverter.computeYearly,
        }

        data = self._api_client.get_pce_consumption(self.__consumption_type, startDate, endDate, [pceIdentifier])

        Logger.debug("Json meter data: %s", data)

        meteo_end_date, meteo_days = meteo_window(startDate, endDate)

        # Get weather data.
        try:
            temperatures = self._api_client.get_pce_meteo(meteo_end_date, meteo_days, pceIdentifier)
        except Exception:  # noqa: BLE001
            # Not a blocking error.
            temperatures = None

        Logger.debug("Json temperature data: %s", temperatures)

        # Transform all the data into the target structure.
        if data is None or len(data) == 0:
            return res

        daily = JsonParser.readings(data, temperatures, pceIdentifier)

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
class RawConsumptionWebDataSource:
    """Returns the GrDF consumption API response as received, without post processing.

    Not an IDataSource: load() returns the raw payload, not a MeterReadingsByFrequency.
    """

    # ------------------------------------------------------
    def __init__(
        self,
        username: str,
        password: str,
        consumption_type: ConsumptionType = ConsumptionType.INFORMATIVE,
    ):
        self.__api_client = APIClient(username, password)
        self.__consumption_type = consumption_type

    # ------------------------------------------------------
    def load(self, pce_identifier: str, start_date: date, end_date: date) -> dict[str, Any]:

        if not self.__api_client.is_logged_in():
            self.__api_client.login()

        return self.__api_client.get_pce_consumption_raw(
            self.__consumption_type, start_date, end_date, [pce_identifier]
        )


# ------------------------------------------------------------------------------------------------------------
class RawTemperatureWebDataSource:
    """Returns the GrDF temperature (meteo) API response as received, without post processing.

    Not an IDataSource: load() returns the raw payload, not a MeterReadingsByFrequency.
    """

    # ------------------------------------------------------
    def __init__(self, username: str, password: str):

        self.__api_client = APIClient(username, password)

    # ------------------------------------------------------
    def load(self, pce_identifier: str, start_date: date, end_date: date) -> dict[str, Any]:

        if not self.__api_client.is_logged_in():
            self.__api_client.login()

        meteo_end_date, meteo_days = meteo_window(start_date, end_date)

        return self.__api_client.get_pce_meteo_raw(meteo_end_date, meteo_days, pce_identifier)


# ------------------------------------------------------------------------------------------------------------
class JsonFileDataSource(IDataSource):
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
    def readings(
        self,
        pceIdentifier: str,
        startDate: date,  # noqa: ARG002
        endDate: date,  # noqa: ARG002
        frequencies: list[Frequency] | None = None,
    ) -> ReadingsByFrequency:

        res: ReadingsByFrequency = {}

        with open(self.__consumptionJsonFile, encoding="utf-8") as consumptionJsonFile:
            with open(self.__temperatureJsonFile, encoding="utf-8") as temperatureJsonFile:
                daily = JsonParser.readings_from_json(
                    consumptionJsonFile.read(), temperatureJsonFile.read(), pceIdentifier
                )

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
class TestDataSource(IDataSource):
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
    def readings(
        self,
        pceIdentifier: str,  # noqa: ARG002
        startDate: date,  # noqa: ARG002
        endDate: date,  # noqa: ARG002
        frequencies: list[Frequency] | None = None,
    ) -> ReadingsByFrequency:

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

            with open(dataSampleFilename, encoding="utf-8") as jsonFile:
                rows = cast(list[dict[str, Any]], json.load(jsonFile))
                res[frequency.value] = [] if frequency == Frequency.HOURLY else readings_from_samples(frequency, rows)

        return res


# ------------------------------------------------------------------------------------------------------------
class FrequencyConverter:
    MONTHS = MONTH_NAMES

    # ------------------------------------------------------
    @staticmethod
    def computeHourly(daily: Sequence[PeriodReading]) -> list[PeriodReading]:  # noqa: ARG004

        return []

    # ------------------------------------------------------
    @staticmethod
    def computeDaily(daily: Sequence[PeriodReading]) -> list[PeriodReading]:

        return list(daily)

    # ------------------------------------------------------
    @staticmethod
    def computeWeekly(daily: Sequence[PeriodReading]) -> list[PeriodReading]:

        return FrequencyConverter.__aggregate(
            daily, Frequency.WEEKLY, lambda day: day - timedelta(days=day.weekday()), minimum_days=7
        )

    # ------------------------------------------------------
    @staticmethod
    def computeMonthly(daily: Sequence[PeriodReading]) -> list[PeriodReading]:

        return FrequencyConverter.__aggregate(daily, Frequency.MONTHLY, lambda day: day.replace(day=1), minimum_days=28)

    # ------------------------------------------------------
    @staticmethod
    def computeYearly(daily: Sequence[PeriodReading]) -> list[PeriodReading]:

        return FrequencyConverter.__aggregate(
            daily, Frequency.YEARLY, lambda day: day.replace(month=1, day=1), minimum_days=360
        )

    # ------------------------------------------------------
    @staticmethod
    def __aggregate(
        daily: Sequence[PeriodReading],
        frequency: Frequency,
        bucket_start: Callable[[date], date],
        minimum_days: int,
    ) -> list[PeriodReading]:
        """Groups the days into the periods of a frequency, whole periods from the calendar.

        A period is kept when it has at least minimum_days days with consumption. The last period is always kept, even
        when it is partial.
        """

        buckets: dict[date, list[PeriodReading]] = {}
        for day in daily:
            buckets.setdefault(bucket_start(day.start_date), []).append(day)

        starts = sorted(buckets)
        res: list[PeriodReading] = []
        for index, start in enumerate(starts):
            rows = buckets[start]
            days_with_consumption = sum(1 for row in rows if row.energy_kwh is not None)
            if days_with_consumption < minimum_days and index != len(starts) - 1:
                continue

            res.append(
                PeriodReading(
                    start_date=start,
                    end_date=FrequencyConverter.__period_end(frequency, start),
                    frequency=frequency,
                    start_index_m3=min((r.start_index_m3 for r in rows if r.start_index_m3 is not None), default=None),
                    end_index_m3=max((r.end_index_m3 for r in rows if r.end_index_m3 is not None), default=None),
                    volume_m3=sum((r.volume_m3 for r in rows if r.volume_m3 is not None), 0),
                    energy_kwh=sum((r.energy_kwh for r in rows if r.energy_kwh is not None), 0),
                    timestamp=min(r.timestamp for r in rows),
                )
            )

        return res

    # ------------------------------------------------------
    @staticmethod
    def __period_end(frequency: Frequency, start: date) -> date:
        """Returns the day after the last day of a period that starts on start."""

        if frequency == Frequency.WEEKLY:
            return start + timedelta(days=7)
        if frequency == Frequency.MONTHLY:
            return next_month_start(start)

        return date(start.year + 1, 1, 1)
