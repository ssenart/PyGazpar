import json
import logging
import os
import tempfile
import warnings
from abc import ABC, abstractmethod
from collections.abc import Callable, Sequence
from datetime import date, timedelta
from typing import Any, cast

from pygazpar.api_client import DEFAULT_EXCEL_FILENAME, APIClient, ConsumptionType, ServerError
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

    def __init__(self, pce_identifier: str):
        super().__init__(f"The PCE {pce_identifier} does not exist in this account.", 400)


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
        self, pce_identifier: str, start_date: date, end_date: date, frequencies: list[Frequency] | None = None
    ) -> ReadingsByFrequency:
        pass

    # ------------------------------------------------------
    def load(
        self, pce_identifier: str, start_date: date, end_date: date, frequencies: list[Frequency] | None = None
    ) -> MeterReadingsByFrequency:
        """Returns the readings as dicts, the form the datasources give to their users."""

        return {
            key: as_dicts(value)
            for key, value in self.readings(pce_identifier, start_date, end_date, frequencies).items()
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

        return [pce.id_object for pce in pce_list]

    # ------------------------------------------------------
    def readings(
        self, pce_identifier: str, start_date: date, end_date: date, frequencies: list[Frequency] | None = None
    ) -> ReadingsByFrequency:

        if not self._api_client.is_logged_in():
            self._api_client.login()

        if pce_identifier not in self.get_pce_identifiers():
            raise UnknownPceError(pce_identifier)

        res = self._load_from_session(pce_identifier, start_date, end_date, frequencies)

        Logger.debug("The data update terminates normally")

        return res

    @abstractmethod
    def _load_from_session(
        self, pce_identifier: str, start_date: date, end_date: date, frequencies: list[Frequency] | None = None
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

    # ------------------------------------------------------
    def __init__(
        self,
        username: str,
        password: str,
        tmp_directory: str | None = None,
        *,
        tmpDirectory: str | None = None,  # noqa: N803
    ):

        super().__init__(username, password)

        if tmpDirectory is not None:
            warnings.warn(
                "The tmpDirectory parameter is deprecated. Please migrate to the tmp_directory parameter",
                DeprecationWarning,
                stacklevel=2,
            )
            tmp_directory = tmp_directory or tmpDirectory

        if tmp_directory is None:
            raise TypeError("ExcelWebDataSource needs a tmp_directory")

        self._tmp_directory = tmp_directory

    # ------------------------------------------------------
    def _load_from_session(
        self, pce_identifier: str, start_date: date, end_date: date, frequencies: list[Frequency] | None = None
    ) -> ReadingsByFrequency:

        res = {}

        if frequencies is None:
            # Transform Enum in List.
            frequency_list = list(Frequency)
        else:
            # Get distinct values.
            frequency_list = list(set(frequencies))

        for frequency in frequency_list:
            Logger.debug(
                f"Loading data of frequency {ExcelWebDataSource.FREQUENCY_VALUES[frequency]} from {start_date.strftime(ExcelWebDataSource.DATE_FORMAT)} to {end_date.strftime(ExcelWebDataSource.DATE_FORMAT)}"
            )

            response = self._api_client.get_pce_consumption_excelsheet(
                ConsumptionType.INFORMATIVE,
                start_date,
                end_date,
                APIClientFrequency(ExcelWebDataSource.FREQUENCY_VALUES[frequency]),
                [pce_identifier],
            )

            # The XLSX file lives in a private directory under the TMP directory: nothing else can collide with it, and
            # the directory is removed even when the parsing fails. openpyxl does not close the file properly, hence
            # ignore_cleanup_errors.
            with tempfile.TemporaryDirectory(dir=self._tmp_directory, ignore_cleanup_errors=True) as directory:
                data_file_path = os.path.join(directory, DEFAULT_EXCEL_FILENAME)
                with open(data_file_path, "wb") as file:
                    file.write(response.content)

                res[frequency.value] = ExcelParser.parse(
                    data_file_path, frequency if frequency != Frequency.YEARLY else Frequency.DAILY
                )

            # We compute yearly from daily data.
            if frequency == Frequency.YEARLY:
                res[frequency.value] = FrequencyConverter.compute_yearly(res[frequency.value])

        return res


# ------------------------------------------------------------------------------------------------------------
class ExcelFileDataSource(IDataSource):
    def __init__(self, excel_file: str):

        self._excel_file = excel_file

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
        pce_identifier: str,  # noqa: ARG002
        start_date: date,  # noqa: ARG002
        end_date: date,  # noqa: ARG002
        frequencies: list[Frequency] | None = None,
    ) -> ReadingsByFrequency:

        res = {}

        if frequencies is None:
            # Transform Enum in List.
            frequency_list = list(Frequency)
        else:
            # Get unique values.
            frequency_list = list(set(frequencies))

        for frequency in frequency_list:
            if frequency != Frequency.YEARLY:
                res[frequency.value] = ExcelParser.parse(self._excel_file, frequency)
            else:
                daily = ExcelParser.parse(self._excel_file, Frequency.DAILY)
                res[frequency.value] = FrequencyConverter.compute_yearly(daily)

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
        self._consumption_type = consumption_type

    # ------------------------------------------------------
    def _load_from_session(
        self, pce_identifier: str, start_date: date, end_date: date, frequencies: list[Frequency] | None = None
    ) -> ReadingsByFrequency:

        res = dict[str, Any]()

        compute_by_frequency = {
            Frequency.HOURLY: FrequencyConverter.compute_hourly,
            Frequency.DAILY: FrequencyConverter.compute_daily,
            Frequency.WEEKLY: FrequencyConverter.compute_weekly,
            Frequency.MONTHLY: FrequencyConverter.compute_monthly,
            Frequency.YEARLY: FrequencyConverter.compute_yearly,
        }

        data = self._api_client.get_pce_consumption(self._consumption_type, start_date, end_date, [pce_identifier])

        Logger.debug("Json meter data: %s", data)

        meteo_end_date, meteo_days = meteo_window(start_date, end_date)

        # Get weather data.
        try:
            temperatures = self._api_client.get_pce_meteo(meteo_end_date, meteo_days, pce_identifier)
        except Exception as error:  # noqa: BLE001
            # Not a blocking error: the readings are returned without temperatures.
            Logger.warning("The temperatures are not available, the readings have none: %s", error)
            temperatures = None

        Logger.debug("Json temperature data: %s", temperatures)

        if frequencies is None:
            # Transform Enum in List.
            frequency_list = list(Frequency)
        else:
            # Get unique values.
            frequency_list = list(set(frequencies))

        # Transform all the data into the target structure.
        if data is None or len(data) == 0:
            # No data: every requested frequency has an empty list of readings, as with data.
            return {frequency.value: [] for frequency in frequency_list}

        daily = JsonParser.readings(data, temperatures, pce_identifier)

        Logger.debug("Processed daily data: %s", daily)

        for frequency in frequency_list:
            res[frequency.value] = compute_by_frequency[frequency](daily)

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
        self._api_client = APIClient(username, password)
        self._consumption_type = consumption_type

    # ------------------------------------------------------
    def load(self, pce_identifier: str, start_date: date, end_date: date) -> dict[str, Any]:

        if not self._api_client.is_logged_in():
            self._api_client.login()

        return self._api_client.get_pce_consumption_raw(self._consumption_type, start_date, end_date, [pce_identifier])


# ------------------------------------------------------------------------------------------------------------
class RawTemperatureWebDataSource:
    """Returns the GrDF temperature (meteo) API response as received, without post processing.

    Not an IDataSource: load() returns the raw payload, not a MeterReadingsByFrequency.
    """

    # ------------------------------------------------------
    def __init__(self, username: str, password: str):

        self._api_client = APIClient(username, password)

    # ------------------------------------------------------
    def load(self, pce_identifier: str, start_date: date, end_date: date) -> dict[str, Any]:

        if not self._api_client.is_logged_in():
            self._api_client.login()

        meteo_end_date, meteo_days = meteo_window(start_date, end_date)

        return self._api_client.get_pce_meteo_raw(meteo_end_date, meteo_days, pce_identifier)


# ------------------------------------------------------------------------------------------------------------
class JsonFileDataSource(IDataSource):
    # ------------------------------------------------------
    def __init__(self, consumption_json_file: str, temperature_json_file):

        self._consumption_json_file = consumption_json_file
        self._temperature_json_file = temperature_json_file

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
        pce_identifier: str,
        start_date: date,  # noqa: ARG002
        end_date: date,  # noqa: ARG002
        frequencies: list[Frequency] | None = None,
    ) -> ReadingsByFrequency:

        res: ReadingsByFrequency = {}

        with open(self._consumption_json_file, encoding="utf-8") as consumption_json_file:
            with open(self._temperature_json_file, encoding="utf-8") as temperature_json_file:
                daily = JsonParser.readings_from_json(
                    consumption_json_file.read(), temperature_json_file.read(), pce_identifier
                )

        compute_by_frequency = {
            Frequency.HOURLY: FrequencyConverter.compute_hourly,
            Frequency.DAILY: FrequencyConverter.compute_daily,
            Frequency.WEEKLY: FrequencyConverter.compute_weekly,
            Frequency.MONTHLY: FrequencyConverter.compute_monthly,
            Frequency.YEARLY: FrequencyConverter.compute_yearly,
        }

        if frequencies is None:
            # Transform Enum in List.
            frequency_list = list(Frequency)
        else:
            # Get unique values.
            frequency_list = list(set(frequencies))

        for frequency in frequency_list:
            res[frequency.value] = compute_by_frequency[frequency](daily)

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
        pce_identifier: str,  # noqa: ARG002
        start_date: date,  # noqa: ARG002
        end_date: date,  # noqa: ARG002
        frequencies: list[Frequency] | None = None,
    ) -> ReadingsByFrequency:

        res = dict[str, Any]()

        data_sample_filename_by_frequency = {
            Frequency.HOURLY: "hourly_data_sample.json",
            Frequency.DAILY: "daily_data_sample.json",
            Frequency.WEEKLY: "weekly_data_sample.json",
            Frequency.MONTHLY: "monthly_data_sample.json",
            Frequency.YEARLY: "yearly_data_sample.json",
        }

        if frequencies is None:
            # Transform Enum in List.
            frequency_list = list(Frequency)
        else:
            # Get unique values.
            frequency_list = list(set(frequencies))

        for frequency in frequency_list:
            data_sample_filename = (
                f"{os.path.dirname(os.path.abspath(__file__))}/resources/{data_sample_filename_by_frequency[frequency]}"
            )

            with open(data_sample_filename, encoding="utf-8") as json_file:
                rows = cast(list[dict[str, Any]], json.load(json_file))
                res[frequency.value] = [] if frequency == Frequency.HOURLY else readings_from_samples(frequency, rows)

        return res


# ------------------------------------------------------------------------------------------------------------
class FrequencyConverter:
    MONTHS = MONTH_NAMES

    # ------------------------------------------------------
    @staticmethod
    def compute_hourly(daily: Sequence[PeriodReading]) -> list[PeriodReading]:  # noqa: ARG004

        return []

    # ------------------------------------------------------
    @staticmethod
    def compute_daily(daily: Sequence[PeriodReading]) -> list[PeriodReading]:

        return list(daily)

    # ------------------------------------------------------
    @staticmethod
    def compute_weekly(daily: Sequence[PeriodReading]) -> list[PeriodReading]:

        return FrequencyConverter._aggregate(
            daily, Frequency.WEEKLY, lambda day: day - timedelta(days=day.weekday()), minimum_days=7
        )

    # ------------------------------------------------------
    @staticmethod
    def compute_monthly(daily: Sequence[PeriodReading]) -> list[PeriodReading]:

        return FrequencyConverter._aggregate(daily, Frequency.MONTHLY, lambda day: day.replace(day=1), minimum_days=28)

    # ------------------------------------------------------
    @staticmethod
    def compute_yearly(daily: Sequence[PeriodReading]) -> list[PeriodReading]:

        return FrequencyConverter._aggregate(
            daily, Frequency.YEARLY, lambda day: day.replace(month=1, day=1), minimum_days=360
        )

    # ------------------------------------------------------
    @staticmethod
    def _aggregate(
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
                    end_date=FrequencyConverter._period_end(frequency, start),
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
    def _period_end(frequency: Frequency, start: date) -> date:
        """Returns the day after the last day of a period that starts on start."""

        if frequency == Frequency.WEEKLY:
            return start + timedelta(days=7)
        if frequency == Frequency.MONTHLY:
            return next_month_start(start)

        return date(start.year + 1, 1, 1)
