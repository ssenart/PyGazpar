import http.cookiejar
import json
import logging
import time
import traceback
from datetime import date
from enum import Enum
from typing import Any

from requests import Response, Session

SESSION_TOKEN_URL = "https://connexion.grdf.fr/api/v1/authn"
SESSION_TOKEN_PAYLOAD = """{{
    "username": "{0}",
    "password": "{1}",
    "options": {{
        "multiOptionalFactorEnroll": "false",
        "warnBeforePasswordExpired": "false"
    }}
}}"""

AUTH_TOKEN_URL = "https://connexion.grdf.fr/login/sessionCookieRedirect"
AUTH_TOKEN_PARAMS = """{{
    "checkAccountSetupComplete": "true",
    "token": "{0}",
    "redirectUrl": "https://monespace.grdf.fr"
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

        session = Session()
        session.headers.update({"domain": "grdf.fr"})
        session.headers.update({"Content-Type": "application/json"})
        session.headers.update({"X-Requested-With": "XMLHttpRequest"})

        payload = SESSION_TOKEN_PAYLOAD.format(self._username, self._password)

        response = session.post(SESSION_TOKEN_URL, data=payload)

        if response.status_code != 200:
            raise ValueError(
                f"An error occurred while logging in. Status code: {response.status_code} - {response.text}"
            )

        session_token = response.json().get("sessionToken")

        jar = http.cookiejar.CookieJar()

        self._session = Session()  # pylint: disable=attribute-defined-outside-init
        self._session.headers.update({"Content-Type": "application/json"})
        self._session.headers.update({"X-Requested-With": "XMLHttpRequest"})

        params = json.loads(AUTH_TOKEN_PARAMS.format(session_token))

        response = self._session.get(AUTH_TOKEN_URL, params=params, allow_redirects=True, cookies=jar)  # type: ignore

        if response.status_code != 200:
            raise ValueError(
                f"An error occurred while getting the auth token. Status code: {response.status_code} - {response.text}"
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
            raise ValueError("You must login first.")

        retry = self._retry_count
        while retry > 0:

            try:
                response = self._session.get(f"{API_BASE_URL}{endpoint}", params=params)

                if "text/html" in response.headers.get("Content-Type"):  # type: ignore
                    raise ValueError(
                        f"An unknown error occurred. Please check your query parameters (endpoint: {endpoint}): {params}"
                    )

                if response.status_code != 200:
                    raise ValueError(
                        f"HTTP error on enpoint '{endpoint}': Status code: {response.status_code} - {response.text}. Query parameters: {params}"
                    )

                break
            except Exception as e:  # pylint: disable=broad-exception-caught
                if retry == 1:
                    Logger.error(f"{e}. Retry limit reached: {traceback.format_exc()}")
                    raise e
                retry -= 1
                Logger.warning(f"{e}. Retry in 3 seconds ({retry} retries left)...")
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
