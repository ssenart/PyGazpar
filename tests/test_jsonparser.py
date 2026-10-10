import json
import logging
import random
from datetime import date, datetime, timedelta
from decimal import Decimal
from fractions import Fraction
from unittest.mock import Mock

from pygazpar.api_client import ConsumptionType
from pygazpar.datasource import JsonWebDataSource
from pygazpar.jsonparser import CALCULATED_TYPE, JsonParser
from pygazpar.model import PropertyName

PCE_IDENTIFIER = "12345678901234"


def period_dates(releve):
    """Returns the first day and the day after the last day of a published period."""

    return (
        datetime.fromisoformat(releve["dateDebutReleve"]).date(),
        datetime.fromisoformat(releve["dateFinReleve"]).date(),
    )


def rows_between(readings, start, end):
    """Returns the daily rows whose day is in [start, end)."""

    return [
        reading
        for reading in readings
        if start <= datetime.strptime(reading[PropertyName.TIME_PERIOD.value], "%d/%m/%Y").date() < end
    ]


def informative_record(day, index_start, index_end, coefficient=11.0):
    """Returns a measured GrDF informative record, one gas day with its indexes."""

    return {
        "journeeGaziere": day,
        "qualificationReleve": "Mesuré",
        "indexDebut": index_start,
        "indexFin": index_end,
        "volumeBrutConsomme": index_end - index_start,
        "energieConsomme": round((index_end - index_start) * coefficient),
        "coeffConversion": coefficient,
        "temperature": None,
    }


def no_data_record(day):
    """Returns a GrDF informative record without data for its day."""

    return {
        "journeeGaziere": day,
        "qualificationReleve": "Absence de Données",
        "indexDebut": None,
        "indexFin": None,
        "volumeBrutConsomme": None,
        "energieConsomme": None,
        "coeffConversion": None,
        "temperature": None,
    }


class TestJsonParser:
    # ------------------------------------------------------
    def test_informative_readings_use_gas_day(self):
        pce_identifier = PCE_IDENTIFIER
        data = {
            pce_identifier: {
                "releves": [
                    {
                        "journeeGaziere": "2026-07-23",
                        "dateFinReleve": "2026-07-24T06:00:00+02:00",
                        "indexDebut": 2159,
                        "indexFin": 2160,
                        "volumeBrutConsomme": 0.28,
                        "energieConsomme": 3.16,
                        "coeffConversion": 11.29,
                        "temperature": 24.29,
                        "qualificationReleve": "Mesuré",
                    }
                ]
            }
        }

        readings = JsonParser.parse(json.dumps(data), "null", pce_identifier)

        assert readings[0][PropertyName.TIME_PERIOD.value] == "23/07/2026"

    # ------------------------------------------------------
    def test_published_readings_are_split_by_day(self):
        with open("tests/resources/donnees_publiees.json", encoding="utf-8") as consumption_file:
            raw = consumption_file.read()

        readings = JsonParser.parse(raw, "null", PCE_IDENTIFIER)
        published = json.loads(raw)[PCE_IDENTIFIER]["releves"]

        assert len(readings) == 1850
        assert readings[0][PropertyName.TIME_PERIOD.value] == "10/10/2017"
        assert readings[-1][PropertyName.TIME_PERIOD.value] == "02/11/2022"
        assert (
            sum(r[PropertyName.VOLUME.value] for r in readings)
            == published[-1]["indexFin"] - published[0]["indexDebut"]
        )
        # The gap of October 2019 adds 1194 kWh to the published energy.
        assert (
            sum(r[PropertyName.ENERGY.value] for r in readings) == sum(r["energieConsomme"] for r in published) + 1194
        )
        assert all(r[PropertyName.TYPE.value] == CALCULATED_TYPE for r in readings)

    # ------------------------------------------------------
    def test_each_published_period_keeps_its_exact_volume_and_energy_sums(self):
        with open("tests/resources/donnees_publiees.json", encoding="utf-8") as consumption_file:
            raw = consumption_file.read()

        readings = JsonParser.parse(raw, "null", PCE_IDENTIFIER)
        published = json.loads(raw)[PCE_IDENTIFIER]["releves"]

        for releve in published:
            start, end = period_dates(releve)
            block = rows_between(readings, start, end)

            assert len(block) == (end - start).days
            assert sum(r[PropertyName.VOLUME.value] for r in block) == releve["volumeBrutConsomme"]
            assert sum(r[PropertyName.ENERGY.value] for r in block) == releve["energieConsomme"]

    # ------------------------------------------------------
    def test_split_rows_keep_index_difference_equal_to_volume_and_energy_close_to_volume_times_coefficient(self):
        pce_identifier = PCE_IDENTIFIER

        with open("tests/resources/donnees_publiees.json", encoding="utf-8") as consumption_file:
            raw = consumption_file.read()

        readings = JsonParser.parse(raw, "null", pce_identifier)

        for reading in readings:
            volume = reading[PropertyName.VOLUME.value]
            assert reading[PropertyName.END_INDEX.value] - reading[PropertyName.START_INDEX.value] == volume
            # Two-day periods in the sample are off by about 0.5 kWh in the publication itself, plus rounding.
            assert (
                abs(reading[PropertyName.ENERGY.value] - volume * reading[PropertyName.CONVERTER_FACTOR.value]) <= 1.5
            )

    # ------------------------------------------------------
    def test_published_period_is_spread_with_exact_sums_and_chained_indexes(self):
        pce_identifier = PCE_IDENTIFIER
        data = {
            pce_identifier: {
                "releves": [
                    {
                        "journeeGaziere": None,
                        "dateDebutReleve": "2026-01-01T06:00:00+00:00",
                        "dateFinReleve": "2026-01-04T06:00:00+00:00",
                        "indexDebut": 100,
                        "indexFin": 110,
                        "volumeBrutConsomme": 10,
                        "energieConsomme": 100,
                        "coeffConversion": 11.0,
                        "temperature": None,
                    }
                ]
            }
        }

        readings = JsonParser.parse(json.dumps(data), "null", pce_identifier)

        assert [r[PropertyName.TIME_PERIOD.value] for r in readings] == ["01/01/2026", "02/01/2026", "03/01/2026"]
        assert [r[PropertyName.VOLUME.value] for r in readings] == [3, 3, 4]
        assert [r[PropertyName.ENERGY.value] for r in readings] == [30, 30, 40]
        assert [r[PropertyName.START_INDEX.value] for r in readings] == [100, 103, 106]
        assert [r[PropertyName.END_INDEX.value] for r in readings] == [103, 106, 110]
        assert all(r[PropertyName.TYPE.value] == CALCULATED_TYPE for r in readings)

    # ------------------------------------------------------
    def test_published_period_takes_the_meteo_temperature_of_each_day(self):
        pce_identifier = PCE_IDENTIFIER
        data = {
            pce_identifier: {
                "releves": [
                    {
                        "journeeGaziere": None,
                        "dateDebutReleve": "2026-01-01T06:00:00+00:00",
                        "dateFinReleve": "2026-01-03T06:00:00+00:00",
                        "indexDebut": 100,
                        "indexFin": 104,
                        "volumeBrutConsomme": 4,
                        "energieConsomme": 40,
                        "coeffConversion": 11.0,
                        "temperature": None,
                    }
                ]
            }
        }

        readings = JsonParser.parse(json.dumps(data), json.dumps({"2026-01-02": 5.5}), pce_identifier)

        assert [r[PropertyName.TEMPERATURE.value] for r in readings] == [None, 5.5]

    # ------------------------------------------------------
    def test_published_period_without_days_is_ignored(self):
        pce_identifier = PCE_IDENTIFIER
        data = {
            pce_identifier: {
                "releves": [
                    {
                        "journeeGaziere": None,
                        "dateDebutReleve": "2026-01-01T06:00:00+00:00",
                        "dateFinReleve": "2026-01-01T06:00:00+00:00",
                        "indexDebut": 100,
                        "indexFin": 100,
                        "volumeBrutConsomme": 0,
                        "energieConsomme": 0,
                        "coeffConversion": 11.0,
                        "temperature": None,
                    }
                ]
            }
        }

        readings = JsonParser.parse(json.dumps(data), "null", pce_identifier)

        assert readings == []

    # ------------------------------------------------------
    def test_readings_without_any_date_are_ignored(self):
        pce_identifier = PCE_IDENTIFIER
        data = {
            pce_identifier: {
                "releves": [
                    {
                        "journeeGaziere": None,
                        "dateFinReleve": None,
                        "temperature": None,
                    }
                ]
            }
        }

        readings = JsonParser.parse(json.dumps(data), "null", pce_identifier)

        assert readings == []

    # ------------------------------------------------------
    def test_split_volumes_of_a_published_period_differ_by_at_most_one_unit(self):
        with open("tests/resources/donnees_publiees.json", encoding="utf-8") as consumption_file:
            raw = consumption_file.read()

        readings = JsonParser.parse(raw, "null", PCE_IDENTIFIER)

        for releve in json.loads(raw)[PCE_IDENTIFIER]["releves"]:
            volumes = [r[PropertyName.VOLUME.value] for r in rows_between(readings, *period_dates(releve))]

            assert max(volumes) - min(volumes) <= 1

    # ------------------------------------------------------
    def test_split_energy_is_within_one_kwh_of_its_pro_rata_share(self):
        with open("tests/resources/donnees_publiees.json", encoding="utf-8") as consumption_file:
            raw = consumption_file.read()

        readings = JsonParser.parse(raw, "null", PCE_IDENTIFIER)

        for releve in json.loads(raw)[PCE_IDENTIFIER]["releves"]:
            volume = releve["volumeBrutConsomme"]
            if volume == 0:
                continue
            for reading in rows_between(readings, *period_dates(releve)):
                share = Fraction(releve["energieConsomme"] * reading[PropertyName.VOLUME.value], volume)
                assert abs(Fraction(reading[PropertyName.ENERGY.value]) - share) < 1

    # ------------------------------------------------------
    def test_random_periods_keep_the_volume_and_energy_invariants(self):
        pce_identifier = PCE_IDENTIFIER
        generator = random.Random(42)

        for _ in range(300):
            days = generator.randint(1, 60)
            volume = generator.randint(0, 5000)
            energy = generator.randint(0, 60000)
            start = date(2026, 1, 1) + timedelta(days=generator.randint(0, 365))
            index_start = generator.randint(0, 100000)
            releve = {
                "journeeGaziere": None,
                "dateDebutReleve": f"{start.isoformat()}T06:00:00+00:00",
                "dateFinReleve": f"{(start + timedelta(days=days)).isoformat()}T06:00:00+00:00",
                "indexDebut": index_start,
                "indexFin": index_start + volume,
                "volumeBrutConsomme": volume,
                "energieConsomme": energy,
                "coeffConversion": 11.0,
                "temperature": None,
            }

            readings = JsonParser.parse(json.dumps({pce_identifier: {"releves": [releve]}}), "null", pce_identifier)

            volumes = [r[PropertyName.VOLUME.value] for r in readings]
            energies = [r[PropertyName.ENERGY.value] for r in readings]
            assert len(readings) == days
            assert sum(volumes) == volume
            assert sum(energies) == energy
            assert max(volumes) - min(volumes) <= 1
            assert readings[0][PropertyName.START_INDEX.value] == index_start
            assert readings[-1][PropertyName.END_INDEX.value] == index_start + volume
            for before, after in zip(readings, readings[1:], strict=False):
                assert before[PropertyName.END_INDEX.value] == after[PropertyName.START_INDEX.value]
            for reading in readings:
                assert (
                    reading[PropertyName.END_INDEX.value] - reading[PropertyName.START_INDEX.value]
                    == reading[PropertyName.VOLUME.value]
                )
                if volume > 0:
                    share = Fraction(energy * reading[PropertyName.VOLUME.value], volume)
                    assert abs(Fraction(reading[PropertyName.ENERGY.value]) - share) < 1

    # ------------------------------------------------------
    def test_zero_volume_period_has_zero_energy(self):
        pce_identifier = PCE_IDENTIFIER
        releve = {
            "journeeGaziere": None,
            "dateDebutReleve": "2026-03-01T06:00:00+00:00",
            "dateFinReleve": "2026-03-03T06:00:00+00:00",
            "indexDebut": 500,
            "indexFin": 500,
            "volumeBrutConsomme": 0,
            "energieConsomme": 0,
            "coeffConversion": 11.0,
            "temperature": None,
        }

        readings = JsonParser.parse(json.dumps({pce_identifier: {"releves": [releve]}}), "null", pce_identifier)

        assert [r[PropertyName.VOLUME.value] for r in readings] == [0, 0]
        assert [r[PropertyName.ENERGY.value] for r in readings] == [0, 0]

    # ------------------------------------------------------
    def test_energy_without_volume_is_spread_evenly_over_the_days(self):
        pce_identifier = PCE_IDENTIFIER
        releve = {
            "journeeGaziere": None,
            "dateDebutReleve": "2026-03-01T06:00:00+00:00",
            "dateFinReleve": "2026-03-03T06:00:00+00:00",
            "indexDebut": 500,
            "indexFin": 500,
            "volumeBrutConsomme": 0,
            "energieConsomme": 5,
            "coeffConversion": 11.0,
            "temperature": None,
        }

        readings = JsonParser.parse(json.dumps({pce_identifier: {"releves": [releve]}}), "null", pce_identifier)

        assert [r[PropertyName.ENERGY.value] for r in readings] == [2, 3]

    # ------------------------------------------------------
    def test_decimal_period_is_split_in_the_precision_of_its_totals(self):
        pce_identifier = PCE_IDENTIFIER
        releve = {
            "journeeGaziere": None,
            "dateDebutReleve": "2026-01-01T06:00:00+00:00",
            "dateFinReleve": "2026-01-04T06:00:00+00:00",
            "indexDebut": 100,
            "indexFin": 110.3,
            "volumeBrutConsomme": 10.3,
            "energieConsomme": 100.5,
            "coeffConversion": 11.0,
            "temperature": None,
        }

        readings = JsonParser.parse(json.dumps({pce_identifier: {"releves": [releve]}}), "null", pce_identifier)

        assert [r[PropertyName.VOLUME.value] for r in readings] == [3.4, 3.4, 3.5]
        assert [r[PropertyName.ENERGY.value] for r in readings] == [33.1, 33.2, 34.2]
        assert sum(Decimal(str(r[PropertyName.VOLUME.value])) for r in readings) == Decimal("10.3")
        assert sum(Decimal(str(r[PropertyName.ENERGY.value])) for r in readings) == Decimal("100.5")
        assert readings[-1][PropertyName.END_INDEX.value] == 110.3

    # ------------------------------------------------------
    def test_random_decimal_periods_keep_exact_sums(self):
        pce_identifier = PCE_IDENTIFIER
        generator = random.Random(7)

        for _ in range(200):
            days = generator.randint(1, 40)
            volume_tenths = generator.randint(0, 50000)
            energy_tenths = generator.randint(0, 600000)
            start = date(2026, 1, 1) + timedelta(days=generator.randint(0, 365))
            releve = {
                "journeeGaziere": None,
                "dateDebutReleve": f"{start.isoformat()}T06:00:00+00:00",
                "dateFinReleve": f"{(start + timedelta(days=days)).isoformat()}T06:00:00+00:00",
                "indexDebut": 0,
                "indexFin": volume_tenths / 10,
                "volumeBrutConsomme": volume_tenths / 10,
                "energieConsomme": energy_tenths / 10,
                "coeffConversion": 11.0,
                "temperature": None,
            }

            readings = JsonParser.parse(json.dumps({pce_identifier: {"releves": [releve]}}), "null", pce_identifier)

            volumes = [Decimal(str(r[PropertyName.VOLUME.value])) for r in readings]
            energies = [Decimal(str(r[PropertyName.ENERGY.value])) for r in readings]
            assert len(readings) == days
            assert sum(volumes) == Decimal(volume_tenths) / 10
            assert sum(energies) == Decimal(energy_tenths) / 10
            assert max(volumes) - min(volumes) <= Decimal("0.1")
            assert Decimal(str(readings[-1][PropertyName.END_INDEX.value])) == Decimal(volume_tenths) / 10
            for reading, volume, energy in zip(readings, volumes, energies, strict=True):
                assert Decimal(str(reading[PropertyName.END_INDEX.value])) - Decimal(
                    str(reading[PropertyName.START_INDEX.value])
                ) == Decimal(str(reading[PropertyName.VOLUME.value]))
                if volume_tenths:
                    share = Fraction(str(volume)) * Fraction(energy_tenths, volume_tenths)
                    assert abs(Fraction(str(energy)) - share) < Fraction(1, 10)

    # ------------------------------------------------------
    def test_published_periods_that_do_not_chain_log_one_warning(self, caplog):
        with open("tests/resources/donnees_publiees.json", encoding="utf-8") as consumption_file:
            raw = consumption_file.read()

        with caplog.at_level(logging.WARNING, logger="pygazpar.jsonparser"):
            JsonParser.parse(raw, "null", PCE_IDENTIFIER)

        warnings = [record.getMessage() for record in caplog.records if "do not chain" in record.getMessage()]
        assert len(warnings) == 1
        assert "2019-10-03" in warnings[0]
        assert "107" in warnings[0]

    # ------------------------------------------------------
    def test_chained_published_periods_log_no_warning(self, caplog):
        releves = [
            {
                "journeeGaziere": None,
                "dateDebutReleve": "2026-01-01T06:00:00+00:00",
                "dateFinReleve": "2026-01-03T06:00:00+00:00",
                "indexDebut": 100,
                "indexFin": 104,
                "volumeBrutConsomme": 4,
                "energieConsomme": 44,
                "coeffConversion": 11.0,
                "temperature": None,
            },
            {
                "journeeGaziere": None,
                "dateDebutReleve": "2026-01-03T06:00:00+00:00",
                "dateFinReleve": "2026-01-05T06:00:00+00:00",
                "indexDebut": 104,
                "indexFin": 108,
                "volumeBrutConsomme": 4,
                "energieConsomme": 44,
                "coeffConversion": 11.0,
                "temperature": None,
            },
        ]

        with caplog.at_level(logging.WARNING, logger="pygazpar.jsonparser"):
            JsonParser.parse(json.dumps({PCE_IDENTIFIER: {"releves": releves}}), "null", PCE_IDENTIFIER)

        assert not [record for record in caplog.records if "do not chain" in record.getMessage()]

    # ------------------------------------------------------
    def test_gap_between_published_periods_is_rebuilt_from_the_indexes(self):
        with open("tests/resources/donnees_publiees.json", encoding="utf-8") as consumption_file:
            raw = consumption_file.read()

        readings = JsonParser.parse(raw, "null", PCE_IDENTIFIER)
        gap = rows_between(readings, date(2019, 10, 3), date(2019, 11, 3))

        assert len(gap) == 31
        assert gap[0][PropertyName.START_INDEX.value] == 9996
        assert gap[-1][PropertyName.END_INDEX.value] == 10103
        assert sum(r[PropertyName.VOLUME.value] for r in gap) == 107
        assert sum(r[PropertyName.ENERGY.value] for r in gap) == 1194
        assert all(abs(r[PropertyName.CONVERTER_FACTOR.value] - 11.16) < 1e-9 for r in gap)
        assert all(r[PropertyName.TYPE.value] == CALCULATED_TYPE for r in gap)
        for before, after in zip(gap, gap[1:], strict=False):
            assert before[PropertyName.END_INDEX.value] == after[PropertyName.START_INDEX.value]

    # ------------------------------------------------------
    def test_synthetic_gap_is_rebuilt_from_the_index_difference(self):
        releves = [
            {
                "journeeGaziere": None,
                "dateDebutReleve": "2026-01-01T06:00:00+00:00",
                "dateFinReleve": "2026-01-03T06:00:00+00:00",
                "indexDebut": 100,
                "indexFin": 104,
                "volumeBrutConsomme": 4,
                "energieConsomme": 44,
                "coeffConversion": 11.0,
                "temperature": None,
            },
            {
                "journeeGaziere": None,
                "dateDebutReleve": "2026-01-06T06:00:00+00:00",
                "dateFinReleve": "2026-01-08T06:00:00+00:00",
                "indexDebut": 110,
                "indexFin": 114,
                "volumeBrutConsomme": 4,
                "energieConsomme": 44,
                "coeffConversion": 11.2,
                "temperature": None,
            },
        ]

        readings = JsonParser.parse(json.dumps({PCE_IDENTIFIER: {"releves": releves}}), "null", PCE_IDENTIFIER)
        gap = rows_between(readings, date(2026, 1, 3), date(2026, 1, 6))

        assert [r[PropertyName.TIME_PERIOD.value] for r in gap] == ["03/01/2026", "04/01/2026", "05/01/2026"]
        assert sum(r[PropertyName.VOLUME.value] for r in gap) == 6
        assert sum(r[PropertyName.ENERGY.value] for r in gap) == 67
        assert all(abs(r[PropertyName.CONVERTER_FACTOR.value] - 11.1) < 1e-9 for r in gap)

    # ------------------------------------------------------
    def test_informative_day_without_data_is_rebuilt_from_the_indexes(self):
        releves = [
            informative_record("2026-01-01", 100, 104),
            no_data_record("2026-01-02"),
            informative_record("2026-01-03", 108, 112),
        ]

        readings = JsonParser.parse(json.dumps({PCE_IDENTIFIER: {"releves": releves}}), "null", PCE_IDENTIFIER)
        day = rows_between(readings, date(2026, 1, 2), date(2026, 1, 3))

        assert len(day) == 1
        assert day[0][PropertyName.START_INDEX.value] == 104
        assert day[0][PropertyName.END_INDEX.value] == 108
        assert day[0][PropertyName.VOLUME.value] == 4
        assert day[0][PropertyName.ENERGY.value] == 44
        assert day[0][PropertyName.TYPE.value] == CALCULATED_TYPE
        assert readings[0][PropertyName.TYPE.value] == "Mesuré"
        assert readings[-1][PropertyName.TYPE.value] == "Mesuré"

    # ------------------------------------------------------
    def test_informative_day_without_data_at_the_start_stays_without_data(self):
        releves = [no_data_record("2026-01-01"), informative_record("2026-01-02", 100, 104)]

        readings = JsonParser.parse(json.dumps({PCE_IDENTIFIER: {"releves": releves}}), "null", PCE_IDENTIFIER)

        assert readings[0][PropertyName.TYPE.value] == "Absence de Données"
        assert readings[0][PropertyName.VOLUME.value] is None
        assert readings[1][PropertyName.TYPE.value] == "Mesuré"


class TestJsonWebDataSource:
    # ------------------------------------------------------
    def test_requested_consumption_type_is_forwarded_to_api(self):
        data_source = JsonWebDataSource("user@example.com", "password", ConsumptionType.PUBLISHED)
        api_client = Mock()
        api_client.get_pce_consumption.return_value = {}
        api_client.get_pce_meteo.return_value = None
        data_source._api_client = api_client

        data_source._load_from_session(
            PCE_IDENTIFIER,
            date(2023, 7, 27),
            date(2026, 7, 25),
        )

        api_client.get_pce_consumption.assert_called_once_with(
            ConsumptionType.PUBLISHED,
            date(2023, 7, 27),
            date(2026, 7, 25),
            [PCE_IDENTIFIER],
        )
