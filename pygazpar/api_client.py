import json
import logging
import os
import re
import time
from datetime import date
from decimal import Decimal
from enum import Enum
from typing import Any

from requests import Response, Session
from requests.exceptions import ConnectionError as RequestsConnectionError
from requests.exceptions import Timeout

from pygazpar.grdf import (
    GrdfConsumptionResponse,
    GrdfExcelSheet,
    GrdfMeteoResponse,
    GrdfPce,
    GrdfPceConsumption,
    GrdfPceList,
)

START_URL = "https://monespace.grdf.fr/"

MAIL_SESSION_TOKEN_URL = "https://connexion.grdf.fr/idp/idx/identify"

PASSWORD_SESSION_TOKEN_URL = "https://connexion.grdf.fr/idp/idx/challenge/answer"

API_BASE_URL = "https://monespace.grdf.fr/api"

DATE_FORMAT = "%Y-%m-%d"

# (connect, read) timeouts in seconds: without them a stalled GrDF connection hangs the caller forever.
REQUEST_TIMEOUT = (10, 60)

# The delay before a retry starts here and doubles at each attempt, up to MAX_RETRY_DELAY_SECONDS.
RETRY_DELAY_SECONDS = 3

MAX_RETRY_DELAY_SECONDS = 15

MAX_RETRY_AFTER_SECONDS = 60

HTTP_TOO_MANY_REQUESTS = 429

DEFAULT_EXCEL_FILENAME = "Donnees_informatives.xlsx"

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
def excel_filename(content_disposition: str | None) -> str:
    """Returns the file name of a Content-Disposition header, without any directory part.

    The name comes from the server: it is cut down to its base name before anyone uses it as a path.
    """

    match = re.search(r'filename\*?=(?:UTF-8\'\')?"?([^";]+)"?', content_disposition or "")
    filename = os.path.basename(match.group(1).strip().replace("\\", "/")) if match else ""

    return filename if filename not in ("", ".", "..") else DEFAULT_EXCEL_FILENAME


# ------------------------------------------------------
class APIClient:
    # ------------------------------------------------------
    def __init__(self, username: str, password: str, retry_count: int = 10):
        self._username = username
        self._password = password
        self._retry_count = retry_count
        self._session: Session | None = None

    # ------------------------------------------------------
    def login(self):
        if self._session is not None:
            return

        session = Session()
        session.headers.update({"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"})

        start_response = session.get(START_URL, timeout=REQUEST_TIMEOUT)
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
            raise ValueError("Cannot retrieve stateToken inside HTML response")

        payload = json.dumps({"identifier": self._username, "stateHandle": state_token})
        session.cookies.set("ln", self._username)

        mail_response = session.post(
            MAIL_SESSION_TOKEN_URL,
            data=payload,
            headers={"Accept": "application/json; okta-version=1.0.0", "Content-Type": "application/json"},
            timeout=REQUEST_TIMEOUT,
        )

        if mail_response.status_code != 200:
            raise ServerError(
                f"An error occurred while logging in mail. Status code: {mail_response.status_code} - {mail_response.text}",
                mail_response.status_code,
            )

        state_handle = mail_response.json().get("stateHandle")

        payload = json.dumps({"credentials": {"passcode": self._password}, "stateHandle": state_handle})

        password_response = session.post(
            PASSWORD_SESSION_TOKEN_URL,
            data=payload,
            headers={"Accept": "application/json; okta-version=1.0.0", "Content-Type": "application/json"},
            timeout=REQUEST_TIMEOUT,
        )

        if password_response.status_code != 200:
            raise ServerError(
                f"An error occurred while logging in password. Status code: {password_response.status_code} - {password_response.text}",
                password_response.status_code,
            )

        success_url = password_response.json()["success"]["href"]

        response_redirect = session.get(success_url, timeout=REQUEST_TIMEOUT)

        if response_redirect.status_code != 200:
            raise ServerError(
                f"An error occurred while logging in response_redirect. Status code: {response_redirect.status_code} - {response_redirect.url}",
                response_redirect.status_code,
            )

        self._session = session

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
    @staticmethod
    def _is_session_expired(response: Response) -> bool:
        """Tells whether GrDF refused the session: a 401, or a redirection from the API to a login page."""

        if response.status_code == 401:
            return True

        is_html = "text/html" in (response.headers.get("Content-Type") or "")

        return is_html and not response.url.startswith(API_BASE_URL)

    # ------------------------------------------------------
    @staticmethod
    def _backoff_delay(attempt: int) -> float:
        """Returns the seconds to wait after a failed attempt: 3, 6, 12, then 15 seconds at most."""

        return min(RETRY_DELAY_SECONDS * 2 ** (attempt - 1), MAX_RETRY_DELAY_SECONDS)

    # ------------------------------------------------------
    @staticmethod
    def _wait_before_retry(error: Exception, attempt: int, attempts: int, delay: float | None = None) -> None:
        """Waits before the next attempt, or raises the error when the retry limit is reached.

        The delay grows with the attempt number, unless the caller gives one.
        """

        if attempt == attempts:
            Logger.error(f"{error}. Retry limit reached.", exc_info=error)
            raise error

        if delay is None:
            delay = APIClient._backoff_delay(attempt)

        Logger.warning(f"{error}. Retry in {delay:g} seconds ({attempts - attempt} retries left)...")
        time.sleep(delay)

    # ------------------------------------------------------
    @staticmethod
    def _retry_after(response: Response) -> float | None:
        """Returns the seconds GrDF asks to wait in its Retry-After header, or None when it gives no number of seconds."""

        try:
            seconds = float(response.headers.get("Retry-After", ""))
        except ValueError:
            return None

        return min(max(seconds, 0), MAX_RETRY_AFTER_SECONDS)

    # ------------------------------------------------------
    def get(self, endpoint: str, params: dict[str, Any]) -> Response:
        """Calls an endpoint of the API.

        The call is retried on network errors and on the HTML answers GrDF sends instead of an error. When the session
        has expired, the client logs in again, once, and repeats the call.
        """

        if self._session is None:
            raise ConnectionError("You must login first")

        attempts = max(self._retry_count, 1)
        logged_in_again = False
        attempt = 1
        while True:
            session = self._session
            if session is None:
                raise ConnectionError("You must login first")

            try:
                response = session.get(f"{API_BASE_URL}{endpoint}", params=params, timeout=REQUEST_TIMEOUT)
            except (RequestsConnectionError, Timeout) as networkError:
                self._wait_before_retry(networkError, attempt, attempts)
                attempt += 1
                continue

            if self._is_session_expired(response):
                if logged_in_again:
                    raise ServerError(f"The session expired again right after logging in (endpoint: {endpoint})", 401)
                Logger.warning("The session has expired. Logging in again...")
                logged_in_again = True
                self.logout()
                self.login()
                continue

            if response.status_code == HTTP_TOO_MANY_REQUESTS:
                # GrDF throttles the calls sent back to back, with an HTML body: it is not an unknown error.
                self._wait_before_retry(
                    ServerError(
                        f"GrDF is limiting the request rate (endpoint: {endpoint}): {params}", HTTP_TOO_MANY_REQUESTS
                    ),
                    attempt,
                    attempts,
                    self._retry_after(response),
                )
                attempt += 1
                continue

            if "text/html" in (response.headers.get("Content-Type") or ""):
                self._wait_before_retry(
                    InternalServerError(
                        f"An unknown error occurred. Please check your query parameters (endpoint: {endpoint}): {params}"
                    ),
                    attempt,
                    attempts,
                )
                attempt += 1
                continue

            if response.status_code != 200:
                raise ServerError(
                    f"HTTP error on enpoint '{endpoint}': Status code: {response.status_code} - {response.text}. Query parameters: {params}",
                    response.status_code,
                )

            return response

    # ------------------------------------------------------
    def get_pce_list(self, details: bool = False) -> list[GrdfPce]:
        """Returns the PCE list of the account."""

        res = self.get("/e-conso/pce", {"details": details}).json(parse_float=Decimal)

        return GrdfPceList.model_validate(res).root

    # ------------------------------------------------------
    def _consumption_json(
        self,
        consumption_type: ConsumptionType,
        start_date: date,
        end_date: date,
        pce_list: list[str],
        parse_float: Any,
    ) -> Any:

        start = start_date.strftime(DATE_FORMAT)
        end = end_date.strftime(DATE_FORMAT)

        return self.get(
            f"/e-conso/pce/consommation/{consumption_type.value}",
            {"dateDebut": start, "dateFin": end, "pceList[]": ",".join(pce_list)},
        ).json(parse_float=parse_float)

    # ------------------------------------------------------
    def get_pce_consumption_raw(
        self, consumption_type: ConsumptionType, start_date: date, end_date: date, pce_list: list[str]
    ) -> dict[str, Any]:
        """Returns the consumption response as the API sent it, once checked against its shape."""

        res = self._consumption_json(consumption_type, start_date, end_date, pce_list, None)

        if type(res) is list and len(res) == 0:
            return dict[str, Any]()

        GrdfConsumptionResponse.model_validate(res)

        return res

    # ------------------------------------------------------
    def get_pce_consumption(
        self, consumption_type: ConsumptionType, start_date: date, end_date: date, pce_list: list[str]
    ) -> dict[str, GrdfPceConsumption]:
        """Returns the consumption of each PCE, keyed by PCE identifier. Its records are validated by the parser."""

        res = self._consumption_json(consumption_type, start_date, end_date, pce_list, Decimal)

        if type(res) is list and len(res) == 0:
            return {}

        return GrdfConsumptionResponse.model_validate(res).root

    # ------------------------------------------------------
    def get_pce_consumption_excelsheet(
        self,
        consumption_type: ConsumptionType,
        start_date: date,
        end_date: date,
        frequency: Frequency,
        pce_list: list[str],
    ) -> GrdfExcelSheet:

        start = start_date.strftime(DATE_FORMAT)
        end = end_date.strftime(DATE_FORMAT)

        response = self.get(
            f"/e-conso/pce/consommation/{consumption_type.value}/telecharger",
            {"dateDebut": start, "dateFin": end, "frequence": frequency.value, "pceList[]": ",".join(pce_list)},
        )

        filename = excel_filename(response.headers.get("Content-Disposition"))

        return GrdfExcelSheet(filename=filename, content=response.content)

    # ------------------------------------------------------
    def _meteo_json(self, end_date: date, days: int, pce: str) -> Any:

        end = end_date.strftime(DATE_FORMAT)

        return self.get(f"/e-conso/pce/{pce}/meteo", {"dateFinPeriode": end, "nbJours": days}).json()

    # ------------------------------------------------------
    def get_pce_meteo_raw(self, end_date: date, days: int, pce: str) -> dict[str, Any]:
        """Returns the meteo response as the API sent it, once checked against its shape."""

        res = self._meteo_json(end_date, days, pce)

        if type(res) is list and len(res) == 0:
            return dict[str, Any]()

        GrdfMeteoResponse.model_validate(res)

        return res

    # ------------------------------------------------------
    def get_pce_meteo(self, end_date: date, days: int, pce: str) -> dict[date, float | None]:
        """Returns the temperature of each day, keyed by date."""

        res = self._meteo_json(end_date, days, pce)

        if type(res) is list and len(res) == 0:
            return {}

        return GrdfMeteoResponse.model_validate(res).root
