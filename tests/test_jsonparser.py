import json
from datetime import date
from unittest.mock import Mock

from pygazpar.api_client import ConsumptionType
from pygazpar.datasource import JsonWebDataSource
from pygazpar.enum import PropertyName
from pygazpar.jsonparser import JsonParser


class TestJsonParser:

    # ------------------------------------------------------
    def test_informative_readings_use_gas_day(self):
        pce_identifier = "22423299474865"
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
    def test_published_readings_use_last_day_of_period(self):
        pce_identifier = "22423299474865"

        with open("tests/resources/donnees_publiees.json", encoding="utf-8") as consumption_file:
            readings = JsonParser.parse(consumption_file.read(), "null", pce_identifier)

        assert len(readings) == 87
        assert readings[0][PropertyName.TIME_PERIOD.value] == "08/04/2018"
        assert readings[0][PropertyName.ENERGY.value] == 22417
        assert readings[-1][PropertyName.TIME_PERIOD.value] == "02/11/2022"

    # ------------------------------------------------------
    def test_readings_without_any_date_are_ignored(self):
        pce_identifier = "22423299474865"
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


class TestJsonWebDataSource:  # pylint: disable=too-few-public-methods

    # ------------------------------------------------------
    def test_requested_consumption_type_is_forwarded_to_api(self):
        data_source = JsonWebDataSource("user@example.com", "password", ConsumptionType.PUBLISHED)
        api_client = Mock()
        api_client.get_pce_consumption.return_value = {}
        api_client.get_pce_meteo.return_value = None
        data_source._api_client = api_client  # pylint: disable=protected-access

        data_source._loadFromSession(  # pylint: disable=protected-access
            "22423299474865",
            date(2023, 7, 27),
            date(2026, 7, 25),
        )

        api_client.get_pce_consumption.assert_called_once_with(
            ConsumptionType.PUBLISHED,
            date(2023, 7, 27),
            date(2026, 7, 25),
            ["22423299474865"],
        )
