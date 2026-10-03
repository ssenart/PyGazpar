import argparse
import sys
from unittest import mock

import pytest

from pygazpar import __main__ as cli
from pygazpar.api_client import APIClient, ConsumptionType

PCE = "12345678901234"


class TestCredentialsFromEnvironment:

    # ------------------------------------------------------
    def test_missing_credentials_are_read_from_environment(self, monkeypatch):

        monkeypatch.setenv("GRDF_USERNAME", "user@example.com")
        monkeypatch.setenv("GRDF_PASSWORD", "secret")
        monkeypatch.setenv("PCE_IDENTIFIER", PCE)
        args = argparse.Namespace(username=None, password=None, pce=None)

        cli.fill_credentials_from_env(args, mock.Mock())

        assert (args.username, args.password, args.pce) == ("user@example.com", "secret", PCE)

    # ------------------------------------------------------
    def test_command_line_takes_precedence_over_environment(self, monkeypatch):

        monkeypatch.setenv("GRDF_USERNAME", "from-env@example.com")
        monkeypatch.setenv("GRDF_PASSWORD", "from-env")
        monkeypatch.setenv("PCE_IDENTIFIER", "0000")
        args = argparse.Namespace(username="from-flag@example.com", password="from-flag", pce=PCE)

        cli.fill_credentials_from_env(args, mock.Mock())

        assert (args.username, args.password, args.pce) == ("from-flag@example.com", "from-flag", PCE)

    # ------------------------------------------------------
    def test_missing_credentials_are_an_error(self, monkeypatch):

        monkeypatch.delenv("GRDF_USERNAME", raising=False)
        monkeypatch.delenv("GRDF_PASSWORD", raising=False)
        monkeypatch.delenv("PCE_IDENTIFIER", raising=False)
        args = argparse.Namespace(username=None, password=None, pce=None)
        parser = mock.Mock()

        cli.fill_credentials_from_env(args, parser)

        parser.error.assert_called_once()


class TestConsumptionTypeOption:

    # ------------------------------------------------------
    def test_json_datasource_forwards_published_consumption_type(self, tmp_path):

        argv = [
            "pygazpar",
            "-u",
            "user@example.com",
            "-p",
            "secret",
            "-c",
            PCE,
            "-t",
            str(tmp_path),
            "--datasource",
            "json",
            "--consumption-type",
            "PUBLISHED",
        ]

        with (
            mock.patch.object(cli, "load_dotenv"),
            mock.patch.object(sys, "argv", argv),
            mock.patch.object(APIClient, "login"),
            mock.patch.object(APIClient, "get_pce_consumption", return_value={}) as get_consumption,
        ):
            assert cli.main() == 0

        assert get_consumption.call_args.args[0] == ConsumptionType.PUBLISHED

    # ------------------------------------------------------
    def test_consumption_type_is_rejected_for_other_datasources(self, tmp_path):

        argv = ["pygazpar", "-u", "u", "-p", "p", "-c", PCE, "-t", str(tmp_path), "--datasource", "test"]
        argv += ["--consumption-type", "PUBLISHED"]

        with (
            mock.patch.object(cli, "load_dotenv"),
            mock.patch.object(sys, "argv", argv),
            pytest.raises(SystemExit) as exit_info,
        ):
            cli.main()

        assert exit_info.value.code == 2
