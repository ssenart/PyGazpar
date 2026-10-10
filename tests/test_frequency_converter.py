from datetime import date, timedelta

from pygazpar.datasource import FrequencyConverter
from pygazpar.model import DailyReading, Frequency


def daily_readings(first_day: date, days: int) -> list[DailyReading]:
    """Returns one day of consumption per day, with a volume of 1 m3 and an energy of 11 kWh."""

    return [
        DailyReading.model_validate(
            {
                "start_date": first_day + timedelta(days=index),
                "end_date": first_day + timedelta(days=index + 1),
                "frequency": Frequency.DAILY,
                "start_index_m3": index,
                "end_index_m3": index + 1,
                "volume_m3": 1,
                "energy_kwh": 11,
                "converter_factor_kwh/m3": 11.0,
                "temperature_degC": None,
                "type": "Calculé",
                "timestamp": "2026-01-01T00:00:00",
            }
        )
        for index in range(days)
    ]


class TestFrequencyConverter:
    # ------------------------------------------------------
    def test_incomplete_first_month_is_dropped_and_last_month_is_kept(self):

        monthly = FrequencyConverter.compute_monthly(daily_readings(date(2026, 1, 20), 27))

        assert [(reading.time_period, reading.volume_m3) for reading in monthly] == [("Février 2026", 15)]

    # ------------------------------------------------------
    def test_weeks_follow_the_calendar_across_the_year_boundary(self):

        weekly = FrequencyConverter.compute_weekly(daily_readings(date(2019, 12, 30), 14))

        assert [reading.time_period for reading in weekly] == [
            "Du 30/12/2019 au 05/01/2020",
            "Du 06/01/2020 au 12/01/2020",
        ]
        assert [reading.volume_m3 for reading in weekly] == [7, 7]
