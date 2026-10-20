"""The samples are documentation that runs: they must keep working as the library changes."""

from datetime import date
from decimal import Decimal
from pathlib import Path
from unittest import mock

import pytest

from pygazpar.api_client import APIClient
from pygazpar.errors import LoginError, RateLimitError
from pygazpar.grdf import GrdfPce, GrdfPceConsumption
from samples import excelSample, jsonSample, offlineFilesSample, publishedSample, rawSample, testSample

PCE = "12345678901234"
RESOURCES = Path(__file__).parent / "resources"


@pytest.fixture(autouse=True)
def environment(monkeypatch):
    """Fake credentials, and no .env file: the developer's own must not reach the tests."""

    monkeypatch.setattr("dotenv.load_dotenv", lambda *_args, **_kwargs: False)
    monkeypatch.setenv("GRDF_USERNAME", "user@example.com")
    monkeypatch.setenv("GRDF_PASSWORD", "secret")
    monkeypatch.setenv("PCE_IDENTIFIER", PCE)


def record(day: str) -> dict:
    return {
        "journeeGaziere": day,
        "dateDebutReleve": f"{day}T06:00:00+00:00",
        "dateFinReleve": f"{day[:8]}{int(day[8:]) + 1:02d}T06:00:00+00:00",
        "indexDebut": Decimal(10),
        "indexFin": Decimal(12),
        "volumeBrutConsomme": Decimal(2),
        "energieConsomme": Decimal(22),
        "coeffConversion": Decimal("11.2"),
        "qualificationReleve": "Mesuré",
    }


def grdf(**patches):
    """Patches the GrDF calls of the web samples, and returns the patches by name."""

    consumption = {PCE: GrdfPceConsumption(idPce=PCE, frequence=None, releves=[record("2026-01-02")])}
    defaults = {
        "login": None,
        "is_logged_in": True,
        "logout": None,
        "get_pce_list": [GrdfPce.model_validate({"idObject": PCE})],
        "get_pce_consumption": consumption,
        "get_pce_consumption_raw": {PCE: {"idPce": PCE, "frequence": None, "releves": [record("2026-01-02")]}},
        "get_pce_meteo": {date(2026, 1, 2): 5.5},
        "get_pce_meteo_raw": {"2026-01-02": 5.5},
    }
    defaults.update(patches)
    return {name: mock.patch.object(APIClient, name, return_value=value) for name, value in defaults.items()}


class Patched:
    def __init__(self, **patches):
        self._patches = grdf(**patches)
        self.mocks: dict[str, mock.MagicMock] = {}

    def __enter__(self):
        self.mocks = {name: patch.start() for name, patch in self._patches.items()}
        return self.mocks

    def __exit__(self, *_args):
        for patch in self._patches.values():
            patch.stop()


# ------------------------------------------------------------------------------------------------------------
class TestOfflineSamples:
    # ------------------------------------------------------
    def test_test_sample(self, capsys):

        assert testSample.main() == 0
        assert "daily:" in capsys.readouterr().out

    # ------------------------------------------------------
    def test_offline_files_sample_with_json_files(self, capsys):
        argv = ["sample", str(RESOURCES / "donnees_informatives.json"), str(RESOURCES / "temperatures.json")]

        assert offlineFilesSample.main(argv) == 0
        assert "daily: 1096 readings" in capsys.readouterr().out

    # ------------------------------------------------------
    def test_offline_files_sample_with_an_excel_file(self, capsys):
        argv = ["sample", str(RESOURCES / "Donnees_informatives_PCE_DAILY.xlsx")]

        assert offlineFilesSample.main(argv) == 0
        assert "daily:" in capsys.readouterr().out

    # ------------------------------------------------------
    def test_offline_files_sample_explains_its_usage(self, capsys):

        assert offlineFilesSample.main(["sample"]) == 2
        assert "python -m samples.offlineFilesSample" in capsys.readouterr().err

    # ------------------------------------------------------
    def test_offline_files_sample_reports_a_missing_file(self, capsys):

        assert offlineFilesSample.main(["sample", "missing.json", "missing-too.json"]) == 1
        assert "Cannot read the file" in capsys.readouterr().err


# ------------------------------------------------------------------------------------------------------------
class TestWebSamples:
    # ------------------------------------------------------
    @pytest.mark.parametrize("sample", [jsonSample, excelSample])
    def test_a_sample_logs_out_even_though_it_fails(self, sample, capsys):

        with Patched() as mocks:
            mocks["get_pce_list"].side_effect = LoginError("bad credentials", 401)
            assert sample.main() == 1

        mocks["logout"].assert_called()
        assert "refused the login" in capsys.readouterr().err

    # ------------------------------------------------------
    def test_json_sample_prints_the_readings(self, capsys):

        with Patched() as mocks:
            assert jsonSample.main() == 0

        mocks["logout"].assert_called_once()
        assert "daily:" in capsys.readouterr().out

    # ------------------------------------------------------
    def test_json_sample_uses_the_only_pce_of_the_account(self, monkeypatch):
        monkeypatch.delenv("PCE_IDENTIFIER")

        with Patched() as mocks:
            assert jsonSample.main() == 0

        assert mocks["get_pce_consumption"].call_args.args[3] == [PCE]

    # ------------------------------------------------------
    def test_json_sample_asks_for_a_pce_when_there_are_several(self, monkeypatch, capsys):
        monkeypatch.delenv("PCE_IDENTIFIER")
        two = [GrdfPce.model_validate({"idObject": PCE}), GrdfPce.model_validate({"idObject": "99999999999999"})]

        with Patched(get_pce_list=two):
            assert jsonSample.main() == 2

        assert "PCE_IDENTIFIER" in capsys.readouterr().err

    # ------------------------------------------------------
    def test_a_missing_credential_is_explained(self, monkeypatch, capsys):
        monkeypatch.delenv("GRDF_PASSWORD")

        assert jsonSample.main() == 2
        assert "GRDF_PASSWORD" in capsys.readouterr().err

    # ------------------------------------------------------
    def test_rate_limit_is_explained(self, capsys):

        with Patched() as mocks:
            mocks["get_pce_list"].side_effect = RateLimitError("slow down")
            assert jsonSample.main() == 1

        assert "limiting" in capsys.readouterr().err

    # ------------------------------------------------------
    def test_published_sample_reads_the_published_consumption_for_a_date_range(self, capsys):

        with Patched() as mocks:
            assert publishedSample.main() == 0

        assert mocks["get_pce_consumption"].call_args.args[0].value == "publiees"
        assert "days from" in capsys.readouterr().out

    # ------------------------------------------------------
    def test_raw_sample_prints_the_counts_of_the_raw_responses(self, capsys):

        with Patched() as mocks:
            assert rawSample.main() == 0

        mocks["logout"].assert_called()
        out = capsys.readouterr().out
        assert "1 records" in out
        assert "1 days of temperatures" in out
