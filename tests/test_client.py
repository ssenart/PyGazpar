import os

import pytest

from pygazpar.client import Client
from pygazpar.datasource import ExcelWebDataSource, JsonWebDataSource, TestDataSource
from pygazpar.enum import Frequency


class TestClient:  # pylint: disable=too-many-public-methods

    @classmethod
    def setup_class(cls):
        """setup any state specific to the execution of the given class (which
        usually contains tests).
        """
        tmpdir = os.path.normpath(f"{os.getcwd()}/tmp")

        # We create the tmp directory if not already exists.
        if not os.path.exists(tmpdir):
            os.mkdir(tmpdir)

        cls._username = os.environ["GRDF_USERNAME"]  # pylint: disable=attribute-defined-outside-init
        cls._password = os.environ["GRDF_PASSWORD"]  # pylint: disable=attribute-defined-outside-init
        cls._pceIdentifier = os.environ["PCE_IDENTIFIER"]  # pylint: disable=attribute-defined-outside-init
        cls._tmp_directory = tmpdir  # pylint: disable=attribute-defined-outside-init

        cls._jsonClient = Client(JsonWebDataSource(TestClient._username, TestClient._password))
        cls._excelClient = Client(
            ExcelWebDataSource(TestClient._username, TestClient._password, TestClient._tmp_directory)
        )
        cls._testClient = Client(TestDataSource())

    @classmethod
    def teardown_class(cls):
        """teardown any state that was previously setup with a call to
        setup_class.
        """
        cls._jsonClient.logout()
        cls._excelClient.logout()
        cls._testClient.logout()

    def setup_method(self):
        """setup any state tied to the execution of the given method in a
        class.  setup_method is invoked for every test method of a class.
        """

    def teardown_method(self):
        """teardown any state that was previously setup with a setup_method
        call.
        """

    def test_login_error(self):
        client = Client(JsonWebDataSource("WrongUsername", "WrongPassword"))

        with pytest.raises(Exception):
            client.load_since(TestClient._pceIdentifier, 365, [Frequency.DAILY])

    def test_get_pce_identifiers(self):
        pce_identifiers = TestClient._jsonClient.get_pce_identifiers()

        assert len(pce_identifiers) > 0

    def test_hourly_live(self):
        data = TestClient._jsonClient.load_since(TestClient._pceIdentifier, 365, [Frequency.HOURLY])

        assert len(data[Frequency.HOURLY.value]) == 0

    def test_one_day_jsonweb(self):
        data = TestClient._jsonClient.load_since(TestClient._pceIdentifier, 1, [Frequency.DAILY])

        assert len(data[Frequency.DAILY.value]) <= 1

    def test_two_days_jsonweb(self):
        data = TestClient._jsonClient.load_since(TestClient._pceIdentifier, 2, [Frequency.DAILY])

        assert len(data[Frequency.DAILY.value]) <= 2

    # @pytest.mark.skip(reason="Requires live data")
    def test_daily_jsonweb(self):
        data = TestClient._jsonClient.load_since(TestClient._pceIdentifier, 365, [Frequency.DAILY])

        assert len(data[Frequency.DAILY.value]) > 0

    def test_weekly_jsonweb(self):
        data = TestClient._jsonClient.load_since(TestClient._pceIdentifier, 365, [Frequency.WEEKLY])

        assert len(data[Frequency.WEEKLY.value]) >= 51 and len(data[Frequency.WEEKLY.value]) <= 54

    def test_monthly_jsonweb(self):
        data = TestClient._jsonClient.load_since(TestClient._pceIdentifier, 365, [Frequency.MONTHLY])

        assert len(data[Frequency.MONTHLY.value]) >= 11 and len(data[Frequency.MONTHLY.value]) <= 13

    def test_yearly_jsonweb(self):
        data = TestClient._jsonClient.load_since(TestClient._pceIdentifier, 365, [Frequency.YEARLY])

        assert len(data[Frequency.YEARLY.value]) >= 1

    def test_daily_excelweb(self):
        data = TestClient._excelClient.load_since(TestClient._pceIdentifier, 365, [Frequency.DAILY])

        assert len(data[Frequency.DAILY.value]) > 0

    def test_weekly_excelweb(self):
        data = TestClient._excelClient.load_since(TestClient._pceIdentifier, 365, [Frequency.WEEKLY])

        assert len(data[Frequency.WEEKLY.value]) >= 51 and len(data[Frequency.WEEKLY.value]) <= 54

    def test_monthly_excelweb(self):
        data = TestClient._excelClient.load_since(TestClient._pceIdentifier, 365, [Frequency.MONTHLY])

        assert len(data[Frequency.MONTHLY.value]) >= 12 and len(data[Frequency.MONTHLY.value]) <= 13

    def test_yearly_excelweb(self):
        data = TestClient._excelClient.load_since(TestClient._pceIdentifier, 365, [Frequency.YEARLY])

        assert len(data[Frequency.YEARLY.value]) >= 1

    def test_hourly_sample(self):
        data = TestClient._testClient.load_since(TestClient._pceIdentifier, 365, [Frequency.HOURLY])

        assert len(data[Frequency.HOURLY.value]) == 0

    def test_daily_sample(self):
        data = TestClient._testClient.load_since(TestClient._pceIdentifier, 365, [Frequency.DAILY])

        assert len(data[Frequency.DAILY.value]) == 711

    def test_weekly_sample(self):
        data = TestClient._testClient.load_since(TestClient._pceIdentifier, 365, [Frequency.WEEKLY])

        assert len(data[Frequency.WEEKLY.value]) > 0

    def test_monthly_sample(self):
        data = TestClient._testClient.load_since(TestClient._pceIdentifier, 365, [Frequency.MONTHLY])

        assert len(data[Frequency.MONTHLY.value]) > 0

    def test_yearly_sample(self):
        data = TestClient._testClient.load_since(TestClient._pceIdentifier, 365, [Frequency.YEARLY])

        assert len(data[Frequency.YEARLY.value]) == 2
