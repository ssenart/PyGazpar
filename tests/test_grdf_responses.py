import json
from datetime import date
from unittest import mock

import pytest
from pydantic import ValidationError

from pygazpar.api_client import APIClient, ConsumptionType
from pygazpar.grdf import GrdfConsumptionResponse, GrdfMeteoResponse, GrdfPceList

PCE_IDENTIFIER = "12345678901234"


class TestGrdfResponses:
    # ------------------------------------------------------
    def test_sample_consumption_response_is_valid(self):
        with open("tests/resources/donnees_publiees.json", encoding="utf-8") as sample_file:
            GrdfConsumptionResponse.model_validate(json.load(sample_file))

    # ------------------------------------------------------
    def test_sample_meteo_response_is_valid(self):
        with open("tests/resources/temperatures.json", encoding="utf-8") as sample_file:
            GrdfMeteoResponse.model_validate(json.load(sample_file))

    # ------------------------------------------------------
    def test_consumption_without_records_is_rejected(self):
        with pytest.raises(ValidationError, match="releves"):
            GrdfConsumptionResponse.model_validate({PCE_IDENTIFIER: {"idPce": PCE_IDENTIFIER, "frequence": None}})

    # ------------------------------------------------------
    def test_meteo_with_text_is_rejected(self):
        with pytest.raises(ValidationError):
            GrdfMeteoResponse.model_validate({"2026-01-01": "warm"})

    # ------------------------------------------------------
    def test_pce_list_needs_identifiers(self):
        GrdfPceList.model_validate([{"idObject": PCE_IDENTIFIER}])

        with pytest.raises(ValidationError, match="idObject"):
            GrdfPceList.model_validate([{"name": "no identifier"}])


class TestApiClientValidation:
    # ------------------------------------------------------
    def test_malformed_consumption_is_rejected_at_the_boundary(self):
        response = mock.Mock()
        response.json.return_value = {PCE_IDENTIFIER: {"idPce": 1}}

        with mock.patch.object(APIClient, "get", return_value=response):
            with pytest.raises(ValidationError):
                APIClient("user", "password").get_pce_consumption(
                    ConsumptionType.INFORMATIVE, date(2026, 1, 1), date(2026, 1, 3), [PCE_IDENTIFIER]
                )

    # ------------------------------------------------------
    def test_valid_consumption_is_returned_unchanged(self):
        payload = {PCE_IDENTIFIER: {"idPce": PCE_IDENTIFIER, "frequence": None, "releves": []}}
        response = mock.Mock()
        response.json.return_value = payload

        with mock.patch.object(APIClient, "get", return_value=response):
            result = APIClient("user", "password").get_pce_consumption_raw(
                ConsumptionType.INFORMATIVE, date(2026, 1, 1), date(2026, 1, 3), [PCE_IDENTIFIER]
            )

        assert result is payload

    # ------------------------------------------------------
    def test_typed_consumption_is_a_model_per_pce(self):
        response = mock.Mock()
        response.json.return_value = {PCE_IDENTIFIER: {"idPce": PCE_IDENTIFIER, "frequence": None, "releves": []}}

        with mock.patch.object(APIClient, "get", return_value=response):
            result = APIClient("user", "password").get_pce_consumption(
                ConsumptionType.INFORMATIVE, date(2026, 1, 1), date(2026, 1, 3), [PCE_IDENTIFIER]
            )

        assert result[PCE_IDENTIFIER].releves == []
