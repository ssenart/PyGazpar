from pygazpar.excelparser import ExcelParser
from pygazpar.enum import Frequency


class TestDataFileParser:

    # ------------------------------------------------------
    def test_daily_sample(self):
        data = ExcelParser.parse("tests/resources/Donnees_informatives_PCE_DAILY.xlsx", Frequency.DAILY)
        assert (len(data) == 363)

    # ------------------------------------------------------
    def test_weekly_sample(self):
        data = ExcelParser.parse("tests/resources/Donnees_informatives_PCE_WEEKLY.xlsx", Frequency.WEEKLY)
        assert (len(data) == 53)

    # ------------------------------------------------------
    def test_monthly_sample(self):
        data = ExcelParser.parse("tests/resources/Donnees_informatives_PCE_MONTHLY.xlsx", Frequency.MONTHLY)
        assert (len(data) == 13)
