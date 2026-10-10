import logging
from datetime import date, timedelta

from pygazpar.datasource import (
    IDataSource,
    MeterReadingsByFrequency,
    ReadingsByFrequency,
)
from pygazpar.model import Frequency

DEFAULT_LAST_N_DAYS = 365


Logger = logging.getLogger(__name__)


# ------------------------------------------------------------------------------------------------------------
class Client:
    # ------------------------------------------------------
    def __init__(self, data_source: IDataSource):
        self._data_source = data_source

    # ------------------------------------------------------
    def __enter__(self) -> "Client":
        """Logs in, so that a with block logs out whatever happens: with Client(data_source) as client:"""

        self.login()

        return self

    # ------------------------------------------------------
    def __exit__(self, exc_type: object, exc_value: object, traceback: object) -> None:

        self.logout()

    # ------------------------------------------------------
    def login(self) -> None:

        try:
            self._data_source.login()
        except Exception:
            Logger.error("An unexpected error occured while login", exc_info=True)
            raise

    # ------------------------------------------------------
    def logout(self) -> None:

        try:
            self._data_source.logout()
        except Exception:
            Logger.error("An unexpected error occured while logout", exc_info=True)
            raise

    # ------------------------------------------------------
    def get_pce_identifiers(self) -> list[str]:

        try:
            res = self._data_source.get_pce_identifiers()
        except Exception:
            Logger.error("An unexpected error occured while getting the PCE identifiers", exc_info=True)
            raise

        return res

    # ------------------------------------------------------
    def load_since(
        self, pce_identifier: str, last_n_days: int = DEFAULT_LAST_N_DAYS, frequencies: list[Frequency] | None = None
    ) -> MeterReadingsByFrequency:

        end_date = date.today()
        start_date = end_date + timedelta(days=-last_n_days)

        return self.load_date_range(pce_identifier, start_date, end_date, frequencies)

    # ------------------------------------------------------
    def load_date_range(
        self, pce_identifier: str, start_date: date, end_date: date, frequencies: list[Frequency] | None = None
    ) -> MeterReadingsByFrequency:

        Logger.debug("Start loading the data...")

        try:
            res = self._data_source.load(pce_identifier, start_date, end_date, frequencies)

            Logger.debug("The data load terminates normally")
        except Exception:
            Logger.error("An unexpected error occured while loading the data", exc_info=True)
            raise

        return res

    # ------------------------------------------------------
    def load_readings_since(
        self, pce_identifier: str, last_n_days: int = DEFAULT_LAST_N_DAYS, frequencies: list[Frequency] | None = None
    ) -> ReadingsByFrequency:
        """Returns the readings of the last N days as models: the typed form of load_since()."""

        end_date = date.today()
        start_date = end_date + timedelta(days=-last_n_days)

        return self.load_readings_date_range(pce_identifier, start_date, end_date, frequencies)

    # ------------------------------------------------------
    def load_readings_date_range(
        self, pce_identifier: str, start_date: date, end_date: date, frequencies: list[Frequency] | None = None
    ) -> ReadingsByFrequency:
        """Returns the readings of a date range as models: the typed form of load_date_range()."""

        Logger.debug("Start loading the readings...")

        try:
            res = self._data_source.readings(pce_identifier, start_date, end_date, frequencies)

            Logger.debug("The readings load terminates normally")
        except Exception:
            Logger.error("An unexpected error occured while loading the readings", exc_info=True)
            raise

        return res
