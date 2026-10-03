from datetime import date, timedelta
from unittest import mock

import pytest

from pygazpar.api_client import APIClient, ConsumptionType
from pygazpar.datasource import RawConsumptionWebDataSource, RawTemperatureWebDataSource


class TestRawConsumptionWebDataSource:

    # ------------------------------------------------------
    def test_load_returns_api_payload_unmodified(self):

        consumption = {"releves": [{"dateDebut": "2026-09-01", "volumeBrutM3": 1.2}]}

        with (
            mock.patch.object(APIClient, "login"),
            mock.patch.object(APIClient, "get_pce_consumption_raw", return_value=consumption) as get_consumption,
        ):
            res = RawConsumptionWebDataSource("user", "password").load("123", date(2026, 9, 1), date(2026, 9, 30))

        assert res == consumption
        get_consumption.assert_called_once_with(
            ConsumptionType.INFORMATIVE, date(2026, 9, 1), date(2026, 9, 30), ["123"]
        )

    # ------------------------------------------------------
    def test_load_uses_given_consumption_type(self):

        with (
            mock.patch.object(APIClient, "login"),
            mock.patch.object(APIClient, "get_pce_consumption_raw", return_value={}) as get_consumption,
        ):
            RawConsumptionWebDataSource("user", "password", ConsumptionType.PUBLISHED).load(
                "123", date(2026, 9, 1), date(2026, 9, 30)
            )

        get_consumption.assert_called_once_with(ConsumptionType.PUBLISHED, date(2026, 9, 1), date(2026, 9, 30), ["123"])


class TestRawTemperatureWebDataSource:

    # ------------------------------------------------------
    def test_load_returns_api_payload_unmodified(self):

        temperatures = {"temperatures": [{"date": "2026-09-01", "temperature": 15.0}]}

        with (
            mock.patch.object(APIClient, "login"),
            mock.patch.object(APIClient, "get_pce_meteo_raw", return_value=temperatures),
        ):
            res = RawTemperatureWebDataSource("user", "password").load("123", date(2026, 9, 1), date(2026, 9, 30))

        assert res == temperatures

    # ------------------------------------------------------
    def test_load_window_is_start_to_end_when_end_is_in_the_past(self):

        with (
            mock.patch.object(APIClient, "login"),
            mock.patch.object(APIClient, "get_pce_meteo_raw", return_value={}) as get_meteo,
        ):
            RawTemperatureWebDataSource("user", "password").load("123", date(2026, 9, 1), date(2026, 9, 30))

        get_meteo.assert_called_once_with(date(2026, 9, 30), 29, "123")

    # ------------------------------------------------------
    def test_load_caps_end_at_yesterday_and_days_at_least_ten(self):

        today = date.today()

        with (
            mock.patch.object(APIClient, "login"),
            mock.patch.object(APIClient, "get_pce_meteo_raw", return_value={}) as get_meteo,
        ):
            RawTemperatureWebDataSource("user", "password").load("123", today - timedelta(days=5), today)

        get_meteo.assert_called_once_with(today - timedelta(days=1), 10, "123")

    # ------------------------------------------------------
    def test_load_raises_when_temperatures_fail(self):

        with (
            mock.patch.object(APIClient, "login"),
            mock.patch.object(APIClient, "get_pce_meteo_raw", side_effect=ConnectionError("meteo down")),
        ):
            with pytest.raises(ConnectionError):
                RawTemperatureWebDataSource("user", "password").load("123", date(2026, 9, 1), date(2026, 9, 30))
