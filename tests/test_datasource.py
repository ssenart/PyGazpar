import os
from pygazpar.datasource import TestDataSource, JsonFileDataSource, ExcelFileDataSource, JsonWebDataSource, ExcelWebDataSource
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
    def test_sample(self):

        dataSource = TestDataSource()

        endDate = date.today()
        startDate = endDate + timedelta(days=-365)

        data = dataSource.load(self.__pceIdentifier, startDate, endDate)

        assert (len(data[Frequency.DAILY.value]) == 711)

        assert (len(data[Frequency.WEEKLY.value]) == 102)

        assert (len(data[Frequency.MONTHLY.value]) == 24)

        assert (len(data[Frequency.YEARLY.value]) == 2)

    # ------------------------------------------------------
    def test_jsonfile_sample(self):

        dataSource = JsonFileDataSource("tests/resources/donnees_informatives.json", "tests/resources/temperatures.json")

        endDate = date.today()
        startDate = endDate + timedelta(days=-365)

        data = dataSource.load(self.__pceIdentifier, startDate, endDate, [Frequency.DAILY, Frequency.WEEKLY, Frequency.MONTHLY, Frequency.YEARLY])

        assert (len(data[Frequency.DAILY.value]) == 1096)

        assert (len(data[Frequency.WEEKLY.value]) == 155)

        assert (len(data[Frequency.MONTHLY.value]) == 37)

        assert (len(data[Frequency.YEARLY.value]) == 3)

    # ------------------------------------------------------
    def test_daily_excelfile_sample(self):

        dataSource = ExcelFileDataSource("tests/resources/Donnees_informatives_PCE_DAILY.xlsx")

        endDate = date.today()
        startDate = endDate + timedelta(days=-365)

        data = dataSource.load(self.__pceIdentifier, startDate, endDate, [Frequency.DAILY])

        assert (len(data[Frequency.DAILY.value]) == 363)

    # ------------------------------------------------------
    def test_weekly_excelfile_sample(self):

        dataSource = ExcelFileDataSource("tests/resources/Donnees_informatives_PCE_WEEKLY.xlsx")

        endDate = date.today()
        startDate = endDate + timedelta(days=-365)

        data = dataSource.load(self.__pceIdentifier, startDate, endDate, [Frequency.WEEKLY])

        assert (len(data[Frequency.WEEKLY.value]) == 53)

    # ------------------------------------------------------
    def test_monthly_excelfile_sample(self):

        dataSource = ExcelFileDataSource("tests/resources/Donnees_informatives_PCE_MONTHLY.xlsx")

        endDate = date.today()
        startDate = endDate + timedelta(days=-365)

        data = dataSource.load(self.__pceIdentifier, startDate, endDate, [Frequency.MONTHLY])

        assert (len(data[Frequency.MONTHLY.value]) == 13)

    # ------------------------------------------------------
    def test_yearly_excelfile_sample(self):

        dataSource = ExcelFileDataSource("tests/resources/Donnees_informatives_PCE_DAILY.xlsx")

        endDate = date.today()
        startDate = endDate + timedelta(days=-365)

        data = dataSource.load(self.__pceIdentifier, startDate, endDate, [Frequency.YEARLY])

        assert (len(data[Frequency.YEARLY.value]) == 1)

    # ------------------------------------------------------
    def test_jsonweb(self):

        dataSource = JsonWebDataSource(self.__username, self.__password)

        endDate = date.today()
        startDate = endDate + timedelta(days=-365)

        data = dataSource.load(self.__pceIdentifier, startDate, endDate, [Frequency.DAILY, Frequency.WEEKLY, Frequency.MONTHLY, Frequency.YEARLY])

        assert (len(data[Frequency.DAILY.value]) > 0)

        assert (len(data[Frequency.WEEKLY.value]) >= 51 and len(data[Frequency.WEEKLY.value]) <= 54)

        assert (len(data[Frequency.MONTHLY.value]) >= 12 and len(data[Frequency.MONTHLY.value]) <= 13)

        assert (len(data[Frequency.YEARLY.value]) == 1)

    # ------------------------------------------------------
    def test_excelweb(self):

        dataSource = ExcelWebDataSource(self.__username, self.__password, self.__tmp_directory)

        endDate = date.today()
        startDate = endDate + timedelta(days=-365)

        data = dataSource.load(self.__pceIdentifier, startDate, endDate, [Frequency.DAILY, Frequency.WEEKLY, Frequency.MONTHLY, Frequency.YEARLY])

        assert (len(data[Frequency.DAILY.value]) > 0)

        assert (len(data[Frequency.WEEKLY.value]) >= 51 and len(data[Frequency.WEEKLY.value]) <= 54)

        assert (len(data[Frequency.MONTHLY.value]) >= 12 and len(data[Frequency.MONTHLY.value]) <= 13)

        assert (len(data[Frequency.YEARLY.value]) == 1)
