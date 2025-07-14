import logging
import time
import traceback
from datetime import date
from enum import Enum
from typing import Any

from requests import Response, Session

import secrets
import hashlib
import base64
import re
import os

def create_pkce_pair():
    code_verifier = base64.urlsafe_b64encode(os.urandom(40)).rstrip(b'=').decode('utf-8')
    challenge = hashlib.sha256(code_verifier.encode('utf-8')).digest()
    code_challenge = base64.urlsafe_b64encode(challenge).rstrip(b'=').decode('utf-8')
    return code_verifier, code_challenge

MAIL_SESSION_TOKEN_URL = "https://connexion.grdf.fr/idp/idx/identify"
PASSWORD_SESSION_TOKEN_URL = "https://connexion.grdf.fr/idp/idx/challenge/answer"
CLIENT_ID_URL = "https://connexion.grdf.fr/assets/apps/enduser-v2.enduser/0.0.1-2445-g3242879/static/js/main.js"
AUTHORIZE_URL = "https://connexion.grdf.fr/oauth2/v1/authorize" 
TOKEN_URL = "https://connexion.grdf.fr/oauth2/v1/token"

MAIL_SESSION_TOKEN_PAYLOAD = """{{
    "identifier": "{0}",
    "stateHandle": "{1}"
}}"""

PASSWORD_SESSION_TOKEN_PAYLOAD = """{{
    "credentials": {{
        "passcode": "{0}"
    }},
    "stateHandle": "{1}"
}}"""

API_BASE_URL = "https://monespace.grdf.fr/api"

DATE_FORMAT = "%Y-%m-%d"

Logger = logging.getLogger(__name__)


# ------------------------------------------------------
class ConsumptionType(str, Enum):
    INFORMATIVE = "informatives"
    PUBLISHED = "publiees"


# ------------------------------------------------------
class Frequency(str, Enum):
    HOURLY = "Horaire"
    DAILY = "Journalier"
    WEEKLY = "Hebdomadaire"
    MONTHLY = "Mensuel"
    YEARLY = "Annuel"


# ------------------------------------------------------
class ServerError(SystemError):

    def __init__(self, message: str, status_code: int):
        super().__init__(message)
        self.status_code = status_code


# ------------------------------------------------------
class InternalServerError(ServerError):

    def __init__(self, message: str):
        super().__init__(message, 500)


# ------------------------------------------------------
class APIClient:

    # ------------------------------------------------------
    def __init__(self, username: str, password: str, retry_count: int = 10):
        self._username = username
        self._password = password
        self._retry_count = retry_count
        self._session = None

    # ------------------------------------------------------
    def login(self):
        if self._session is not None:
            return

        code_verifier, code_challenge = create_pkce_pair()

        self._session = Session()
        self._session.headers.update({"Content-Type": "application/ion+json"})
        self._session.headers.update({"Accept": "application/ion+json; okta-version=1.0.0"})
        self._session.headers.update({
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)",
            "Referer": "https://connexion.grdf.fr/",
            "Accept-Language": "fr-FR,fr;q=0.9"
        })

        url_client_id_response = self._session.get(CLIENT_ID_URL)
        if url_client_id_response.status_code != 200:
            raise ServerError(
                f"An error occurred while logging in start. Status code: {url_client_id_response.status_code} - {url_client_id_response.url}",
                url_client_id_response.status_code,
            )
        client_id = "okta." + url_client_id_response.text.split(",Kt=\"okta.")[1].split("\"")[0]

        params = {
            "client_id": client_id,
            "code_challenge": code_challenge,
            "code_challenge_method": "S256",
            "nonce": secrets.token_urlsafe(48),
            "redirect_uri": "https://connexion.grdf.fr/enduser/callback",
            "response_type": "code",
            "state": secrets.token_urlsafe(48),
            "scope": "openid profile email okta.users.read.self okta.users.manage.self okta.internal.enduser.read okta.internal.enduser.manage okta.enduser.dashboard.read okta.enduser.dashboard.manage okta.myAccount.sessions.manage"
        }

        start_response = self._session.get(AUTHORIZE_URL, params=params)
        if start_response.status_code != 200:
            raise ServerError(
                f"An error occurred while logging in start. Status code: {start_response.status_code} - {start_response.url}",
                start_response.status_code,
            )

        pattern = r'"stateToken"\s*:\s*"([^"]+)"'
        match = re.search(pattern, start_response.text)
        if match:
            state_token_html = match.group(1)
            state_token = state_token_html.replace("\\x2D", "-")
        else:
            raise ValueError("Impossible de trouver le stateToken dans la réponse HTML")

        payload = MAIL_SESSION_TOKEN_PAYLOAD.format(self._username, state_token)
        self._session.cookies.set("ln", self._username)

        mail_response = self._session.post(MAIL_SESSION_TOKEN_URL, data=payload)

        if mail_response.status_code != 200:
            raise ServerError(
                f"An error occurred while logging in mail. Status code: {mail_response.status_code} - {mail_response.text}",
                mail_response.status_code,
            )

        stateHandle = mail_response.json().get("stateHandle")
        payload = PASSWORD_SESSION_TOKEN_PAYLOAD.format(self._password, stateHandle)

        password_response = self._session.post(PASSWORD_SESSION_TOKEN_URL, data=payload)

        if password_response.status_code != 200:
            raise ServerError(
                f"An error occurred while logging in password. Status code: {password_response.status_code} - {password_response.text}",
                password_response.status_code,
            )

        success_url = password_response.json()['success']['href']

        response_redirect = self._session.get(success_url)

        if response_redirect.status_code != 200:
            raise ServerError(
                f"An error occurred while logging in response_redirect. Status code: {response_redirect.status_code} - {response_redirect.url}",
                response_redirect.status_code,
            )

        code = response_redirect.url.split("code=")[1].split("&")[0]

        params = {
            "client_id": client_id,
            "redirect_uri": "https://connexion.grdf.fr/enduser/callback",
            "grant_type": "authorization_code",
            "code" : code,
            "code_verifier" : code_verifier
        }
        self._session.headers.update({"Content-Type": "application/x-www-form-urlencoded"})
        self._session.headers.update({"Accept": "application/json"})
        token_response = self._session.post(TOKEN_URL, params=params)
        if token_response.status_code != 200:
            raise ServerError(
                f"An error occurred while logging in token_response. Status code: {token_response.status_code} - {token_response.url} - {token_response.text}",
                token_response.status_code,
            )

    # ------------------------------------------------------
    def is_logged_in(self) -> bool:
        return self._session is not None

    # ------------------------------------------------------
    def logout(self):
        if self._session is None:
            return

        self._session.close()
        self._session = None

    # ------------------------------------------------------
    def get(self, endpoint: str, params: dict[str, Any]) -> Response:

        if self._session is None:
            raise ConnectionError("You must login first")

        retry = self._retry_count
        while retry > 0:

            try:
                response = self._session.get(f"{API_BASE_URL}{endpoint}", params=params)

                if "text/html" in response.headers.get("Content-Type"):  # type: ignore
                    raise InternalServerError(
                        f"An unknown error occurred. Please check your query parameters (endpoint: {endpoint}): {params}"
                    )

                if response.status_code != 200:
                    raise ServerError(
                        f"HTTP error on enpoint '{endpoint}': Status code: {response.status_code} - {response.text}. Query parameters: {params}",
                        response.status_code,
                    )

                break
            except InternalServerError as internalServerError:  # pylint: disable=broad-exception-caught
                if retry == 1:
                    Logger.error(f"{internalServerError}. Retry limit reached: {traceback.format_exc()}")
                    raise internalServerError
                retry -= 1
                Logger.warning(f"{internalServerError}. Retry in 3 seconds ({retry} retries left)...")
                time.sleep(3)

        return response

    # ------------------------------------------------------
    def get_pce_list(self, details: bool = False) -> list[Any]:

        res = self.get("/e-conso/pce", {"details": details}).json()

        if type(res) is not list:
            raise TypeError(f"Invalid response type: {type(res)} (list expected)")

        return res

    # ------------------------------------------------------
    def get_pce_consumption(
        self, consumption_type: ConsumptionType, start_date: date, end_date: date, pce_list: list[str]
    ) -> dict[str, Any]:

        start = start_date.strftime(DATE_FORMAT)
        end = end_date.strftime(DATE_FORMAT)

        res = self.get(
            f"/e-conso/pce/consommation/{consumption_type.value}",
            {"dateDebut": start, "dateFin": end, "pceList[]": ",".join(pce_list)},
        ).json()

        if type(res) is list and len(res) == 0:
            return dict[str, Any]()

        if type(res) is not dict:
            raise TypeError(f"Invalid response type: {type(res)} (dict expected)")

        return res

    # ------------------------------------------------------
    def get_pce_consumption_excelsheet(
        self,
        consumption_type: ConsumptionType,
        start_date: date,
        end_date: date,
        frequency: Frequency,
        pce_list: list[str],
    ) -> dict[str, Any]:

        start = start_date.strftime(DATE_FORMAT)
        end = end_date.strftime(DATE_FORMAT)

        response = self.get(
            f"/e-conso/pce/consommation/{consumption_type.value}/telecharger",
            {"dateDebut": start, "dateFin": end, "frequence": frequency.value, "pceList[]": ",".join(pce_list)},
        )

        filename = response.headers["Content-Disposition"].split("filename=")[1]

        res = {"filename": filename, "content": response.content}

        return res

    # ------------------------------------------------------
    def get_pce_meteo(self, end_date: date, days: int, pce: str) -> dict[str, Any]:

        end = end_date.strftime(DATE_FORMAT)

        res = self.get(f"/e-conso/pce/{pce}/meteo", {"dateFinPeriode": end, "nbJours": days}).json()

        if type(res) is list and len(res) == 0:
            return dict[str, Any]()

        if type(res) is not dict:
            raise TypeError(f"Invalid response type: {type(res)} (dict expected)")

        return res
