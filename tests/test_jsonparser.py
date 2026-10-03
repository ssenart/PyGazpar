import json
import random
from datetime import date, datetime, timedelta
from decimal import Decimal
from fractions import Fraction
from unittest.mock import Mock

from pygazpar.api_client import ConsumptionType
from pygazpar.datasource import JsonWebDataSource
from pygazpar.enum import PropertyName
from pygazpar.jsonparser import CALCULATED_TYPE, JsonParser

PCE_IDENTIFIER = "12345678901234"


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
        pce_identifier = PCE_IDENTIFIER

        with open("tests/resources/donnees_publiees.json", encoding="utf-8") as consumption_file:
            raw = consumption_file.read()

        readings = JsonParser.parse(raw, "null", pce_identifier)
        published = json.loads(raw)[pce_identifier]["releves"]

        assert len(readings) == 1819
        assert readings[0][PropertyName.TIME_PERIOD.value] == "10/10/2017"
        assert readings[-1][PropertyName.TIME_PERIOD.value] == "02/11/2022"
        assert sum(r[PropertyName.VOLUME.value] for r in readings) == sum(r["volumeBrutConsomme"] for r in published)
        assert sum(r[PropertyName.ENERGY.value] for r in readings) == sum(r["energieConsomme"] for r in published)
        assert all(r[PropertyName.TYPE.value] == CALCULATED_TYPE for r in readings)

    # ------------------------------------------------------
    def test_each_published_period_keeps_its_exact_volume_and_energy_sums(self):
        pce_identifier = PCE_IDENTIFIER

        with open("tests/resources/donnees_publiees.json", encoding="utf-8") as consumption_file:
            raw = consumption_file.read()

        readings = JsonParser.parse(raw, "null", pce_identifier)
        published = json.loads(raw)[pce_identifier]["releves"]

        position = 0
        for releve in published:
            days = (
                datetime.fromisoformat(releve["dateFinReleve"]).date()
                - datetime.fromisoformat(releve["dateDebutReleve"]).date()
            ).days
            block = readings[position : position + days]
            position += days

            assert len(block) == days
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
        pce_identifier = PCE_IDENTIFIER

        with open("tests/resources/donnees_publiees.json", encoding="utf-8") as consumption_file:
            raw = consumption_file.read()

        readings = JsonParser.parse(raw, "null", pce_identifier)
        published = json.loads(raw)[pce_identifier]["releves"]

        position = 0
        for releve in published:
            days = (
                datetime.fromisoformat(releve["dateFinReleve"]).date()
                - datetime.fromisoformat(releve["dateDebutReleve"]).date()
            ).days
            volumes = [r[PropertyName.VOLUME.value] for r in readings[position : position + days]]
            position += days

            assert max(volumes) - min(volumes) <= 1

    # ------------------------------------------------------
    def test_split_energy_is_within_one_kwh_of_its_pro_rata_share(self):
        pce_identifier = PCE_IDENTIFIER

        with open("tests/resources/donnees_publiees.json", encoding="utf-8") as consumption_file:
            raw = consumption_file.read()

        readings = JsonParser.parse(raw, "null", pce_identifier)
        published = json.loads(raw)[pce_identifier]["releves"]

        position = 0
        for releve in published:
            days = (
                datetime.fromisoformat(releve["dateFinReleve"]).date()
                - datetime.fromisoformat(releve["dateDebutReleve"]).date()
            ).days
            block = readings[position : position + days]
            position += days

            volume = releve["volumeBrutConsomme"]
            if volume == 0:
                continue
            for reading in block:
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
            for before, after in zip(readings, readings[1:]):
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
            for reading, volume, energy in zip(readings, volumes, energies):
                assert Decimal(str(reading[PropertyName.END_INDEX.value])) - Decimal(
                    str(reading[PropertyName.START_INDEX.value])
                ) == Decimal(str(reading[PropertyName.VOLUME.value]))
                if volume_tenths:
                    share = Fraction(str(volume)) * Fraction(energy_tenths, volume_tenths)
                    assert abs(Fraction(str(energy)) - share) < Fraction(1, 10)


class TestJsonWebDataSource:  # pylint: disable=too-few-public-methods

    # ------------------------------------------------------
    def test_requested_consumption_type_is_forwarded_to_api(self):
        data_source = JsonWebDataSource("user@example.com", "password", ConsumptionType.PUBLISHED)
        api_client = Mock()
        api_client.get_pce_consumption.return_value = {}
        api_client.get_pce_meteo.return_value = None
        data_source._api_client = api_client  # pylint: disable=protected-access

        data_source._loadFromSession(  # pylint: disable=protected-access
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
