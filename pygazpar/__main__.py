import sys

CLI_EXTRA_HINT = 'The pygazpar command line needs the cli extra: pip install "pygazpar[cli]"'


def main() -> None:
    """Entry point of the pygazpar command. The CLI dependencies are an optional extra of the library."""

    try:
        from pygazpar.cli import run
    except ModuleNotFoundError as error:
        if (error.name or "").split(".")[0] not in ("typer", "rich", "click"):
            raise
        print(CLI_EXTRA_HINT, file=sys.stderr)
        sys.exit(1)

    run()


if __name__ == "__main__":
    main()
