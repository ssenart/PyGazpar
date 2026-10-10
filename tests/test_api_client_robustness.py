import logging
import os
from datetime import date
from unittest import mock

import pytest
from requests.exceptions import ConnectionError as RequestsConnectionError
from requests.exceptions import ReadTimeout

from pygazpar import Frequency
from pygazpar.api_client import (
    API_BASE_URL,
    DEFAULT_EXCEL_FILENAME,
    MAX_RETRY_AFTER_SECONDS,
    MAX_RETRY_DELAY_SECONDS,
    REQUEST_TIMEOUT,
    RETRY_DELAY_SECONDS,
    APIClient,
    InternalServerError,
    ServerError,
    excel_filename,
)
from pygazpar.datasource import ExcelWebDataSource, JsonWebDataSource
from pygazpar.grdf import GrdfExcelSheet

ENDPOINT = "/e-conso/pce"
URL = f"{API_BASE_URL}{ENDPOINT}"


def answer(status_code=200, content_type="application/json", url=URL):
    response = mock.Mock()
    response.status_code = status_code
    response.headers = {"Content-Type": content_type} if content_type is not None else {}
    response.url = url
    response.text = ""
    return response


def client_with(*answers, retry_count=3):
    client = APIClient("user@example.com", "password", retry_count=retry_count)
    session = mock.Mock()
    session.get.side_effect = list(answers)
    client._session = session
    return client, session


@pytest.fixture(autouse=True)
def no_sleep():
    with mock.patch("pygazpar.api_client.time.sleep") as sleep:
        yield sleep


class TestRequestTimeout:
    # ------------------------------------------------------
    def test_get_sends_a_timeout(self):
        client, session = client_with(answer())

        client.get(ENDPOINT, {})

        assert session.get.call_args.kwargs["timeout"] == REQUEST_TIMEOUT


class TestNetworkErrors:
    # ------------------------------------------------------
    @pytest.mark.parametrize("error", [RequestsConnectionError("down"), ReadTimeout("slow")])
    def test_a_network_error_is_retried(self, error, no_sleep):
        ok = answer()
        client, session = client_with(error, ok)

        assert client.get(ENDPOINT, {}) is ok
        assert session.get.call_count == 2
        no_sleep.assert_called_once()

    # ------------------------------------------------------
    def test_the_network_error_is_raised_when_the_retry_limit_is_reached(self):
        client, session = client_with(*[ReadTimeout("slow")] * 3, retry_count=3)

        with pytest.raises(ReadTimeout):
            client.get(ENDPOINT, {})

        assert session.get.call_count == 3


class TestGetRobustness:
    # ------------------------------------------------------
    def test_a_missing_content_type_is_not_a_crash(self):
        ok = answer(content_type=None)
        client, _ = client_with(ok)

        assert client.get(ENDPOINT, {}) is ok

    # ------------------------------------------------------
    def test_a_retry_count_of_zero_still_calls_once(self):
        ok = answer()
        client, session = client_with(ok, retry_count=0)

        assert client.get(ENDPOINT, {}) is ok
        assert session.get.call_count == 1

    # ------------------------------------------------------
    def test_an_html_answer_is_retried_then_raised(self):
        client, session = client_with(*[answer(content_type="text/html")] * 2, retry_count=2)

        with pytest.raises(InternalServerError):
            client.get(ENDPOINT, {})

        assert session.get.call_count == 2

    # ------------------------------------------------------
    def test_an_http_error_is_raised_at_once(self):
        client, session = client_with(answer(status_code=400))

        with pytest.raises(ServerError) as error:
            client.get(ENDPOINT, {})

        assert error.value.status_code == 400
        assert session.get.call_count == 1


class TestRateLimit:
    # ------------------------------------------------------
    def throttled(self, retry_after=None):
        response = answer(status_code=429, content_type="text/html")
        if retry_after is not None:
            response.headers["Retry-After"] = retry_after
        return response

    # ------------------------------------------------------
    def test_a_429_is_retried_after_the_default_delay(self, no_sleep, caplog):
        ok = answer()
        client, session = client_with(self.throttled(), ok)

        with caplog.at_level(logging.WARNING, logger="pygazpar.api_client"):
            assert client.get(ENDPOINT, {}) is ok

        assert session.get.call_count == 2
        no_sleep.assert_called_once_with(RETRY_DELAY_SECONDS)
        assert "limiting the request rate" in caplog.text
        assert "unknown error" not in caplog.text

    # ------------------------------------------------------
    @pytest.mark.parametrize(
        "retry_after, expected", [("7", 7), ("0", 0), ("600", MAX_RETRY_AFTER_SECONDS), ("soon", RETRY_DELAY_SECONDS)]
    )
    def test_the_retry_after_header_is_honored_within_a_limit(self, retry_after, expected, no_sleep):
        client, _ = client_with(self.throttled(retry_after), answer())

        client.get(ENDPOINT, {})

        no_sleep.assert_called_once_with(expected)

    # ------------------------------------------------------
    def test_the_delay_grows_at_each_attempt_up_to_a_limit(self, no_sleep):
        client, session = client_with(*[self.throttled()] * 6, answer(), retry_count=10)

        client.get(ENDPOINT, {})

        delays = [call.args[0] for call in no_sleep.call_args_list]
        assert delays == [3, 6, 12, MAX_RETRY_DELAY_SECONDS, MAX_RETRY_DELAY_SECONDS, MAX_RETRY_DELAY_SECONDS]
        assert session.get.call_count == 7

    # ------------------------------------------------------
    def test_network_errors_and_html_answers_back_off_too(self, no_sleep):
        client, _ = client_with(
            ReadTimeout("slow"), answer(content_type="text/html"), ReadTimeout("slow"), answer(), retry_count=10
        )

        client.get(ENDPOINT, {})

        assert [call.args[0] for call in no_sleep.call_args_list] == [3, 6, 12]

    # ------------------------------------------------------
    def test_a_429_at_the_retry_limit_is_a_rate_limit_error(self):
        client, session = client_with(*[self.throttled()] * 2, retry_count=2)

        with pytest.raises(ServerError) as error:
            client.get(ENDPOINT, {})

        assert error.value.status_code == 429
        assert session.get.call_count == 2


class TestExpiredSession:
    # ------------------------------------------------------
    @pytest.mark.parametrize(
        "expired",
        [
            answer(status_code=401),
            answer(content_type="text/html", url="https://connexion.grdf.fr/login"),
        ],
    )
    def test_the_client_logs_in_again_once_and_repeats_the_call(self, expired):
        ok = answer()
        client, _ = client_with(expired, ok)

        with mock.patch.object(APIClient, "login") as login, mock.patch.object(APIClient, "logout") as logout:
            assert client.get(ENDPOINT, {}) is ok

        login.assert_called_once()
        logout.assert_called_once()

    # ------------------------------------------------------
    def test_a_second_expiry_is_raised(self):
        client, _ = client_with(answer(status_code=401), answer(status_code=401))

        with mock.patch.object(APIClient, "login"), mock.patch.object(APIClient, "logout"):
            with pytest.raises(ServerError) as error:
                client.get(ENDPOINT, {})

        assert error.value.status_code == 401

    # ------------------------------------------------------
    def test_the_repeated_call_uses_the_new_session(self):
        client, old_session = client_with(answer(status_code=401))
        new_session = mock.Mock()
        ok = answer()
        new_session.get.return_value = ok

        def login_again():
            client._session = new_session

        with mock.patch.object(APIClient, "login", side_effect=login_again):
            assert client.get(ENDPOINT, {}) is ok

        assert old_session.get.call_count == 1
        assert new_session.get.call_count == 1


class TestExcelFilename:
    # ------------------------------------------------------
    @pytest.mark.parametrize(
        "header, expected",
        [
            ("attachment; filename=Donnees_informatives_1.xlsx", "Donnees_informatives_1.xlsx"),
            ('attachment; filename="Donnees informatives.xlsx"', "Donnees informatives.xlsx"),
            ("attachment; filename*=UTF-8''Donnees_2.xlsx", "Donnees_2.xlsx"),
            ("attachment; filename=../../etc/passwd", "passwd"),
            ("attachment; filename=..\\..\\evil.xlsx", "evil.xlsx"),
            ("attachment; filename=..", DEFAULT_EXCEL_FILENAME),
            ("attachment", DEFAULT_EXCEL_FILENAME),
            (None, DEFAULT_EXCEL_FILENAME),
        ],
    )
    def test_the_name_is_a_base_name(self, header, expected):
        assert excel_filename(header) == expected


class TestExcelWebDataSourceTmpDirectory:
    # ------------------------------------------------------
    def test_the_tmp_directory_is_left_clean_and_foreign_files_are_kept(self, tmp_path):
        foreign = tmp_path / "Donnees_informatives_other.xlsx"
        foreign.write_bytes(b"belongs to someone else")
        seen = []

        def parse(path, _frequency):
            seen.append(os.path.dirname(path))
            assert os.path.isfile(path)
            return []

        data_source = ExcelWebDataSource("user", "password", str(tmp_path))
        sheet = GrdfExcelSheet(filename="../../x.xlsx", content=b"xlsx")

        with (
            mock.patch.object(data_source._api_client, "get_pce_consumption_excelsheet", return_value=sheet),
            mock.patch("pygazpar.datasource.ExcelParser.parse", side_effect=parse),
        ):
            result = data_source._load_from_session("PCE", date(2025, 1, 1), date(2025, 1, 7), [Frequency.DAILY])

        assert result == {"daily": []}
        assert seen and seen[0] != str(tmp_path)
        assert os.listdir(tmp_path) == [foreign.name]

    # ------------------------------------------------------
    def test_the_private_directory_is_removed_when_the_parsing_fails(self, tmp_path):
        data_source = ExcelWebDataSource("user", "password", str(tmp_path))
        sheet = GrdfExcelSheet(filename="x.xlsx", content=b"xlsx")

        with (
            mock.patch.object(data_source._api_client, "get_pce_consumption_excelsheet", return_value=sheet),
            mock.patch("pygazpar.datasource.ExcelParser.parse", side_effect=ValueError("bad file")),
        ):
            with pytest.raises(ValueError):
                data_source._load_from_session("PCE", date(2025, 1, 1), date(2025, 1, 7), [Frequency.DAILY])

        assert os.listdir(tmp_path) == []


class TestJsonWebDataSourceResults:
    # ------------------------------------------------------
    def test_no_data_gives_an_empty_list_per_requested_frequency(self):
        data_source = JsonWebDataSource("user", "password")

        with (
            mock.patch.object(data_source._api_client, "get_pce_consumption", return_value={}),
            mock.patch.object(data_source._api_client, "get_pce_meteo", return_value={}),
        ):
            result = data_source._load_from_session(
                "PCE", date(2010, 1, 1), date(2010, 1, 7), [Frequency.DAILY, Frequency.MONTHLY]
            )

        assert result == {"daily": [], "monthly": []}

    # ------------------------------------------------------
    def test_a_temperature_failure_is_logged_and_not_blocking(self, caplog):
        data_source = JsonWebDataSource("user", "password")

        with (
            mock.patch.object(data_source._api_client, "get_pce_consumption", return_value={}),
            mock.patch.object(data_source._api_client, "get_pce_meteo", side_effect=ServerError("meteo down", 500)),
            caplog.at_level(logging.WARNING, logger="pygazpar.datasource"),
        ):
            data_source._load_from_session("PCE", date(2010, 1, 1), date(2010, 1, 7), [Frequency.DAILY])

        assert "temperatures are not available" in caplog.text
        assert "meteo down" in caplog.text


class TestExcelWebDataSourceConstructor:
    # ------------------------------------------------------
    def test_the_legacy_tmp_directory_keyword_still_works_with_a_warning(self):
        with pytest.warns(DeprecationWarning, match="tmp_directory"):
            data_source = ExcelWebDataSource("user", "password", tmpDirectory="tmp")

        assert data_source._tmp_directory == "tmp"

    # ------------------------------------------------------
    def test_a_tmp_directory_is_required(self):
        with pytest.raises(TypeError, match="tmp_directory"):
            ExcelWebDataSource("user", "password")
