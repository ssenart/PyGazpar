import logging
import requests
import datetime
import json
from typing import Dict

DEFAULT_LAST_N_DAYS = 365


Logger = logging.getLogger(__name__)


# ------------------------------------------------------------------------------------------------------------
class ClientV2:

    # ------------------------------------------------------
    def __init__(self, username: str, password: str, pceIdentifier: str, lastNDays: int = DEFAULT_LAST_N_DAYS, testMode: bool = False):
        self.__username = username
        self.__password = password
        self.__pceIdentifier = pceIdentifier
        self.__lastNDays = lastNDays
        self.__testMode = testMode
        self.__data = {}

    # ------------------------------------------------------
    def data(self) -> Dict:
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

            session.headers.update(
                {
                    "User-Agent": "Mozilla/5.0"
                    " (Linux; Android 6.0; Nexus 5 Build/MRA58N)"
                    " AppleWebKit/537.36 (KHTML, like Gecko)"
                    " Chrome/61.0.3163.100 Mobile Safari/537.36",
                    "Accept-Encoding": "gzip, deflate, br",
                    "Accept": "application/json, */*",
                    "Connection": "keep-alive",
                    "domain": "grdf.fr",
                }
            )

            # Get auth_nonce cookie.
            _ = session.get("https://monespace.grdf.fr/client/particulier/accueil")
            if "auth_nonce" not in session.cookies:
                raise Exception("Cannot get auth_nonce.")
            auth_nonce = session.cookies.get("auth_nonce")

            # Login
            loginResponse = session.post('https://login.monespace.grdf.fr/sofit-account-api/api/v1/auth', data={
                'email': self.__username,
                'password': self.__password,
                'capp': 'meg',
                'goto': f"https://sofa-connexion.grdf.fr:443/openam/oauth2/externeGrdf/authorize?response_type=code&scope=openid%20profile%20email%20infotravaux%20%2Fv1%2Faccreditation%20%2Fv1%2Faccreditations%20%2Fdigiconso%2Fv1%20%2Fdigiconso%2Fv1%2Fconsommations%20new_meg&client_id=prod_espaceclient&state=0&redirect_uri=https%3A%2F%2Fmonespace.grdf.fr%2F_codexch&nonce={auth_nonce}&by_pass_okta=1&capp=meg"
            })

            # Check login result.
            loginData = json.loads(loginResponse.text)

            if "status" in loginData and "error" in loginData and loginData["status"] >= 400:
                raise Exception(f"{loginData['error']} ({loginData['status']})")

            if "state" in loginData and loginData["state"] != "SUCCESS":
                raise Exception(loginData["error"])

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
