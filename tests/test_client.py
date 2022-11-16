from pygazpar.enum import Frequency
from pygazpar.client import Client
from pygazpar.clientV2 import ClientV2
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
        client = Client("WrongUserName", "WrongPassword", "WrongPCENumber", Frequency.DAILY, tmpDirectory=self.__tmp_directory, lastNDays=365, testMode=False)

        with pytest.raises(Exception):
            client.update()

    @pytest.mark.skip(reason="Hourly data is not yet implemented")
    def test_hourly_live(self):
        client = Client(self.__username, self.__password, self.__pceIdentifier, Frequency.HOURLY, tmpDirectory=self.__tmp_directory, lastNDays=30)
        client.update()

        assert (len(client.data()) > 0)

    # @pytest.mark.skip(reason="Requires live data")
    def test_daily_live(self):
        client = Client(self.__username, self.__password, self.__pceIdentifier, Frequency.DAILY, tmpDirectory=self.__tmp_directory, lastNDays=720)
        client.update()

        assert (len(client.data()) > 0)

    # @pytest.mark.skip(reason="Requires live data")
    def test_weekly_live(self):
        client = Client(self.__username, self.__password, self.__pceIdentifier, Frequency.WEEKLY, tmpDirectory=self.__tmp_directory, lastNDays=30)
        client.update()

        assert (len(client.data()) > 0)

    # @pytest.mark.skip(reason="Requires live data")
    def test_monthly_live(self):
        client = Client(self.__username, self.__password, self.__pceIdentifier, Frequency.MONTHLY, tmpDirectory=self.__tmp_directory, lastNDays=1095)
        client.update()

        assert (len(client.data()) > 0)

    def test_hourly_sample(self):
        client = Client(self.__username, self.__password, self.__pceIdentifier, Frequency.HOURLY, tmpDirectory=self.__tmp_directory, lastNDays=365, testMode=True)
        client.update()

        assert (len(client.data()) == 0)

    def test_daily_sample(self):
        client = Client(self.__username, self.__password, self.__pceIdentifier, Frequency.DAILY, tmpDirectory=self.__tmp_directory, lastNDays=365, testMode=True)
        client.update()

        assert (len(client.data()) > 0)

    def test_weekly_sample(self):
        client = Client(self.__username, self.__password, self.__pceIdentifier, Frequency.WEEKLY, tmpDirectory=self.__tmp_directory, lastNDays=365, testMode=True)
        client.update()

        assert (len(client.data()) > 0)

    def test_monthly_sample(self):
        client = Client(self.__username, self.__password, self.__pceIdentifier, Frequency.MONTHLY, tmpDirectory=self.__tmp_directory, lastNDays=30, testMode=True)
        client.update()

        assert (len(client.data()) > 0)

    # @pytest.mark.skip(reason="Requires live data")
    def test_clientV2(self):
        client = ClientV2(self.__username, self.__password, self.__pceIdentifier, lastNDays=360, testMode=False)
        client.update()

        assert (len(client.data()) == 360)
