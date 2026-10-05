import json
import logging
from datetime import date
from decimal import Decimal

import pytest
from pydantic import ValidationError

from pygazpar.datasource import FrequencyConverter
from pygazpar.grdf import GrdfRecord
from pygazpar.jsonparser import JsonParser
from pygazpar.model import (
    MONTHS,
    DailyReading,
    Frequency,
    PeriodReading,
    PropertyName,
    period_label,
)

PCE_IDENTIFIER = "12345678901234"


def informative_record(day, volume=4, energy=44):
    return {
        "journeeGaziere": day,
        "qualificationReleve": "Mesuré",
        "indexDebut": 100,
        "indexFin": 100 + volume,
        "volumeBrutConsomme": volume,
        "energieConsomme": energy,
        "coeffConversion": 11.0,
        "temperature": None,
    }


def published_record(**overrides):
    record = {
        "journeeGaziere": None,
        "dateDebutReleve": "2026-01-01T06:00:00+00:00",
        "dateFinReleve": "2026-01-04T06:00:00+00:00",
        "indexDebut": 100,
        "indexFin": 104,
        "volumeBrutConsomme": 4,
        "energieConsomme": 44,
        "coeffConversion": 11.0,
        "temperature": None,
    }
    record.update(overrides)
    return record


class TestGrdfRecord:
    # ------------------------------------------------------
    @pytest.mark.parametrize(
        "path", ["tests/resources/donnees_informatives.json", "tests/resources/donnees_publiees.json"]
    )
    def test_every_sample_record_is_valid(self, path):
        with open(path, encoding="utf-8") as sample_file:
            data = json.load(sample_file)
        releves = data[next(iter(data))]["releves"]

        for releve in releves:
            GrdfRecord.model_validate(releve)

    # ------------------------------------------------------
    def test_published_period_without_indexes_is_rejected(self):
        with pytest.raises(ValidationError, match="needs its indexes"):
            GrdfRecord.model_validate(published_record(indexDebut=None))

    # ------------------------------------------------------
    def test_negative_volume_is_rejected(self):
        with pytest.raises(ValidationError, match="negative"):
            GrdfRecord.model_validate(informative_record("2026-01-02", volume=-1))

    # ------------------------------------------------------
    def test_empty_published_period_is_rejected(self):
        with pytest.raises(ValidationError, match="period is empty"):
            GrdfRecord.model_validate(published_record(dateFinReleve="2026-01-01T06:00:00+00:00"))

    # ------------------------------------------------------
    def test_unknown_fields_are_kept(self):
        record = GrdfRecord.model_validate(
            informative_record("2026-01-02") | {"natureReleve": "Informative Journalier"}
        )

        assert record.model_extra == {"natureReleve": "Informative Journalier"}

    # ------------------------------------------------------
    def test_decimal_text_is_kept_exactly(self):
        text = '{"journeeGaziere": "2026-01-02", "volumeBrutConsomme": 0.28, "energieConsomme": 3.16, "coeffConversion": 11.1}'

        record = GrdfRecord.model_validate(json.loads(text, parse_float=Decimal))

        assert record.volumeBrutConsomme == Decimal("0.28")
        assert record.energieConsomme == Decimal("3.16")


class TestReadings:
    # ------------------------------------------------------
    def test_daily_reading_dict_form_has_the_property_names_and_no_dates(self):
        reading = DailyReading.model_validate(
            {
                "start_date": date(2026, 1, 2),
                "end_date": date(2026, 1, 3),
                "frequency": Frequency.DAILY,
                "time_period": "02/01/2026",
                "start_index_m3": 100,
                "end_index_m3": 104,
                "volume_m3": 4,
                "energy_kwh": 44,
                "converter_factor_kwh/m3": 11.0,
                "temperature_degC": None,
                "type": "Calculé",
                "timestamp": "2026-01-03T00:00:00",
            }
        )

        dumped = reading.model_dump(by_alias=True)

        assert set(dumped) == {property_name.value for property_name in PropertyName}
        assert dumped["frequency"] == "daily"
        assert dumped["start_date"] == "2026-01-02"
        assert dumped["end_date"] == "2026-01-03"
        assert reading.start_date == date(2026, 1, 2)

    # ------------------------------------------------------
    def test_empty_period_reading_is_rejected(self):
        with pytest.raises(ValidationError, match="period is empty"):
            PeriodReading.model_validate(
                {
                    "start_date": date(2026, 1, 2),
                    "end_date": date(2026, 1, 2),
                    "frequency": Frequency.DAILY,
                    "time_period": "02/01/2026",
                    "start_index_m3": None,
                    "end_index_m3": None,
                    "volume_m3": None,
                    "energy_kwh": None,
                    "timestamp": "t",
                }
            )


class TestPartialPeriods:
    # ------------------------------------------------------
    def test_partial_first_week_of_a_file_is_a_valid_weekly_period(self):
        reading = PeriodReading.model_validate(
            {
                "start_date": date(2020, 11, 24),
                "end_date": date(2020, 11, 30),
                "frequency": Frequency.WEEKLY,
                "timestamp": "t",
            }
        )

        assert reading.time_period == "Du 24/11/2020 au 29/11/2020"


class TestParserSkipsInvalidRecords:
    # ------------------------------------------------------
    def test_invalid_record_is_skipped_with_a_warning(self, caplog):
        releves = [informative_record("2026-01-02"), informative_record("2026-01-03", volume=-1)]

        with caplog.at_level(logging.WARNING, logger="pygazpar.jsonparser"):
            rows = JsonParser.parse(json.dumps({PCE_IDENTIFIER: {"releves": releves}}), "null", PCE_IDENTIFIER)

        assert len(rows) == 1
        assert rows[0][PropertyName.TIME_PERIOD.value] == "02/01/2026"
        assert any("is invalid" in record.getMessage() for record in caplog.records)


class TestPeriodLabels:
    # ------------------------------------------------------
    def test_label_follows_the_frequency(self):
        assert period_label(Frequency.DAILY, date(2026, 1, 2), date(2026, 1, 3)) == "02/01/2026"
        assert period_label(Frequency.WEEKLY, date(2022, 1, 3), date(2022, 1, 10)) == "Du 03/01/2022 au 09/01/2022"
        assert period_label(Frequency.MONTHLY, date(2022, 11, 1), date(2022, 12, 1)) == "Novembre 2022"
        assert period_label(Frequency.YEARLY, date(2022, 1, 1), date(2023, 1, 1)) == "2022"

    # ------------------------------------------------------
    def test_month_names_are_the_converter_ones(self):
        assert MONTHS == FrequencyConverter.MONTHS

    # ------------------------------------------------------
    def test_mismatched_time_period_is_rejected(self):
        with pytest.raises(ValidationError, match="does not match"):
            DailyReading.model_validate(
                {
                    "start_date": date(2026, 1, 2),
                    "end_date": date(2026, 1, 3),
                    "frequency": Frequency.DAILY,
                    "time_period": "03/01/2026",
                    "start_index_m3": None,
                    "end_index_m3": None,
                    "volume_m3": None,
                    "energy_kwh": None,
                    "converter_factor_kwh/m3": None,
                    "temperature_degC": None,
                    "type": None,
                    "timestamp": "t",
                }
            )

    # ------------------------------------------------------
    def test_daily_reading_must_cover_one_day(self):
        with pytest.raises(ValidationError, match="not a daily period"):
            DailyReading.model_validate(
                {
                    "start_date": date(2026, 1, 2),
                    "end_date": date(2026, 1, 4),
                    "frequency": Frequency.DAILY,
                    "start_index_m3": None,
                    "end_index_m3": None,
                    "volume_m3": None,
                    "energy_kwh": None,
                    "converter_factor_kwh/m3": None,
                    "temperature_degC": None,
                    "type": None,
                    "timestamp": "t",
                }
            )

    # ------------------------------------------------------
    def test_weekly_period_must_stay_inside_one_week(self):
        with pytest.raises(ValidationError, match="not a weekly period"):
            PeriodReading.model_validate(
                {
                    "start_date": date(2022, 1, 4),
                    "end_date": date(2022, 1, 11),
                    "frequency": Frequency.WEEKLY,
                    "start_index_m3": None,
                    "end_index_m3": None,
                    "volume_m3": None,
                    "energy_kwh": None,
                    "timestamp": "t",
                }
            )
