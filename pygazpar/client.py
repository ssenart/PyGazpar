import logging
import warnings
from datetime import date, timedelta
from typing import Optional

from pygazpar.datasource import IDataSource, MeterReadingsByFrequency
from pygazpar.enum import Frequency

DEFAULT_LAST_N_DAYS = 365


Logger = logging.getLogger(__name__)


# ------------------------------------------------------------------------------------------------------------
class Client:

    # ------------------------------------------------------
    def __init__(self, dataSource: IDataSource):
        self.__dataSource = dataSource

    # ------------------------------------------------------
    def login(self):

        try:
            self.__dataSource.login()
        except Exception:
            Logger.error("An unexpected error occured while login", exc_info=True)
            raise

    # ------------------------------------------------------
    def logout(self):

        try:
            self.__dataSource.logout()
        except Exception:
            Logger.error("An unexpected error occured while logout", exc_info=True)
            raise

    # ------------------------------------------------------
    def get_pce_identifiers(self) -> list[str]:

        try:
            res = self.__dataSource.get_pce_identifiers()
        except Exception:
            Logger.error("An unexpected error occured while getting the PCE identifiers", exc_info=True)
            raise

        return res

    # ------------------------------------------------------
    def load_since(
        self, pce_identifier: str, last_n_days: int = DEFAULT_LAST_N_DAYS, frequencies: Optional[list[Frequency]] = None
    ) -> MeterReadingsByFrequency:

        end_date = date.today()
        start_date = end_date + timedelta(days=-last_n_days)

        res = self.load_date_range(pce_identifier, start_date, end_date, frequencies)

        return res

    # ------------------------------------------------------
    def load_date_range(
        self, pce_identifier: str, start_date: date, end_date: date, frequencies: Optional[list[Frequency]] = None
    ) -> MeterReadingsByFrequency:

        Logger.debug("Start loading the data...")

        try:
            res = self.__dataSource.load(pce_identifier, start_date, end_date, frequencies)

            Logger.debug("The data load terminates normally")
        except Exception:
            Logger.error("An unexpected error occured while loading the data", exc_info=True)
            raise

        return res

    # ------------------------------------------------------
    def loadSince(
        self, pceIdentifier: str, lastNDays: int = DEFAULT_LAST_N_DAYS, frequencies: Optional[list[Frequency]] = None
    ) -> MeterReadingsByFrequency:
        warnings.warn(
            "Client.loadSince() method will be removed in 2026-01-01. Please migrate to Client.load_since() method",
            DeprecationWarning,
        )
        return self.load_since(pceIdentifier, lastNDays, frequencies)

    # ------------------------------------------------------
    def loadDateRange(
        self, pceIdentifier: str, startDate: date, endDate: date, frequencies: Optional[list[Frequency]] = None
    ) -> MeterReadingsByFrequency:
        warnings.warn(
            "Client.loadDateRange() method will be removed in 2026-01-01. Please migrate to Client.load_date_range() method",
            DeprecationWarning,
        )
        return self.load_date_range(pceIdentifier, startDate, endDate, frequencies)
