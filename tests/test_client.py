from pygazpar.enum import Frequency
from pygazpar.client import Client
from pygazpar.datasource import JsonWebDataSource, TestDataSource, ExcelWebDataSource
import os
import pytest


class TestClient:

    @classmethod
    def setup_class(cls):
        """ setup any state specific to the execution of the given class (which
        usually contains tests).
        """

    @classmethod
    def teardown_class(cls):
        """ teardown any state that was previously setup with a call to
        setup_class.
        """

    def setup_method(self):
        """ setup any state tied to the execution of the given method in a
        class.  setup_method is invoked for every test method of a class.
        """
        tmpdir = os.path.normpath(f"{os.getcwd()}/tmp")

        # We create the tmp directory if not already exists.
        if not os.path.exists(tmpdir):
            os.mkdir(tmpdir)

        self.__username = os.environ["GRDF_USERNAME"]
        self.__password = os.environ["GRDF_PASSWORD"]
        self.__pceIdentifier = os.environ["PCE_IDENTIFIER"]
        self.__tmp_directory = tmpdir

    def teardown_method(self):
        """ teardown any state that was previously setup with a setup_method
        call.
        """

    def test_login_error(self):
        client = Client(JsonWebDataSource("WrongUsername", "WrongPassword"))

        with pytest.raises(Exception):
            client.loadSince(self.__pceIdentifier, 365, [Frequency.DAILY])

    def test_hourly_live(self):
        client = Client(JsonWebDataSource(self.__username, self.__password))

        data = client.loadSince(self.__pceIdentifier, 365, [Frequency.HOURLY])

        assert (len(data[Frequency.HOURLY.value]) == 0)

    # @pytest.mark.skip(reason="Requires live data")
    def test_daily_jsonweb(self):
        client = Client(JsonWebDataSource(self.__username, self.__password))

        data = client.loadSince(self.__pceIdentifier, 365, [Frequency.DAILY])

        assert (len(data[Frequency.DAILY.value]) > 0)

    def test_weekly_jsonweb(self):
        client = Client(JsonWebDataSource(self.__username, self.__password))

        data = client.loadSince(self.__pceIdentifier, 365, [Frequency.WEEKLY])

        assert (len(data[Frequency.WEEKLY.value]) >= 51 and len(data[Frequency.WEEKLY.value]) <= 54)

    def test_monthly_jsonweb(self):
        client = Client(JsonWebDataSource(self.__username, self.__password))

        data = client.loadSince(self.__pceIdentifier, 365, [Frequency.MONTHLY])

        assert (len(data[Frequency.MONTHLY.value]) >= 12 and len(data[Frequency.MONTHLY.value]) <= 13)

    def test_yearly_jsonweb(self):
        client = Client(ExcelWebDataSource(self.__username, self.__password, self.__tmp_directory))

        data = client.loadSince(self.__pceIdentifier, 365, [Frequency.YEARLY])

        assert (len(data[Frequency.YEARLY.value]) == 1)

    def test_daily_excelweb(self):
        client = Client(ExcelWebDataSource(self.__username, self.__password, self.__tmp_directory))

        data = client.loadSince(self.__pceIdentifier, 365, [Frequency.DAILY])

        assert (len(data[Frequency.DAILY.value]) > 0)

    def test_weekly_excelweb(self):
        client = Client(ExcelWebDataSource(self.__username, self.__password, self.__tmp_directory))

        data = client.loadSince(self.__pceIdentifier, 365, [Frequency.WEEKLY])

        assert (len(data[Frequency.WEEKLY.value]) >= 51 and len(data[Frequency.WEEKLY.value]) <= 54)

    def test_monthly_excelweb(self):
        client = Client(ExcelWebDataSource(self.__username, self.__password, self.__tmp_directory))

        data = client.loadSince(self.__pceIdentifier, 365, [Frequency.MONTHLY])

        assert (len(data[Frequency.MONTHLY.value]) >= 12 and len(data[Frequency.MONTHLY.value]) <= 13)

    def test_yearly_excelweb(self):
        client = Client(ExcelWebDataSource(self.__username, self.__password, self.__tmp_directory))

        data = client.loadSince(self.__pceIdentifier, 365, [Frequency.YEARLY])

        assert (len(data[Frequency.YEARLY.value]) == 1)

    def test_hourly_sample(self):
        client = Client(TestDataSource())

        data = client.loadSince(self.__pceIdentifier, 365, [Frequency.HOURLY])

        assert (len(data[Frequency.HOURLY.value]) == 0)

    def test_daily_sample(self):
        client = Client(TestDataSource())

        data = client.loadSince(self.__pceIdentifier, 365, [Frequency.DAILY])

        assert (len(data[Frequency.DAILY.value]) == 711)

    def test_weekly_sample(self):
        client = Client(TestDataSource())

        data = client.loadSince(self.__pceIdentifier, 365, [Frequency.WEEKLY])

        assert (len(data[Frequency.WEEKLY.value]) > 0)

    def test_monthly_sample(self):
        client = Client(TestDataSource())

        data = client.loadSince(self.__pceIdentifier, 365, [Frequency.MONTHLY])

        assert (len(data[Frequency.MONTHLY.value]) > 0)

    def test_yearly_sample(self):
        client = Client(TestDataSource())

        data = client.loadSince(self.__pceIdentifier, 365, [Frequency.YEARLY])

        assert (len(data[Frequency.YEARLY.value]) == 2)
