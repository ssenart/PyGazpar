import json
import os
from datetime import date
from unittest import mock

import pytest
from dotenv import find_dotenv, load_dotenv

from pygazpar.api_client import APIClient, ConsumptionType, ServerError
from pygazpar.client import Client
from pygazpar.datasource import (
    JsonWebDataSource,
    RawConsumptionWebDataSource,
    RawTemperatureWebDataSource,
    UnknownPceError,
)
from pygazpar.model import Frequency

# The credentials for the real API may be in .env, as for the command line.
load_dotenv(find_dotenv(usecwd=True))

INVALID_PCE = "InvalidPceIdentifier"
KNOWN_PCE = "12345678901234"  # A dummy identifier: the only PCE of the account in the offline tests.
START_DATE = date(2025, 1, 1)
END_DATE = date(2025, 1, 7)


def fake_response(status_code, body):
    response = mock.Mock()
    response.status_code = status_code
    response.headers = {"Content-Type": "application/json"}
    response.text = body if isinstance(body, str) else json.dumps(body)
    response.json.return_value = body
    return response


def answer(url, params=None):  # pylint: disable=unused-argument
    """Answers the way GrDF does: the account has one PCE. An unknown PCE gets no consumption, and a refusal for its temperatures."""

    if url.endswith("/e-conso/pce"):
        return fake_response(200, [{"idObject": KNOWN_PCE}])

    if "/meteo" in url and INVALID_PCE in url:
        return fake_response(400, "Le pce InvalidPceIdentifier n'existe pas !")

    return fake_response(200, [])


def client_after_a_successful_login():
    """Returns an API client whose login succeeded: it holds an open session."""

    client = APIClient("user@example.com", "password")
    session = mock.Mock()
    session.get.side_effect = answer
    client._session = session  # pylint: disable=protected-access

    return client


class TestUnknownPceAfterASuccessfulLogin:  # pylint: disable=too-few-public-methods

    # ------------------------------------------------------
    def test_consumption_of_an_unknown_pce_is_empty(self):
        client = client_after_a_successful_login()

        consumption = client.get_pce_consumption(ConsumptionType.INFORMATIVE, START_DATE, END_DATE, [INVALID_PCE])

        assert consumption == {}

    # ------------------------------------------------------
    def test_temperatures_of_an_unknown_pce_raise_a_server_error(self):
        client = client_after_a_successful_login()

        with pytest.raises(ServerError, match="n'existe pas"):
            client.get_pce_meteo(END_DATE, 7, INVALID_PCE)

    # ------------------------------------------------------
    def test_load_since_raises_for_an_unknown_pce(self):
        client = client_after_a_successful_login()

        with mock.patch("pygazpar.datasource.APIClient", return_value=client):
            with pytest.raises(UnknownPceError, match="does not exist in this account"):
                Client(JsonWebDataSource("user@example.com", "password")).load_since(
                    INVALID_PCE, 365, [Frequency.DAILY, Frequency.MONTHLY]
                )

    # ------------------------------------------------------
    def test_load_readings_since_raises_for_an_unknown_pce(self):
        client = client_after_a_successful_login()

        with mock.patch("pygazpar.datasource.APIClient", return_value=client):
            with pytest.raises(UnknownPceError, match="does not exist in this account"):
                Client(JsonWebDataSource("user@example.com", "password")).load_readings_since(
                    INVALID_PCE, 365, [Frequency.DAILY, Frequency.MONTHLY]
                )

    # ------------------------------------------------------
    def test_raw_consumption_of_an_unknown_pce_is_empty(self):
        client = client_after_a_successful_login()

        with mock.patch("pygazpar.datasource.APIClient", return_value=client):
            raw = RawConsumptionWebDataSource("user@example.com", "password").load(INVALID_PCE, START_DATE, END_DATE)

        assert raw == {}

    # ------------------------------------------------------
    def test_raw_temperature_of_an_unknown_pce_raises_a_server_error(self):
        client = client_after_a_successful_login()

        with mock.patch("pygazpar.datasource.APIClient", return_value=client):
            with pytest.raises(ServerError, match="n'existe pas"):
                RawTemperatureWebDataSource("user@example.com", "password").load(INVALID_PCE, START_DATE, END_DATE)


class TestKnownPceWithoutData:  # pylint: disable=too-few-public-methods

    # ------------------------------------------------------
    def test_load_date_range_returns_no_readings_for_a_known_pce_without_data(self):
        client = client_after_a_successful_login()

        with mock.patch("pygazpar.datasource.APIClient", return_value=client):
            data = Client(JsonWebDataSource("user@example.com", "password")).load_date_range(
                KNOWN_PCE, date(2010, 1, 1), date(2010, 1, 7), [Frequency.DAILY, Frequency.MONTHLY]
            )

        assert all(len(readings) == 0 for readings in data.values())


CREDENTIALS_ARE_SET = bool(os.environ.get("GRDF_USERNAME") and os.environ.get("GRDF_PASSWORD"))


@pytest.mark.skipif(not CREDENTIALS_ARE_SET, reason="GRDF_USERNAME and GRDF_PASSWORD are needed for the real API")
class TestUnknownPceWithTheRealApi:  # pylint: disable=too-few-public-methods

    @classmethod
    def setup_class(cls):
        cls._username = os.environ["GRDF_USERNAME"]
        cls._password = os.environ["GRDF_PASSWORD"]
        cls._client = APIClient(cls._username, cls._password)
        cls._client.login()

    # ------------------------------------------------------
    def test_login_works_and_lists_the_pces_of_the_account(self):
        assert len(self._client.get_pce_list()) > 0

    # ------------------------------------------------------
    def test_consumption_of_an_unknown_pce_is_empty(self):
        consumption = self._client.get_pce_consumption(ConsumptionType.INFORMATIVE, START_DATE, END_DATE, [INVALID_PCE])

        assert consumption == {}

    # ------------------------------------------------------
    def test_temperatures_of_an_unknown_pce_raise_a_server_error(self):
        with pytest.raises(ServerError, match="n'existe pas"):
            self._client.get_pce_meteo(END_DATE, 7, INVALID_PCE)

    # ------------------------------------------------------
    def test_load_since_raises_for_an_unknown_pce(self):
        with pytest.raises(UnknownPceError, match="does not exist in this account"):
            Client(JsonWebDataSource(self._username, self._password)).load_since(
                INVALID_PCE, 365, [Frequency.DAILY, Frequency.MONTHLY]
            )

    # ------------------------------------------------------
    def test_load_date_range_returns_no_readings_for_a_known_pce_without_data(self):
        known_pce = self._client.get_pce_list()[0].idObject

        data = Client(JsonWebDataSource(self._username, self._password)).load_date_range(
            known_pce, date(2010, 1, 1), date(2010, 1, 7), [Frequency.DAILY, Frequency.MONTHLY]
        )

        assert all(len(readings) == 0 for readings in data.values())
