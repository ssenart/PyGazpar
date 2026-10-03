from datetime import date

from pygazpar.excelparser import ExcelParser
from pygazpar.model import Frequency


class TestExcelReadings:  # pylint: disable=too-few-public-methods

    # ------------------------------------------------------
    def test_weekly_dates_come_from_the_label(self):
        rows = ExcelParser.parse("tests/resources/Donnees_informatives_PCE_WEEKLY.xlsx", Frequency.WEEKLY)

        assert rows[0].start_date == date(2020, 11, 24)
        assert rows[0].end_date == date(2020, 11, 30)
        assert rows[0].time_period == "Du 24/11/2020 au 29/11/2020"

    # ------------------------------------------------------
    def test_empty_cells_stay_empty_values(self):
        rows = ExcelParser.parse("tests/resources/Donnees_informatives_PCE_DAILY.xlsx", Frequency.DAILY)

        assert any(row.start_index_m3 is None for row in rows)
        assert all(row.converter_factor_kwh_m3 is None for row in rows)
