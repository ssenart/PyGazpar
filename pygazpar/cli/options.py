"""Options shared by the commands, and the helpers that resolve them (credentials, dates, frequencies, logging)."""

import contextlib
import logging
import sys
from collections.abc import Iterator
from dataclasses import dataclass
from datetime import date, timedelta
from typing import Annotated, TextIO

import typer

from pygazpar.cli.errors import EXIT_USAGE, fail
from pygazpar.cli.render import FORMATS, default_format
from pygazpar.model import Frequency

DEFAULT_LAST_N_DAYS = 365

ALL_FREQUENCIES = [Frequency.DAILY, Frequency.WEEKLY, Frequency.MONTHLY, Frequency.YEARLY]

LOG_FORMAT = "%(asctime)s %(levelname)s [%(name)s] %(message)s"

# ------------------------------------------------------------------------------------------------------------
# Option types, to be used in the signature of the commands.
UsernameOption = Annotated[
    str | None,
    typer.Option(
        "--username", "-u", envvar="GRDF_USERNAME", help="GRDF account (email). Env: GRDF_USERNAME.", show_default=False
    ),
]
PasswordOption = Annotated[
    str | None,
    typer.Option(
        "--password",
        "-p",
        envvar="GRDF_PASSWORD",
        help="GRDF password. Visible in the process list: prefer GRDF_PASSWORD, --password-stdin or the prompt.",
        show_default=False,
    ),
]
PasswordStdinOption = Annotated[
    bool, typer.Option("--password-stdin", help="Read the password from the first line of stdin.")
]
PceOption = Annotated[
    str | None,
    typer.Option(
        "--pce",
        "-c",
        envvar="PCE_IDENTIFIER",
        help="PCE identifier. Env: PCE_IDENTIFIER. Chosen automatically when the account has only one.",
        show_default=False,
    ),
]
FormatOption = Annotated[
    str | None,
    typer.Option(
        "--format",
        help=f"Output format: {' | '.join(FORMATS)}. Default: table on a terminal, json when piped or written to a file.",
        show_default=False,
    ),
]
OutputOption = Annotated[
    str | None,
    typer.Option("--output", "-o", help="Write the data to this file instead of stdout.", show_default=False),
]
NoColorOption = Annotated[bool, typer.Option("--no-color", help="Disable colors (NO_COLOR is honored too).")]
VerboseOption = Annotated[int, typer.Option("--verbose", "-v", count=True, help="Log on stderr: -v info, -vv debug.")]
LogFileOption = Annotated[
    str | None, typer.Option("--log-file", help="Also write the debug log to this file.", show_default=False)
]
LastDaysOption = Annotated[
    int | None,
    typer.Option(
        "--last-days", "-d", min=1, help=f"Last N days up to today (default {DEFAULT_LAST_N_DAYS}).", show_default=False
    ),
]
StartOption = Annotated[str | None, typer.Option("--start", help="Start date, YYYY-MM-DD.", show_default=False)]
EndOption = Annotated[
    str | None, typer.Option("--end", help="End date, YYYY-MM-DD (default: today).", show_default=False)
]


# ------------------------------------------------------------------------------------------------------------
@dataclass
class Credentials:
    username: str
    password: str


# ------------------------------------------------------------------------------------------------------------
def setup_logging(verbose: int, log_file: str | None) -> None:
    """Logs on stderr (warnings by default, -v info, -vv debug), and in a file at debug level when asked."""

    stderr_level = logging.WARNING if verbose <= 0 else logging.INFO if verbose == 1 else logging.DEBUG
    handlers: list[logging.Handler] = []

    stderr_handler = logging.StreamHandler(sys.stderr)
    stderr_handler.setLevel(stderr_level)
    if verbose <= 0:
        stderr_handler.setFormatter(logging.Formatter("%(levelname)s: %(message)s"))
    else:
        stderr_handler.setFormatter(logging.Formatter(LOG_FORMAT))
    handlers.append(stderr_handler)

    if log_file:
        file_handler = logging.FileHandler(log_file, mode="w", encoding="utf-8")
        file_handler.setLevel(logging.DEBUG)
        handlers.append(file_handler)

    file_formatter = logging.Formatter(LOG_FORMAT)
    for handler in handlers:
        if isinstance(handler, logging.FileHandler):
            handler.setFormatter(file_formatter)

    logging.basicConfig(level=logging.DEBUG if log_file else stderr_level, handlers=handlers, force=True)

    # Client logs an error with its traceback, then raises it: the CLI reports the error itself, once.
    logging.getLogger("pygazpar.client").setLevel(logging.DEBUG if verbose >= 2 or log_file else logging.CRITICAL)


# ------------------------------------------------------------------------------------------------------------
def resolve_credentials(
    username: str | None, password: str | None, password_stdin: bool, *, no_color: bool = False
) -> Credentials:
    """Returns the credentials: the username, then the password from the option or env, stdin, or a prompt."""

    if not username:
        raise fail(
            "a GRDF username is required: pass --username or set GRDF_USERNAME (or use --datasource test)",
            EXIT_USAGE,
            no_color=no_color,
        )

    if password_stdin:
        password = sys.stdin.readline().rstrip("\r\n")

    if not password and sys.stdin.isatty() and sys.stderr.isatty():
        password = typer.prompt("GRDF password", hide_input=True, err=True)

    if not password:
        raise fail(
            "a GRDF password is required: set GRDF_PASSWORD, use --password-stdin, or run on a terminal",
            EXIT_USAGE,
            no_color=no_color,
        )

    return Credentials(username, password)


# ------------------------------------------------------------------------------------------------------------
def parse_date(text: str, option: str) -> date:
    """Returns the date written YYYY-MM-DD."""

    try:
        return date.fromisoformat(text)
    except ValueError:
        raise fail(f"{option}: {text!r} is not a date, expected YYYY-MM-DD", EXIT_USAGE) from None


# ------------------------------------------------------------------------------------------------------------
def resolve_period(
    last_days: int | None, start: str | None, end: str | None, *, default_days: int | None = DEFAULT_LAST_N_DAYS
) -> tuple[date, date]:
    """Returns the start and end dates: --start/--end, or the last N days up to today.

    --last-days excludes --start and --end. Without any, the last default_days days (a very early start date when
    default_days is None, to keep everything).
    """

    if last_days is not None and (start or end):
        raise fail("--last-days cannot be combined with --start or --end", EXIT_USAGE)

    today = date.today()

    if start or end:
        end_date = parse_date(end, "--end") if end else today
        start_date = parse_date(start, "--start") if start else end_date - timedelta(days=DEFAULT_LAST_N_DAYS)
    else:
        end_date = today
        days = last_days if last_days is not None else default_days
        start_date = end_date - timedelta(days=days) if days is not None else date(2000, 1, 1)

    if start_date > end_date:
        raise fail(f"the start date {start_date} is after the end date {end_date}", EXIT_USAGE)

    return start_date, end_date


# ------------------------------------------------------------------------------------------------------------
def parse_frequencies(texts: list[str] | None) -> list[Frequency]:
    """Returns the frequencies named, in lowercase or uppercase. 'all' stands for daily, weekly, monthly, yearly."""

    if not texts:
        return [Frequency.DAILY]

    frequencies: list[Frequency] = []
    for text in texts:
        if text.lower() == "all":
            candidates = ALL_FREQUENCIES
        else:
            try:
                candidates = [Frequency(text.lower())]
            except ValueError:
                choices = ", ".join([*map(str, Frequency), "all"])
                raise fail(f"--frequency: invalid value {text!r} (choose from {choices})", EXIT_USAGE) from None
        for frequency in candidates:
            if frequency not in frequencies:
                frequencies.append(frequency)

    return frequencies


# ------------------------------------------------------------------------------------------------------------
@contextlib.contextmanager
def open_output(path: str | None, fmt: str | None) -> Iterator[tuple[TextIO, str]]:
    """Yields the stream the data is written to and the format: stdout, or the file given (then json by default)."""

    if fmt is not None and fmt not in FORMATS:
        raise fail(f"--format: invalid value {fmt!r} (choose from {', '.join(FORMATS)})", EXIT_USAGE)

    if path is None:
        yield sys.stdout, fmt or default_format(sys.stdout)
        return

    with open(path, "w", encoding="utf-8", newline="") as stream:
        yield stream, fmt or "json"
