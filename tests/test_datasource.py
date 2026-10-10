import os
from datetime import date, timedelta

from dotenv import load_dotenv

from pygazpar.datasource import (
    ExcelFileDataSource,
    ExcelWebDataSource,
    JsonFileDataSource,
    JsonWebDataSource,
    TestDataSource,
)
from pygazpar.model import Frequency

PCE_IDENTIFIER = "12345678901234"


class TestAllDataSource:
    # ------------------------------------------------------
    @classmethod
    def setup_class(cls):
        """setup any state specific to the execution of the given class (which
        usually contains tests).
        """

    # ------------------------------------------------------
    @classmethod
    def teardown_class(cls):
        """teardown any state that was previously setup with a call to
        setup_class.
        """

    # ------------------------------------------------------
    def setup_method(self):
        """setup any state tied to the execution of the given method in a
        class.  setup_method is invoked for every test method of a class.
        """
        tmpdir = os.path.normpath(f"{os.getcwd()}/tmp")

        # We create the tmp directory if not already exists.
        if not os.path.exists(tmpdir):
            os.mkdir(tmpdir)

        load_dotenv()

        self._username = os.environ["GRDF_USERNAME"]
        self._password = os.environ["GRDF_PASSWORD"]
        self._pceIdentifier = os.environ["PCE_IDENTIFIER"]
        self._tmp_directory = tmpdir

    # ------------------------------------------------------
    def teardown_method(self):
        """teardown any state that was previously setup with a setup_method
        call.
        """

    # ------------------------------------------------------
    def test_sample(self):

        data_source = TestDataSource()

        end_date = date.today()
        start_date = end_date + timedelta(days=-365)

        data = data_source.load(self._pceIdentifier, start_date, end_date)

        assert len(data[Frequency.DAILY.value]) == 711

        assert len(data[Frequency.WEEKLY.value]) == 102

        assert len(data[Frequency.MONTHLY.value]) == 24

        assert len(data[Frequency.YEARLY.value]) == 2

    # ------------------------------------------------------
    def test_jsonfile_sample(self):

        data_source = JsonFileDataSource(
            "tests/resources/donnees_informatives.json", "tests/resources/temperatures.json"
        )

        end_date = date.today()
        start_date = end_date + timedelta(days=-365)

        data = data_source.load(
            PCE_IDENTIFIER,
            start_date,
            end_date,
            [Frequency.DAILY, Frequency.WEEKLY, Frequency.MONTHLY, Frequency.YEARLY],
        )

        assert len(data[Frequency.DAILY.value]) == 1096

        # 156 weeks: the week of 30 December 2019 to 5 January 2020 is its own week.
        assert len(data[Frequency.WEEKLY.value]) == 156

        assert len(data[Frequency.MONTHLY.value]) == 36

        assert len(data[Frequency.YEARLY.value]) == 3

    # ------------------------------------------------------
    def test_daily_excelfile_sample(self):

        data_source = ExcelFileDataSource("tests/resources/Donnees_informatives_PCE_DAILY.xlsx")

        end_date = date.today()
        start_date = end_date + timedelta(days=-365)

        data = data_source.load(self._pceIdentifier, start_date, end_date, [Frequency.DAILY])

        assert len(data[Frequency.DAILY.value]) == 363

    # ------------------------------------------------------
    def test_weekly_excelfile_sample(self):

        data_source = ExcelFileDataSource("tests/resources/Donnees_informatives_PCE_WEEKLY.xlsx")

        end_date = date.today()
        start_date = end_date + timedelta(days=-365)

        data = data_source.load(self._pceIdentifier, start_date, end_date, [Frequency.WEEKLY])

        assert len(data[Frequency.WEEKLY.value]) == 53

    # ------------------------------------------------------
    def test_monthly_excelfile_sample(self):

        data_source = ExcelFileDataSource("tests/resources/Donnees_informatives_PCE_MONTHLY.xlsx")

        end_date = date.today()
        start_date = end_date + timedelta(days=-365)

        data = data_source.load(self._pceIdentifier, start_date, end_date, [Frequency.MONTHLY])

        assert len(data[Frequency.MONTHLY.value]) == 13

    # ------------------------------------------------------
    def test_yearly_excelfile_sample(self):

        data_source = ExcelFileDataSource("tests/resources/Donnees_informatives_PCE_DAILY.xlsx")

        end_date = date.today()
        start_date = end_date + timedelta(days=-365)

        data = data_source.load(self._pceIdentifier, start_date, end_date, [Frequency.YEARLY])

        assert len(data[Frequency.YEARLY.value]) == 1

    # ------------------------------------------------------
    def test_jsonweb(self):

        data_source = JsonWebDataSource(self._username, self._password)

        end_date = date.today()
        start_date = end_date + timedelta(days=-365)

        data = data_source.load(
            self._pceIdentifier,
            start_date,
            end_date,
            [Frequency.DAILY, Frequency.WEEKLY, Frequency.MONTHLY, Frequency.YEARLY],
        )

        assert len(data[Frequency.DAILY.value]) > 0

        assert len(data[Frequency.WEEKLY.value]) >= 51 and len(data[Frequency.WEEKLY.value]) <= 54

        assert len(data[Frequency.MONTHLY.value]) >= 11 and len(data[Frequency.MONTHLY.value]) <= 13

        assert len(data[Frequency.YEARLY.value]) >= 1

    # ------------------------------------------------------
    def test_excelweb(self):

        data_source = ExcelWebDataSource(self._username, self._password, self._tmp_directory)

        end_date = date.today()
        start_date = end_date + timedelta(days=-365)

        data = data_source.load(
            self._pceIdentifier,
            start_date,
            end_date,
            [Frequency.DAILY, Frequency.WEEKLY, Frequency.MONTHLY, Frequency.YEARLY],
        )

        assert len(data[Frequency.DAILY.value]) > 0

        assert len(data[Frequency.WEEKLY.value]) >= 51 and len(data[Frequency.WEEKLY.value]) <= 54

        assert len(data[Frequency.MONTHLY.value]) >= 12 and len(data[Frequency.MONTHLY.value]) <= 13

        assert len(data[Frequency.YEARLY.value]) >= 1
