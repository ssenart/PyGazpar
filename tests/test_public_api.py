import json
from datetime import date
from unittest import mock

import pytest

import pygazpar
from pygazpar import (
    Client,
    Frequency,
    IDataSource,
    JsonWebDataSource,
    LoginError,
    NotLoggedInError,
    PyGazparError,
    RateLimitError,
    RawConsumptionWebDataSource,
    RawTemperatureWebDataSource,
    ServerError,
    TestDataSource,
    UnknownPceError,
)
from pygazpar.api_client import APIClient, GrdfFrequency


class TestErrors:
    # ------------------------------------------------------
    @pytest.mark.parametrize(
        "error",
        [
            ServerError("x", 500),
            LoginError("x", 401),
            RateLimitError("x"),
            NotLoggedInError("x"),
            UnknownPceError("PCE"),
        ],
    )
    def test_every_error_is_a_pygazpar_error(self, error):
        assert isinstance(error, PyGazparError)
        assert not isinstance(error, SystemError)

    # ------------------------------------------------------
    def test_login_and_rate_limit_errors_are_server_errors(self):
        assert issubclass(LoginError, ServerError)
        assert issubclass(RateLimitError, ServerError)
        assert RateLimitError("x").status_code == 429

    # ------------------------------------------------------
    def test_a_client_that_did_not_log_in_still_raises_a_connection_error(self):
        with pytest.raises(ConnectionError, match="login first"):
            APIClient("u", "p").get("/e-conso/pce", {})

        with pytest.raises(NotLoggedInError):
            APIClient("u", "p").get("/e-conso/pce", {})

    # ------------------------------------------------------
    def test_an_unknown_pce_is_not_a_server_error(self):
        error = UnknownPceError("PCE")

        assert not isinstance(error, ServerError)
        assert isinstance(error, LookupError)
        assert "PCE" in str(error)

    # ------------------------------------------------------
    def test_the_errors_stay_importable_from_their_former_modules(self):
        from pygazpar.api_client import InternalServerError
        from pygazpar.api_client import ServerError as ApiServerError
        from pygazpar.datasource import UnknownPceError as DatasourceUnknownPceError

        assert ApiServerError is ServerError
        assert DatasourceUnknownPceError is UnknownPceError
        assert issubclass(InternalServerError, ServerError)


class TestExports:
    # ------------------------------------------------------
    @pytest.mark.parametrize(
        "name", ["PeriodReading", "DailyReading", "IDataSource", "PropertyName", "ConsumptionType"]
    )
    def test_the_types_of_the_results_are_exported(self, name):
        assert hasattr(pygazpar, name)

    # ------------------------------------------------------
    def test_the_two_frequencies_have_distinct_names(self):
        assert pygazpar.Frequency is not GrdfFrequency
        assert pygazpar.Frequency.DAILY.value == "daily"
        assert GrdfFrequency.DAILY.value == "Journalier"


class TestResultsKeyedByFrequency:
    # ------------------------------------------------------
    def test_readings_are_keyed_by_frequency_and_by_its_value(self):
        client = Client(TestDataSource())

        readings = client.load_readings_since("0123456789", 365, [Frequency.DAILY, Frequency.MONTHLY])
        data = client.load_since("0123456789", 365, [Frequency.DAILY, Frequency.MONTHLY])

        for result in (readings, data):
            assert set(result) == {Frequency.DAILY, Frequency.MONTHLY}
            assert result[Frequency.DAILY] is result["daily"]
            assert result.get("monthly") is result[Frequency.MONTHLY]

    # ------------------------------------------------------
    def test_the_dict_form_is_json_with_the_same_keys_as_before(self):
        data = Client(TestDataSource()).load_since("0123456789", 365, [Frequency.DAILY])

        assert list(json.loads(json.dumps(data))) == ["daily"]
        assert data == {"daily": data["daily"]}

    # ------------------------------------------------------
    def test_a_frequency_is_a_string(self):
        assert Frequency.DAILY == "daily"
        assert str(Frequency.DAILY) == "daily"
        assert Frequency("weekly") is Frequency.WEEKLY


class TestContextManager:
    # ------------------------------------------------------
    def test_the_with_block_logs_in_and_out(self):
        data_source = mock.Mock(spec=IDataSource)

        with Client(data_source) as client:
            data_source.login.assert_called_once()
            data_source.logout.assert_not_called()
            assert isinstance(client, Client)

        data_source.logout.assert_called_once()

    # ------------------------------------------------------
    def test_the_with_block_logs_out_when_the_body_fails(self):
        data_source = mock.Mock(spec=IDataSource)

        with pytest.raises(RuntimeError, match="boom"):
            with Client(data_source):
                raise RuntimeError("boom")

        data_source.logout.assert_called_once()


class TestRawDataSources:
    # ------------------------------------------------------
    @pytest.mark.parametrize("data_source_class", [RawConsumptionWebDataSource, RawTemperatureWebDataSource])
    def test_a_raw_data_source_can_log_in_and_out(self, data_source_class):
        with mock.patch("pygazpar.datasource.APIClient") as api_client_class:
            api_client = api_client_class.return_value
            api_client.is_logged_in.return_value = False
            data_source = data_source_class("u", "p")

            data_source.login()
            api_client.login.assert_called_once()

            api_client.is_logged_in.return_value = True
            data_source.logout()
            api_client.logout.assert_called_once()

    # ------------------------------------------------------
    def test_the_raw_data_sources_share_a_base(self):
        assert issubclass(RawConsumptionWebDataSource, pygazpar.RawWebDataSource)
        assert issubclass(RawTemperatureWebDataSource, pygazpar.RawWebDataSource)
        assert not issubclass(RawConsumptionWebDataSource, IDataSource)

    # ------------------------------------------------------
    def test_no_data_from_a_web_source_has_a_key_per_frequency(self):
        data_source = JsonWebDataSource("u", "p")

        with (
            mock.patch.object(data_source._api_client, "get_pce_consumption", return_value={}),
            mock.patch.object(data_source._api_client, "get_pce_meteo", return_value={}),
        ):
            result = data_source._load_from_session("PCE", date(2010, 1, 1), date(2010, 1, 7), [Frequency.DAILY])

        assert result == {Frequency.DAILY: []}
