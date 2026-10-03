from datetime import date, timedelta

from pygazpar.datasource import FrequencyConverter
from pygazpar.enum import PropertyName


def daily_rows(first_day: date, days: int, volume: int = 1, energy: int = 11) -> list[dict]:
    rows = []
    for index in range(days):
        day = first_day + timedelta(days=index)
        rows.append(
            {
                PropertyName.TIME_PERIOD.value: day.strftime("%d/%m/%Y"),
                PropertyName.START_INDEX.value: index,
                PropertyName.END_INDEX.value: index + volume,
                PropertyName.VOLUME.value: volume,
                PropertyName.ENERGY.value: energy,
                PropertyName.CONVERTER_FACTOR.value: 11.0,
                PropertyName.TEMPERATURE.value: None,
                PropertyName.TYPE.value: "Calculé",
                PropertyName.TIMESTAMP.value: "2026-01-01T00:00:00",
            }
        )
    return rows


class TestFrequencyConverter:  # pylint: disable=too-few-public-methods

    # ------------------------------------------------------
    def test_incomplete_first_month_is_dropped_and_last_month_is_kept(self):

        rows = daily_rows(date(2026, 1, 20), 27)

        monthly = FrequencyConverter.computeMonthly(rows)

        assert [(r[PropertyName.TIME_PERIOD.value], r[PropertyName.VOLUME.value]) for r in monthly] == [
            ("Février 2026", 15),
        ]
