import logging
import requests
import datetime

DEFAULT_LAST_N_DAYS = 365


Logger = logging.getLogger(__name__)


# ------------------------------------------------------------------------------------------------------------
class ClientV2:

    # ------------------------------------------------------
    def __init__(self, username: str, password: str, pceIdentifier: int, lastNDays: int = DEFAULT_LAST_N_DAYS, testMode: bool = False):
        self.__username = username
        self.__password = password
        self.__pceIdentifier = pceIdentifier
        self.__lastNDays = lastNDays
        self.__testMode = testMode
        self.__data = {}

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
        pass

    # ------------------------------------------------------
    def __updateLiveMode(self):

        try:
            Logger.debug("Start updating the data...")

            session = requests.Session()

            # Login
            session.post('https://login.monespace.grdf.fr/sofit-account-api/api/v1/auth', data={
                'email': self.__username,
                'password': self.__password,
                'capp': 'meg',
                'goto': 'https://sofa-connexion.grdf.fr:443/openam/oauth2/externeGrdf/authorize?response_type=code&scope=openid%20profile%20email%20infotravaux%20%2Fv1%2Faccreditation%20%2Fv1%2Faccreditations%20%2Fdigiconso%2Fv1%20%2Fdigiconso%2Fv1%2Fconsommations%20new_meg&client_id=prod_espaceclient&state=0&redirect_uri=https%3A%2F%2Fmonespace.grdf.fr%2F_codexch&nonce=skywsNPCVa-AeKo1Rps0HjMVRNbUqA46j7XYA4tImeI&by_pass_okta=1&capp=meg'
            })

            # Build URL to get the data from.
            dateFormat = "%Y-%m-%d"
            endDate = datetime.date.today()
            startDate = endDate + datetime.timedelta(days=-self.__lastNDays)

            url = f"https://monespace.grdf.fr/api/e-conso/pce/consommation/informatives?dateDebut={startDate.strftime(dateFormat)}&dateFin={endDate.strftime(dateFormat)}&pceList%5B%5D={self.__pceIdentifier}"

            # First request never returns data.
            session.get(url)

            # Get data
            response = session.get(url).json()
            self.__data = response[self.__pceIdentifier]['releves']

            Logger.debug("The data update terminates normally")
        except Exception:
            Logger.error("An unexpected error occured while updating the data", exc_info=True)
