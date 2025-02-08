import logging
from datetime import date, timedelta
from typing import List, Optional

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
    def loadSince(
        self, pceIdentifier: str, lastNDays: int = DEFAULT_LAST_N_DAYS, frequencies: Optional[List[Frequency]] = None
    ) -> MeterReadingsByFrequency:

        try:
            endDate = date.today()
            startDate = endDate + timedelta(days=-lastNDays)

            res = self.loadDateRange(pceIdentifier, startDate, endDate, frequencies)
        except Exception:
            Logger.error("An unexpected error occured while loading the data", exc_info=True)
            raise

        return res

    # ------------------------------------------------------
    def loadDateRange(
        self, pceIdentifier: str, startDate: date, endDate: date, frequencies: Optional[List[Frequency]] = None
    ) -> MeterReadingsByFrequency:

        Logger.debug("Start loading the data...")

        try:
            res = self.__dataSource.load(pceIdentifier, startDate, endDate, frequencies)

            Logger.debug("The data load terminates normally")
        except Exception:
            Logger.error("An unexpected error occured while loading the data", exc_info=True)
            raise

        return res
