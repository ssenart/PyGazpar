import os
from pygazpar.datasource import TestDataSource, JsonFileDataSource, ExcelFileDataSource, JsonWebDataSource
from pygazpar.enum import Frequency
from datetime import date, timedelta
from dotenv import load_dotenv


class TestAllDataSource:

    # ------------------------------------------------------
    @classmethod
    def setup_class(cls):
        """ setup any state specific to the execution of the given class (which
        usually contains tests).
        """

    # ------------------------------------------------------
    @classmethod
    def teardown_class(cls):
        """ teardown any state that was previously setup with a call to
        setup_class.
        """

    # ------------------------------------------------------
    def setup_method(self):
        """ setup any state tied to the execution of the given method in a
        class.  setup_method is invoked for every test method of a class.
        """
        tmpdir = os.path.normpath(f"{os.getcwd()}/tmp")

        # We create the tmp directory if not already exists.
        if not os.path.exists(tmpdir):
            os.mkdir(tmpdir)

        load_dotenv()

        self.__username = os.environ["GRDF_USERNAME"]
        self.__password = os.environ["GRDF_PASSWORD"]
        self.__pceIdentifier = os.environ["PCE_IDENTIFIER"]
        self.__tmp_directory = tmpdir

    # ------------------------------------------------------
    def teardown_method(self):
        """ teardown any state that was previously setup with a setup_method
        call.
        """

    # ------------------------------------------------------
    def test_daily_test_sample(self):

        dataSource = TestDataSource()

        endDate = date.today()
        startDate = endDate + timedelta(days=-365)

        data = dataSource.load(self.__pceIdentifier, startDate, endDate, Frequency.DAILY)

        assert (len(data) == 711)

    # ------------------------------------------------------
    def test_daily_jsonfile_sample(self):

        dataSource = JsonFileDataSource("tests/resources/donnees_informatives.json")

        endDate = date.today()
        startDate = endDate + timedelta(days=-365)

        data = dataSource.load(self.__pceIdentifier, startDate, endDate, Frequency.DAILY)

        assert (len(data) == 1096)

    # ------------------------------------------------------
    def test_daily_excelfile_sample(self):

        dataSource = ExcelFileDataSource("tests/resources/Donnees_informatives_PCE_DAILY.xlsx")

        endDate = date.today()
        startDate = endDate + timedelta(days=-365)

        data = dataSource.load(self.__pceIdentifier, startDate, endDate, Frequency.DAILY)

        assert (len(data) == 363)

    # ------------------------------------------------------
    def test_daily_jsonweb(self):

        dataSource = JsonWebDataSource(self.__username, self.__password)

        endDate = date.today()
        startDate = endDate + timedelta(days=-365)

        data = dataSource.load(self.__pceIdentifier, startDate, endDate, Frequency.DAILY)

        assert (len(data) > 0)
