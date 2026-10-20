import builtins
import sys
from unittest import mock

import pytest

from pygazpar import __main__ as entry_point


class TestEntryPoint:
    # ------------------------------------------------------
    def test_the_missing_cli_extra_is_explained(self, capsys):
        real_import = builtins.__import__

        def import_without_typer(name, *args, **kwargs):
            if name.split(".")[0] in ("typer", "rich"):
                raise ModuleNotFoundError(f"No module named {name!r}", name=name)
            return real_import(name, *args, **kwargs)

        with (
            mock.patch.dict(sys.modules, {key: None for key in list(sys.modules) if key.startswith("pygazpar.cli")}),
            mock.patch.object(builtins, "__import__", import_without_typer),
            pytest.raises(SystemExit) as exit_info,
        ):
            for key in [key for key in sys.modules if key.startswith("pygazpar.cli")]:
                del sys.modules[key]
            entry_point.main()

        assert exit_info.value.code == 1
        assert "pygazpar[cli]" in capsys.readouterr().err
