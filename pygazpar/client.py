import logging
from datetime import date, timedelta
from pygazpar.enum import Frequency
from pygazpar.datasource import IDataSource
from typing import Any, List, Dict

AUTH_NONCE_URL = "https://monespace.grdf.fr/client/particulier/accueil"
LOGIN_URL = "https://login.monespace.grdf.fr/sofit-account-api/api/v1/auth"
LOGIN_HEADER = {"domain": "grdf.fr"}
LOGIN_PAYLOAD = """{{
    "email": "{0}",
    "password": "{1}",
    "capp": "meg",
    "goto": "https://sofa-connexion.grdf.fr:443/openam/oauth2/externeGrdf/authorize?response_type=code&scope=openid%20profile%20email%20infotravaux%20%2Fv1%2Faccreditation%20%2Fv1%2Faccreditations%20%2Fdigiconso%2Fv1%20%2Fdigiconso%2Fv1%2Fconsommations%20new_meg&client_id=prod_espaceclient&state=0&redirect_uri=https%3A%2F%2Fmonespace.grdf.fr%2F_codexch&nonce={2}&by_pass_okta=1&capp=meg"}}"""
DATA_URL = "https://monespace.grdf.fr/api/e-conso/pce/consommation/informatives/telecharger?dateDebut={1}&dateFin={2}&frequence={0}&pceList%5B%5D={3}"
DATA_FILENAME = 'Donnees_informatives_*.xlsx'

DEFAULT_TMP_DIRECTORY = '/tmp'
DEFAULT_METER_READING_FREQUENCY = Frequency.DAILY
DEFAULT_LAST_N_DAYS = 365


Logger = logging.getLogger(__name__)


# ------------------------------------------------------------------------------------------------------------
class Client:

    # ------------------------------------------------------
    def __init__(self, dataSource: IDataSource):
        self.__dataSource = dataSource

    # ------------------------------------------------------
    def loadSince(self, pceIdentifier: str, lastNDays: int = DEFAULT_LAST_N_DAYS, meterReadingFrequency: Frequency = DEFAULT_METER_READING_FREQUENCY) -> List[Dict[str, Any]]:

        try:
            endDate = date.today()
            startDate = endDate + timedelta(days=-lastNDays)

            res = self.loadDateRange(pceIdentifier, startDate, endDate, meterReadingFrequency)
        except Exception:
            Logger.error("An unexpected error occured while loading the data", exc_info=True)
            raise

        return res

    # ------------------------------------------------------
    def loadDateRange(self, pceIdentifier: str, startDate: date, endDate: date, meterReadingFrequency: Frequency = DEFAULT_METER_READING_FREQUENCY) -> List[Dict[str, Any]]:

        Logger.debug("Start loading the data...")

        try:
            res = self.__dataSource.load(pceIdentifier, startDate, endDate, meterReadingFrequency)

            Logger.debug("The data load terminates normally")
        except Exception:
            Logger.error("An unexpected error occured while loading the data", exc_info=True)
            raise

        return res
