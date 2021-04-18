from pygazpar.enum import Frequency
from pygazpar.client import Client
import os
import logging


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
        # We create the tmp directory if not already exists.
        if not os.path.exists("./tmp"):
            os.mkdir("./tmp")

        pygazparLogFile = "./tmp/pygazpar_unittest.log"
        if os.path.isfile(pygazparLogFile):
            os.remove(pygazparLogFile)

        # We remove the geckodriver log file
        geckodriverLogFile = "./tmp/pygazpar_geckodriver.log"
        if os.path.isfile(geckodriverLogFile):
            os.remove(geckodriverLogFile)

        # Setup logging.
        logging.basicConfig(level=logging.DEBUG, format="%(asctime)s %(levelname)s [%(name)s] %(message)s")

        self.__username = os.environ["GRDF_USERNAME"]
        self.__password = os.environ["GRDF_PASSWORD"]
        if os.name == 'nt':
            self.__webdriver = "./drivers/geckodriver.exe"
        else:
            self.__webdriver = "./drivers/geckodriver"
        self.__wait_time = 30
        self.__tmp_directory = "./tmp"

    def teardown_method(self, method):
        """ teardown any state that was previously setup with a setup_method
        call.
        """

    def test_daily(self):
        client = Client(self.__username, self.__password, self.__webdriver, self.__wait_time, self.__tmp_directory, 1, True, Frequency.DAILY)
        client.update()

        assert len(client.data()) == 1

    def test_weekly(self):
        client = Client(self.__username, self.__password, self.__webdriver, self.__wait_time, self.__tmp_directory, 1, True, Frequency.WEEKLY)
        client.update()

        assert len(client.data()) == 1

    def test_monthly(self):
        client = Client(self.__username, self.__password, self.__webdriver, self.__wait_time, self.__tmp_directory, 1, True, Frequency.MONTHLY)
        client.update()

        assert len(client.data()) == 1

    def test_empty(self):
        assert 1 == 1
