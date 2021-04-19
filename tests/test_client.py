from pygazpar.enum import Frequency
from pygazpar.client import Client
from pygazpar.client import DummyClient
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

    def setup_method(self, method):
        """ setup any state tied to the execution of the given method in a
        class.  setup_method is invoked for every test method of a class.
        """
        tmpdir = os.path.normpath(f"{os.getcwd()}/tmp")

        # We create the tmp directory if not already exists.
        if not os.path.exists(tmpdir):
            os.mkdir(tmpdir)

        # We remove the geckodriver log file
        geckodriverLogFile = f"{tmpdir}/pygazpar_geckodriver.log"
        if os.path.isfile(geckodriverLogFile):
            os.remove(geckodriverLogFile)

        self.__username = os.environ["GRDF_USERNAME"]
        self.__password = os.environ["GRDF_PASSWORD"]
        if os.name == 'nt':
            self.__webdriver = "./drivers/geckodriver.exe"
        else:
            self.__webdriver = "./drivers/geckodriver"
        self.__wait_time = 30
        self.__tmp_directory = tmpdir

    def teardown_method(self, method):
        """ teardown any state that was previously setup with a setup_method
        call.
        """

    @pytest.mark.skip(reason="Live data are not available")
    def test_hourly_live(self):
        client = Client(self.__username, self.__password, self.__webdriver, self.__wait_time, self.__tmp_directory, 1, True, Frequency.HOURLY)
        client.update()

        assert len(client.data()) == 0

    @pytest.mark.skip(reason="Live data are not available")
    def test_daily_live(self):
        client = Client(self.__username, self.__password, self.__webdriver, self.__wait_time, self.__tmp_directory, 1, True, Frequency.DAILY)
        client.update()

        assert len(client.data()) == 1

    @pytest.mark.skip(reason="Live data are not available")
    def test_weekly_live(self):
        client = Client(self.__username, self.__password, self.__webdriver, self.__wait_time, self.__tmp_directory, 1, True, Frequency.WEEKLY)
        client.update()

        assert len(client.data()) == 1

    @pytest.mark.skip(reason="Live data are not available")
    def test_monthly_live(self):
        client = Client(self.__username, self.__password, self.__webdriver, self.__wait_time, self.__tmp_directory, 1, True, Frequency.MONTHLY)
        client.update()

        assert len(client.data()) == 1

    def test_hourly(self):
        client = DummyClient(0, Frequency.HOURLY)
        client.update()

        assert len(client.data()) == 0

    def test_daily(self):
        client = DummyClient(0, Frequency.DAILY)
        client.update()

        assert len(client.data()) == 3

    def test_weekly(self):
        client = DummyClient(0, Frequency.WEEKLY)
        client.update()

        assert len(client.data()) == 3

    def test_monthly(self):
        client = DummyClient(0, Frequency.MONTHLY)
        client.update()

        assert len(client.data()) == 3
