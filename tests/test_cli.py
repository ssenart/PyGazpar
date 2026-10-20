import csv
import io
import json
from datetime import date
from decimal import Decimal
from pathlib import Path
from unittest import mock

import pytest

pytest.importorskip("typer")

from typer.testing import CliRunner  # noqa: E402

from pygazpar.api_client import APIClient, ConsumptionType, GrdfFrequency  # noqa: E402
from pygazpar.cli.app import app  # noqa: E402
from pygazpar.cli.render import render_csv, render_json, render_ndjson  # noqa: E402
from pygazpar.errors import LoginError, RateLimitError  # noqa: E402
from pygazpar.grdf import GrdfPce, GrdfPceConsumption  # noqa: E402

PCE = "12345678901234"
RESOURCES = Path(__file__).parent / "resources"

runner = CliRunner()


@pytest.fixture(autouse=True)
def clean_environment(monkeypatch):
    """The credentials of the developer must not leak into the tests, nor the colors into the output."""

    for name in ("GRDF_USERNAME", "GRDF_PASSWORD", "PCE_IDENTIFIER"):
        monkeypatch.delenv(name, raising=False)
    monkeypatch.setenv("NO_COLOR", "1")


@pytest.fixture
def init_calls():
    """Records the arguments of every APIClient created, which still works as usual."""

    calls: list[tuple] = []
    real_init = APIClient.__init__

    def spy(self, *args, **kwargs):
        calls.append(args)
        real_init(self, *args, **kwargs)

    with mock.patch.object(APIClient, "__init__", spy):
        yield calls


def web(*args: str) -> list[str]:
    return [*args, "-u", "user@example.com", "-p", "secret"]


def pce_list() -> list[GrdfPce]:
    return [GrdfPce.model_validate({"idObject": PCE, "adresse": "1 rue du Gaz"})]


# ------------------------------------------------------------------------------------------------------------
class TestReadings:
    # ------------------------------------------------------
    def test_json_is_the_default_when_piped(self):

        result = runner.invoke(app, ["readings", "--datasource", "test", "-f", "monthly"])

        assert result.exit_code == 0
        assert list(json.loads(result.stdout)) == ["monthly"]

    # ------------------------------------------------------
    def test_several_frequencies_keep_the_order_asked(self):

        result = runner.invoke(app, ["readings", "--datasource", "test", "-f", "yearly", "-f", "DAILY"])

        assert list(json.loads(result.stdout)) == ["yearly", "daily"]

    # ------------------------------------------------------
    def test_all_stands_for_every_frequency_but_hourly(self):

        result = runner.invoke(app, ["readings", "--datasource", "test", "-f", "all"])

        assert list(json.loads(result.stdout)) == ["daily", "weekly", "monthly", "yearly"]

    # ------------------------------------------------------
    def test_a_daily_reading_has_the_documented_keys(self):

        result = runner.invoke(app, ["readings", "--datasource", "test", "-f", "daily"])

        assert list(json.loads(result.stdout)["daily"][0]) == [
            "start_date",
            "end_date",
            "frequency",
            "time_period",
            "start_index_m3",
            "end_index_m3",
            "volume_m3",
            "energy_kwh",
            "timestamp",
            "converter_factor_kwh_m3",
            "temperature_degC",
            "type",
        ]

    # ------------------------------------------------------
    def test_csv_has_one_header_and_the_frequency_column(self):

        result = runner.invoke(app, ["readings", "--datasource", "test", "-f", "all", "--format", "csv"])

        rows = list(csv.DictReader(io.StringIO(result.stdout)))
        assert {row["frequency"] for row in rows} == {"daily", "weekly", "monthly", "yearly"}

    # ------------------------------------------------------
    def test_ndjson_is_one_object_per_line(self):

        result = runner.invoke(app, ["readings", "--datasource", "test", "-f", "monthly", "--format", "ndjson"])

        lines = result.stdout.strip().split("\n")
        assert len(lines) > 1
        assert all(json.loads(line)["frequency"] == "monthly" for line in lines)

    # ------------------------------------------------------
    def test_table_has_no_ansi_codes_and_one_title_per_frequency(self, monkeypatch):
        monkeypatch.setenv("COLUMNS", "200")

        result = runner.invoke(app, ["readings", "--datasource", "test", "-f", "monthly", "--format", "table"])

        assert "\x1b[" not in result.stdout
        assert "monthly (" in result.stdout
        assert "kWh" in result.stdout
        assert "timestamp" not in result.stdout

    # ------------------------------------------------------
    def test_output_file_is_json_by_default(self, tmp_path):
        target = tmp_path / "out.json"

        result = runner.invoke(app, ["readings", "--datasource", "test", "-f", "daily", "-o", str(target)])

        assert result.exit_code == 0
        assert result.stdout == ""
        assert "daily" in json.loads(target.read_text(encoding="utf-8"))

    # ------------------------------------------------------
    def test_an_empty_frequency_is_reported_on_stderr_not_stdout(self):

        result = runner.invoke(app, ["readings", "--datasource", "test", "-f", "hourly"])

        assert json.loads(result.stdout) == {"hourly": []}
        assert "No hourly readings" in result.stderr

    # ------------------------------------------------------
    def test_the_date_range_is_forwarded(self):

        with (
            mock.patch.object(APIClient, "login"),
            mock.patch.object(APIClient, "logout"),
            mock.patch.object(APIClient, "get_pce_list", return_value=pce_list()),
            mock.patch.object(APIClient, "get_pce_consumption", return_value={}) as consumption,
            mock.patch.object(APIClient, "get_pce_meteo", return_value={}),
        ):
            result = runner.invoke(
                app, ["readings", *web(), "-c", PCE, "--start", "2026-01-01", "--end", "2026-01-31", "-f", "daily"]
            )

        assert result.exit_code == 0
        assert consumption.call_args.args[1:3] == (date(2026, 1, 1), date(2026, 1, 31))

    # ------------------------------------------------------
    def test_published_consumption_type_is_forwarded(self):

        with (
            mock.patch.object(APIClient, "login"),
            mock.patch.object(APIClient, "logout"),
            mock.patch.object(APIClient, "get_pce_list", return_value=pce_list()),
            mock.patch.object(APIClient, "get_pce_consumption", return_value={}) as consumption,
            mock.patch.object(APIClient, "get_pce_meteo", return_value={}),
        ):
            result = runner.invoke(app, ["readings", *web(), "-c", PCE, "--consumption-type", "PUBLISHED"])

        assert result.exit_code == 0
        assert consumption.call_args.args[0] == ConsumptionType.PUBLISHED

    # ------------------------------------------------------
    def test_the_only_pce_of_the_account_is_chosen(self):

        with (
            mock.patch.object(APIClient, "login"),
            mock.patch.object(APIClient, "logout"),
            mock.patch.object(APIClient, "get_pce_list", return_value=pce_list()),
            mock.patch.object(APIClient, "get_pce_consumption", return_value={}) as consumption,
            mock.patch.object(APIClient, "get_pce_meteo", return_value={}),
        ):
            result = runner.invoke(app, ["readings", *web()])

        assert result.exit_code == 0
        assert consumption.call_args.args[3] == [PCE]

    # ------------------------------------------------------
    def test_several_pces_need_a_choice(self):
        two = [*pce_list(), GrdfPce.model_validate({"idObject": "99999999999999"})]

        with (
            mock.patch.object(APIClient, "login"),
            mock.patch.object(APIClient, "logout"),
            mock.patch.object(APIClient, "get_pce_list", return_value=two),
        ):
            result = runner.invoke(app, ["readings", *web()])

        assert result.exit_code == 2
        assert "--pce" in result.stderr


# ------------------------------------------------------------------------------------------------------------
class TestUsageErrors:
    # ------------------------------------------------------
    def test_an_unknown_frequency_is_a_usage_error(self):

        result = runner.invoke(app, ["readings", "--datasource", "test", "-f", "fortnightly"])

        assert result.exit_code == 2
        assert "invalid value" in result.stderr

    # ------------------------------------------------------
    def test_last_days_excludes_start(self):

        result = runner.invoke(app, ["readings", "--datasource", "test", "-d", "3", "--start", "2026-01-01"])

        assert result.exit_code == 2

    # ------------------------------------------------------
    def test_a_malformed_date_is_a_usage_error(self):

        result = runner.invoke(app, ["readings", "--datasource", "test", "--start", "01/02/2026"])

        assert result.exit_code == 2
        assert "YYYY-MM-DD" in result.stderr

    # ------------------------------------------------------
    def test_a_start_after_the_end_is_a_usage_error(self):

        result = runner.invoke(
            app, ["readings", "--datasource", "test", "--start", "2026-02-01", "--end", "2026-01-01"]
        )

        assert result.exit_code == 2

    # ------------------------------------------------------
    def test_a_missing_username_is_a_usage_error(self):

        result = runner.invoke(app, ["readings"])

        assert result.exit_code == 2
        assert "GRDF_USERNAME" in result.stderr

    # ------------------------------------------------------
    def test_a_missing_password_is_a_usage_error_when_not_on_a_terminal(self):

        result = runner.invoke(app, ["readings", "-u", "user@example.com"])

        assert result.exit_code == 2
        assert "GRDF_PASSWORD" in result.stderr

    # ------------------------------------------------------
    def test_consumption_type_is_rejected_for_the_test_datasource(self):

        result = runner.invoke(app, ["readings", "--datasource", "test", "--consumption-type", "published"])

        assert result.exit_code == 2

    # ------------------------------------------------------
    def test_an_unknown_format_is_a_usage_error(self):

        result = runner.invoke(app, ["readings", "--datasource", "test", "--format", "xml"])

        assert result.exit_code == 2


# ------------------------------------------------------------------------------------------------------------
class TestCredentials:
    # ------------------------------------------------------
    def test_credentials_are_read_from_the_environment(self, monkeypatch, init_calls):
        monkeypatch.setenv("GRDF_USERNAME", "env@example.com")
        monkeypatch.setenv("GRDF_PASSWORD", "env-secret")
        monkeypatch.setenv("PCE_IDENTIFIER", PCE)

        with (
            mock.patch.object(APIClient, "login"),
            mock.patch.object(APIClient, "logout"),
            mock.patch.object(APIClient, "get_pce_list", return_value=pce_list()),
            mock.patch.object(APIClient, "get_pce_consumption", return_value={}) as consumption,
            mock.patch.object(APIClient, "get_pce_meteo", return_value={}),
        ):
            result = runner.invoke(app, ["readings"])

        assert result.exit_code == 0
        assert init_calls[0][:2] == ("env@example.com", "env-secret")
        assert consumption.call_args.args[3] == [PCE]

    # ------------------------------------------------------
    def test_the_command_line_takes_precedence_over_the_environment(self, monkeypatch, init_calls):
        monkeypatch.setenv("GRDF_USERNAME", "env@example.com")
        monkeypatch.setenv("GRDF_PASSWORD", "env-secret")

        with (
            mock.patch.object(APIClient, "login"),
            mock.patch.object(APIClient, "logout"),
            mock.patch.object(APIClient, "get_pce_list", return_value=pce_list()),
            mock.patch.object(APIClient, "get_pce_consumption", return_value={}),
            mock.patch.object(APIClient, "get_pce_meteo", return_value={}),
        ):
            result = runner.invoke(app, ["readings", "-u", "flag@example.com", "-p", "flag-secret"])

        assert result.exit_code == 0
        assert init_calls[0][:2] == ("flag@example.com", "flag-secret")

    # ------------------------------------------------------
    def test_the_password_can_come_from_stdin(self, init_calls):

        with (
            mock.patch.object(APIClient, "login"),
            mock.patch.object(APIClient, "logout"),
            mock.patch.object(APIClient, "get_pce_list", return_value=pce_list()),
            mock.patch.object(APIClient, "get_pce_consumption", return_value={}),
            mock.patch.object(APIClient, "get_pce_meteo", return_value={}),
        ):
            result = runner.invoke(
                app, ["readings", "-u", "user@example.com", "--password-stdin"], input="from-stdin\n"
            )

        assert result.exit_code == 0
        assert init_calls[0][:2] == ("user@example.com", "from-stdin")


# ------------------------------------------------------------------------------------------------------------
class TestExitCodes:
    # ------------------------------------------------------
    @pytest.mark.parametrize(
        ("error", "code"),
        [
            (LoginError("bad credentials", 401), 3),
            (RateLimitError("slow down"), 5),
        ],
    )
    def test_a_grdf_error_has_its_own_exit_code(self, error, code):

        with mock.patch.object(APIClient, "login", side_effect=error):
            result = runner.invoke(app, ["readings", *web()])

        assert result.exit_code == code
        assert "Error:" in result.stderr
        assert "Traceback" not in result.stderr

    # ------------------------------------------------------
    def test_an_unknown_pce_has_its_own_exit_code(self):

        with (
            mock.patch.object(APIClient, "login"),
            mock.patch.object(APIClient, "logout"),
            mock.patch.object(APIClient, "get_pce_list", return_value=pce_list()),
        ):
            result = runner.invoke(app, ["readings", *web(), "-c", "00000000000000"])

        assert result.exit_code == 4
        assert "does not exist" in result.stderr

    # ------------------------------------------------------
    def test_auth_check_reports_a_refused_login(self):

        with mock.patch.object(APIClient, "login", side_effect=LoginError("bad credentials", 401)):
            result = runner.invoke(app, ["auth", "check", *web()])

        assert result.exit_code == 3


# ------------------------------------------------------------------------------------------------------------
class TestOtherCommands:
    # ------------------------------------------------------
    def test_pce_lists_the_identifiers(self):

        with (
            mock.patch.object(APIClient, "login"),
            mock.patch.object(APIClient, "logout"),
            mock.patch.object(APIClient, "get_pce_list", return_value=pce_list()),
        ):
            result = runner.invoke(app, ["pce", *web()])

        assert json.loads(result.stdout) == [{"pce": PCE}]

    # ------------------------------------------------------
    def test_auth_check_logs_in_and_out(self):

        with mock.patch.object(APIClient, "login") as login, mock.patch.object(APIClient, "logout") as logout:
            result = runner.invoke(app, ["auth", "check", *web()])

        assert result.exit_code == 0
        login.assert_called_once()
        logout.assert_called_once()
        assert "Login OK" in result.stdout

    # ------------------------------------------------------
    def test_version(self):

        result = runner.invoke(app, ["--version"])

        assert result.exit_code == 0
        assert result.stdout.startswith("PyGazpar ")

        result = runner.invoke(app, ["version", "--format", "json"])
        assert {"pygazpar", "python", "platform"} <= set(json.loads(result.stdout)[0])

    # ------------------------------------------------------
    def test_file_excel(self):

        result = runner.invoke(
            app, ["file", "excel", str(RESOURCES / "Donnees_informatives_PCE_DAILY.xlsx"), "-f", "daily"]
        )

        assert result.exit_code == 0
        assert len(json.loads(result.stdout)["daily"]) > 0

    # ------------------------------------------------------
    def test_file_json_takes_the_only_pce_of_the_file(self):

        result = runner.invoke(
            app,
            [
                "file",
                "json",
                str(RESOURCES / "donnees_informatives.json"),
                str(RESOURCES / "temperatures.json"),
                "-f",
                "daily",
            ],
        )

        assert result.exit_code == 0
        assert len(json.loads(result.stdout)["daily"]) > 0

    # ------------------------------------------------------
    def test_file_json_rejects_a_pce_that_is_not_in_the_file(self):

        result = runner.invoke(
            app,
            [
                "file",
                "json",
                str(RESOURCES / "donnees_informatives.json"),
                str(RESOURCES / "temperatures.json"),
                "-c",
                "nope",
            ],
        )

        assert result.exit_code == 2


# ------------------------------------------------------------------------------------------------------------
class TestApiCommands:
    # ------------------------------------------------------
    def test_api_pce_shows_every_field_with_the_names_of_grdf(self):

        with (
            mock.patch.object(APIClient, "login"),
            mock.patch.object(APIClient, "logout"),
            mock.patch.object(APIClient, "get_pce_list", return_value=pce_list()) as get_list,
        ):
            result = runner.invoke(app, ["api", "pce", "--details", *web()])

        assert json.loads(result.stdout) == [{"idObject": PCE, "adresse": "1 rue du Gaz"}]
        assert get_list.call_args.args == (True,)

    # ------------------------------------------------------
    def test_api_consumption_shows_the_records_with_the_names_of_grdf(self):
        record = {
            "journeeGaziere": "2026-01-02",
            "dateDebutReleve": "2026-01-02T06:00:00+00:00",
            "dateFinReleve": "2026-01-03T06:00:00+00:00",
            "indexDebut": Decimal("10"),
            "indexFin": Decimal("12"),
            "volumeBrutConsomme": Decimal("2"),
            "energieConsomme": Decimal("22"),
            "coeffConversion": Decimal("11.2"),
            "qualificationReleve": "Mesuré",
            "newField": "kept",
        }
        consumption = {PCE: GrdfPceConsumption(idPce=PCE, frequence=None, releves=[record])}

        with (
            mock.patch.object(APIClient, "login"),
            mock.patch.object(APIClient, "logout"),
            mock.patch.object(APIClient, "get_pce_consumption", return_value=consumption),
        ):
            result = runner.invoke(app, ["api", "consumption", *web(), "-c", PCE, "-d", "7"])

        assert result.exit_code == 0
        row = json.loads(result.stdout)[0]
        assert row["journeeGaziere"] == "2026-01-02"
        assert row["energieConsomme"] == 22
        assert row["coeffConversion"] == 11.2
        assert row["newField"] == "kept"

    # ------------------------------------------------------
    def test_api_consumption_raw_prints_the_response_untouched(self):
        payload = {PCE: {"idPce": PCE, "frequence": None, "releves": []}}

        with (
            mock.patch.object(APIClient, "login"),
            mock.patch.object(APIClient, "logout"),
            mock.patch.object(APIClient, "get_pce_consumption_raw", return_value=payload),
        ):
            result = runner.invoke(app, ["api", "consumption", "--raw", *web(), "-c", PCE])

        assert json.loads(result.stdout) == payload

    # ------------------------------------------------------
    def test_raw_only_writes_json(self):

        result = runner.invoke(app, ["api", "consumption", "--raw", "--format", "csv", *web(), "-c", PCE])

        assert result.exit_code == 2

    # ------------------------------------------------------
    def test_api_meteo_lists_the_temperatures(self):

        with (
            mock.patch.object(APIClient, "login"),
            mock.patch.object(APIClient, "logout"),
            mock.patch.object(APIClient, "get_pce_meteo", return_value={date(2026, 1, 2): 5.5, date(2026, 1, 1): None}),
        ):
            result = runner.invoke(app, ["api", "meteo", *web(), "-c", PCE])

        assert json.loads(result.stdout) == [
            {"date": "2026-01-01", "temperature_degC": None},
            {"date": "2026-01-02", "temperature_degC": 5.5},
        ]

    # ------------------------------------------------------
    def test_api_excel_saves_the_file_of_grdf(self, tmp_path):
        from pygazpar.grdf import GrdfExcelSheet

        sheet = GrdfExcelSheet(filename="from-grdf.xlsx", content=b"xlsx")
        target = tmp_path / "mine.xlsx"

        with (
            mock.patch.object(APIClient, "login"),
            mock.patch.object(APIClient, "logout"),
            mock.patch.object(APIClient, "get_pce_consumption_excelsheet", return_value=sheet) as download,
        ):
            result = runner.invoke(app, ["api", "excel", *web(), "-c", PCE, "-f", "Mensuel", "-o", str(target)])

        assert result.exit_code == 0
        assert target.read_bytes() == b"xlsx"
        assert download.call_args.args[3] == GrdfFrequency.MONTHLY


# ------------------------------------------------------------------------------------------------------------
class TestRenderers:
    rows = {"": [{"a": 1, "b": Decimal("1.5"), "c": date(2026, 1, 2)}, {"a": None, "b": Decimal("2"), "d": "x"}]}

    # ------------------------------------------------------
    def test_one_untitled_group_is_a_json_list(self):

        assert json.loads(render_json(self.rows)) == [
            {"a": 1, "b": 1.5, "c": "2026-01-02"},
            {"a": None, "b": 2, "d": "x"},
        ]

    # ------------------------------------------------------
    def test_titled_groups_are_a_json_object(self):

        assert list(json.loads(render_json({"daily": [], "monthly": []}))) == ["daily", "monthly"]

    # ------------------------------------------------------
    def test_csv_uses_the_union_of_the_columns(self):

        assert render_csv(self.rows).split("\n")[0] == "a,b,c,d"

    # ------------------------------------------------------
    def test_ndjson_has_no_blank_line(self):

        assert len(render_ndjson(self.rows).split("\n")) == 2
