import json
from datetime import date

from pygazpar.client import Client
from pygazpar.datasource import JsonFileDataSource, TestDataSource
from pygazpar.model import DailyReading, Frequency, PeriodReading


class TestClientReadings:  # pylint: disable=too-few-public-methods

    # ------------------------------------------------------
    def test_load_readings_since_returns_models(self):
        readings = Client(TestDataSource()).load_readings_since("0", 365, [Frequency.DAILY, Frequency.MONTHLY])

        assert readings[Frequency.DAILY.value]
        assert all(isinstance(reading, DailyReading) for reading in readings[Frequency.DAILY.value])
        assert all(isinstance(reading, PeriodReading) for reading in readings[Frequency.MONTHLY.value])

    # ------------------------------------------------------
    def test_readings_are_the_models_of_the_dict_form(self):
        client = Client(TestDataSource())
        start_date, end_date = date(2020, 1, 1), date(2021, 1, 1)

        readings = client.load_readings_date_range("0", start_date, end_date, [Frequency.MONTHLY])
        rows = client.load_date_range("0", start_date, end_date, [Frequency.MONTHLY])

        assert [reading.model_dump(by_alias=True) for reading in readings[Frequency.MONTHLY.value]] == rows[
            Frequency.MONTHLY.value
        ]


class TestFileDataSourceReadings:  # pylint: disable=too-few-public-methods

    # ------------------------------------------------------
    def test_file_datasource_readings_are_models_and_load_gives_their_dict_form(self):
        with open("tests/resources/donnees_publiees.json", encoding="utf-8") as sample_file:
            pce_identifier = next(iter(json.load(sample_file)))
        datasource = JsonFileDataSource("tests/resources/donnees_publiees.json", "tests/resources/temperatures.json")
        start_date, end_date = date(2020, 1, 1), date(2021, 1, 1)

        readings = datasource.readings(pce_identifier, start_date, end_date, [Frequency.DAILY])
        rows = datasource.load(pce_identifier, start_date, end_date, [Frequency.DAILY])

        assert all(isinstance(reading, DailyReading) for reading in readings[Frequency.DAILY.value])
        # Each call reads the file again, so the timestamps differ: they are left out of the comparison.
        models = [
            {k: v for k, v in reading.model_dump(by_alias=True).items() if k != "timestamp"}
            for reading in readings[Frequency.DAILY.value]
        ]
        dicts = [{k: v for k, v in row.items() if k != "timestamp"} for row in rows[Frequency.DAILY.value]]
        assert models == dicts
