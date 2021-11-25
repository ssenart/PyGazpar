from pygazpar.datafileparser import DataFileParser
from pygazpar.enum import Frequency


class TestDataFileParser:

    def test_daily_sample(self):
        data = DataFileParser.parse("tests/resources/Donnees_informatives_PCE_DAILY.xlsx", Frequency.DAILY, 10)
        assert(len(data) == 10)

        data = DataFileParser.parse("tests/resources/Donnees_informatives_PCE_DAILY.xlsx", Frequency.DAILY, 0)
        assert(len(data) == 363)

    def test_weekly_sample(self):
        data = DataFileParser.parse("tests/resources/Donnees_informatives_PCE_WEEKLY.xlsx", Frequency.WEEKLY, 10)
        assert(len(data) == 10)

        data = DataFileParser.parse("tests/resources/Donnees_informatives_PCE_WEEKLY.xlsx", Frequency.WEEKLY, 0)
        assert(len(data) == 53)

    def test_monthly_sample(self):
        data = DataFileParser.parse("tests/resources/Donnees_informatives_PCE_MONTHLY.xlsx", Frequency.MONTHLY, 10)
        assert(len(data) == 10)

        data = DataFileParser.parse("tests/resources/Donnees_informatives_PCE_MONTHLY.xlsx", Frequency.MONTHLY, 0)
        assert(len(data) == 13)
