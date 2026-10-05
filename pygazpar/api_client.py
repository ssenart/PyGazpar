import json
import logging
import re
import time
import traceback
from datetime import date
from decimal import Decimal
from enum import Enum
from typing import Any

from requests import Response, Session

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
        self._session: Session | None = None

    # ------------------------------------------------------
    def login(self):
        if self._session is not None:
            return

        session = Session()
        session.headers.update({"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"})

        start_response = session.get(START_URL)
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
        )

        if password_response.status_code != 200:
            raise ServerError(
                f"An error occurred while logging in password. Status code: {password_response.status_code} - {password_response.text}",
                password_response.status_code,
            )

        success_url = password_response.json()["success"]["href"]

        response_redirect = session.get(success_url)

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
            except InternalServerError as internalServerError:
                if retry == 1:
                    Logger.error(f"{internalServerError}. Retry limit reached: {traceback.format_exc()}")
                    raise internalServerError
                retry -= 1
                Logger.warning(f"{internalServerError}. Retry in 3 seconds ({retry} retries left)...")
                time.sleep(3)

        return response

    # ------------------------------------------------------
    def get_pce_list(self, details: bool = False) -> list[GrdfPce]:
        """Returns the PCE list of the account."""

        res = self.get("/e-conso/pce", {"details": details}).json(parse_float=Decimal)

        return GrdfPceList.model_validate(res).root

    # ------------------------------------------------------
    def __consumption_json(
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

        res = self.__consumption_json(consumption_type, start_date, end_date, pce_list, None)

        if type(res) is list and len(res) == 0:
            return dict[str, Any]()

        GrdfConsumptionResponse.model_validate(res)

        return res

    # ------------------------------------------------------
    def get_pce_consumption(
        self, consumption_type: ConsumptionType, start_date: date, end_date: date, pce_list: list[str]
    ) -> dict[str, GrdfPceConsumption]:
        """Returns the consumption of each PCE, keyed by PCE identifier. Its records are validated by the parser."""

        res = self.__consumption_json(consumption_type, start_date, end_date, pce_list, Decimal)

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

        filename = response.headers["Content-Disposition"].split("filename=")[1]

        return GrdfExcelSheet(filename=filename, content=response.content)

    # ------------------------------------------------------
    def __meteo_json(self, end_date: date, days: int, pce: str) -> Any:

        end = end_date.strftime(DATE_FORMAT)

        return self.get(f"/e-conso/pce/{pce}/meteo", {"dateFinPeriode": end, "nbJours": days}).json()

    # ------------------------------------------------------
    def get_pce_meteo_raw(self, end_date: date, days: int, pce: str) -> dict[str, Any]:
        """Returns the meteo response as the API sent it, once checked against its shape."""

        res = self.__meteo_json(end_date, days, pce)

        if type(res) is list and len(res) == 0:
            return dict[str, Any]()

        GrdfMeteoResponse.model_validate(res)

        return res

    # ------------------------------------------------------
    def get_pce_meteo(self, end_date: date, days: int, pce: str) -> dict[date, float | None]:
        """Returns the temperature of each day, keyed by date."""

        res = self.__meteo_json(end_date, days, pce)

        if type(res) is list and len(res) == 0:
            return {}

        return GrdfMeteoResponse.model_validate(res).root
