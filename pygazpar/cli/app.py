"""The pygazpar command line: a thin layer over the library, from the GrDF API up to the normalized readings.

pygazpar readings   normalized readings (hourly, daily, weekly, monthly, yearly)
pygazpar pce        PCE identifiers of the account
pygazpar auth check test the login
pygazpar api ...    the GrDF API as it answers (PCE details, consumption records, temperatures, Excel download)
pygazpar file ...   readings from local Excel or JSON files, offline
"""

import json
import logging
import os
import platform
import sys
import tempfile
from pathlib import Path
from typing import Annotated, Any

import typer
from dotenv import find_dotenv, load_dotenv
from pydantic import ValidationError

from pygazpar import (
    Client,
    ConsumptionType,
    ExcelFileDataSource,
    ExcelWebDataSource,
    Frequency,
    IDataSource,
    JsonFileDataSource,
    JsonWebDataSource,
    PeriodReading,
    TestDataSource,
    __version__,
)
from pygazpar.api_client import APIClient, GrdfFrequency
from pygazpar.cli.errors import EXIT_USAGE, fail, handle_errors
from pygazpar.cli.options import (
    EndOption,
    FormatOption,
    LastDaysOption,
    LogFileOption,
    NoColorOption,
    OutputOption,
    PasswordOption,
    PasswordStdinOption,
    PceOption,
    StartOption,
    UsernameOption,
    VerboseOption,
    open_output,
    parse_frequencies,
    resolve_credentials,
    resolve_period,
    setup_logging,
)
from pygazpar.cli.render import UNTITLED, Dataset, Row, emit, to_json
from pygazpar.datasource import meteo_window
from pygazpar.grdf import GrdfRecord

Logger = logging.getLogger(__name__)

DATASOURCES = ("json", "excel", "test")

# Redundant with the title of the table and its period column: kept in json, ndjson and csv.
READINGS_TABLE_HIDE = ("start_date", "end_date", "frequency", "timestamp")

FrequencyOption = Annotated[
    list[str] | None,
    typer.Option(
        "--frequency",
        "-f",
        help="Reading frequency: hourly, daily, weekly, monthly, yearly, or all (= all but hourly). Repeatable. Default: daily.",
        show_default=False,
    ),
]
DatasourceOption = Annotated[
    str,
    typer.Option(
        "--datasource", help="Where the readings come from: json (GrDF API) | excel (GrDF Excel) | test (samples)."
    ),
]
ConsumptionTypeOption = Annotated[
    str | None,
    typer.Option(
        "--consumption-type",
        help="informative (default) or published. Applies to the json datasource.",
        show_default=False,
    ),
]
TmpdirOption = Annotated[
    str | None,
    typer.Option(
        "--tmpdir",
        "-t",
        help="Directory for the Excel files of the excel datasource (default: system temp).",
        show_default=False,
    ),
]
RetryCountOption = Annotated[
    int, typer.Option("--retry-count", min=0, help="Retries of a GrDF call that fails or is throttled.")
]

app = typer.Typer(
    name="pygazpar",
    help="Read your GrDF gas consumption: normalized readings, or the GrDF API as it answers.",
    no_args_is_help=True,
    pretty_exceptions_enable=False,
    rich_markup_mode="rich",
    context_settings={"help_option_names": ["-h", "--help"]},
)
api_app = typer.Typer(
    help="The GrDF API as it answers, without PyGazpar's normalization.",
    no_args_is_help=True,
    pretty_exceptions_enable=False,
)
file_app = typer.Typer(
    help="Readings from local files, offline: no credentials needed.",
    no_args_is_help=True,
    pretty_exceptions_enable=False,
)
auth_app = typer.Typer(help="Credentials.", no_args_is_help=True, pretty_exceptions_enable=False)
app.add_typer(api_app, name="api")
app.add_typer(file_app, name="file")
app.add_typer(auth_app, name="auth")


# ------------------------------------------------------------------------------------------------------------
def version_callback(value: bool) -> None:
    if value:
        typer.echo(f"PyGazpar {__version__}")
        raise typer.Exit()


# ------------------------------------------------------------------------------------------------------------
@app.callback()
def main_callback(
    _version: Annotated[
        bool,
        typer.Option("--version", "-V", callback=version_callback, is_eager=True, help="Show the version and exit."),
    ] = False,
) -> None:
    """Read your GrDF gas consumption: normalized readings, or the GrDF API as it answers."""


# ------------------------------------------------------------------------------------------------------------
def consumption_type_of(text: str | None) -> ConsumptionType:
    """Returns the consumption type named (informative by default), in lowercase or uppercase."""

    try:
        return ConsumptionType[(text or "informative").upper()]
    except KeyError:
        names = ", ".join(consumption_type.name.lower() for consumption_type in ConsumptionType)
        raise fail(f"--consumption-type: invalid value {text!r} (choose from {names})", EXIT_USAGE) from None


# ------------------------------------------------------------------------------------------------------------
def check_datasource(datasource: str, allowed: tuple[str, ...] = DATASOURCES) -> str:
    name = datasource.lower()
    if name not in allowed:
        raise fail(f"--datasource: invalid value {datasource!r} (choose from {', '.join(allowed)})", EXIT_USAGE)

    return name


# ------------------------------------------------------------------------------------------------------------
def build_datasource(
    datasource: str,
    username: str | None,
    password: str | None,
    password_stdin: bool,
    consumption_type: str | None,
    tmpdir: str | None,
    no_color: bool,
) -> IDataSource:
    """Returns the datasource of the readings. The test datasource needs no credentials."""

    if consumption_type is not None and datasource != "json":
        raise fail("--consumption-type requires --datasource json", EXIT_USAGE, no_color=no_color)

    if datasource == "test":
        return TestDataSource()

    credentials = resolve_credentials(username, password, password_stdin, no_color=no_color)

    if datasource == "excel":
        return ExcelWebDataSource(credentials.username, credentials.password, tmpdir or tempfile.gettempdir())

    return JsonWebDataSource(credentials.username, credentials.password, consumption_type_of(consumption_type))


# ------------------------------------------------------------------------------------------------------------
def pick_pce(pce: str | None, identifiers: list[str], no_color: bool) -> str:
    """Returns the PCE asked, or the only one of the account."""

    if pce:
        return pce
    if len(identifiers) == 1:
        Logger.info("Using the only PCE of the account: %s", identifiers[0])
        return identifiers[0]
    if not identifiers:
        raise fail("the account has no PCE", no_color=no_color)

    raise fail(
        f"several PCEs in the account, choose one with --pce: {', '.join(identifiers)}", EXIT_USAGE, no_color=no_color
    )


# ------------------------------------------------------------------------------------------------------------
def reading_row(reading: PeriodReading) -> Row:
    """Returns a reading as a flat row. Keys are the snake_case field names, with `type` for the GrDF type of a day."""

    row = reading.model_dump(mode="json")
    if "type_" in row:
        row["type"] = row.pop("type_")

    return row


# ------------------------------------------------------------------------------------------------------------
def readings_dataset(readings: dict[Frequency, Any], frequencies: list[Frequency]) -> Dataset:
    """Returns the readings by frequency, in the order asked. A frequency without any reading is reported on stderr."""

    dataset: dict[str, list[Row]] = {}
    for frequency in frequencies:
        rows = [reading_row(reading) for reading in readings.get(frequency, [])]
        if not rows:
            Logger.warning("No %s readings in the period.", frequency.value)
        dataset[frequency.value] = rows

    return dataset


# ------------------------------------------------------------------------------------------------------------
def write(
    dataset: Dataset, fmt: str | None, output: str | None, no_color: bool, table_hide: tuple[str, ...] = ()
) -> None:
    with open_output(output, fmt) as (stream, resolved_format):
        emit(dataset, resolved_format, stream, no_color or output is not None, table_hide)


# ------------------------------------------------------------------------------------------------------------
@app.command()
@handle_errors
def readings(
    username: UsernameOption = None,
    password: PasswordOption = None,
    password_stdin: PasswordStdinOption = False,
    pce: PceOption = None,
    datasource: DatasourceOption = "json",
    consumption_type: ConsumptionTypeOption = None,
    frequency: FrequencyOption = None,
    last_days: LastDaysOption = None,
    start: StartOption = None,
    end: EndOption = None,
    fmt: FormatOption = None,
    output: OutputOption = None,
    tmpdir: TmpdirOption = None,
    no_color: NoColorOption = False,
    verbose: VerboseOption = 0,
    log_file: LogFileOption = None,
) -> None:
    """Normalized readings: index, volume (m³), energy (kWh) and, daily, converter factor and temperature.

    Examples:

      pygazpar readings -f daily -d 30

      pygazpar readings -f all --start 2026-01-01 --end 2026-06-30 --format csv -o readings.csv

      pygazpar readings --datasource test -f monthly --format json | jq .
    """

    setup_logging(verbose, log_file)
    source = check_datasource(datasource)
    frequencies = parse_frequencies(frequency)
    start_date, end_date = resolve_period(last_days, start, end)
    data_source = build_datasource(source, username, password, password_stdin, consumption_type, tmpdir, no_color)

    with Client(data_source) as client:
        selected_pce = pick_pce(pce, client.get_pce_identifiers(), no_color)
        result = client.load_readings_date_range(selected_pce, start_date, end_date, frequencies)

    write(readings_dataset(result, frequencies), fmt, output, no_color, READINGS_TABLE_HIDE)


# ------------------------------------------------------------------------------------------------------------
@app.command()
@handle_errors
def pce(
    username: UsernameOption = None,
    password: PasswordOption = None,
    password_stdin: PasswordStdinOption = False,
    datasource: DatasourceOption = "json",
    fmt: FormatOption = None,
    output: OutputOption = None,
    no_color: NoColorOption = False,
    verbose: VerboseOption = 0,
    log_file: LogFileOption = None,
) -> None:
    """List the PCE identifiers of the account (see `pygazpar api pce --details` for everything GrDF says about them)."""

    setup_logging(verbose, log_file)
    source = check_datasource(datasource, ("json", "test"))
    data_source = build_datasource(source, username, password, password_stdin, None, None, no_color)

    with Client(data_source) as client:
        rows: list[Row] = [{"pce": identifier} for identifier in client.get_pce_identifiers()]

    write({UNTITLED: rows}, fmt, output, no_color)


# ------------------------------------------------------------------------------------------------------------
@auth_app.command("check")
@handle_errors
def auth_check(
    username: UsernameOption = None,
    password: PasswordOption = None,
    password_stdin: PasswordStdinOption = False,
    no_color: NoColorOption = False,
    verbose: VerboseOption = 0,
    log_file: LogFileOption = None,
) -> None:
    """Log in to GrDF and log out: exit code 0 when the credentials work, 3 when GrDF refuses them."""

    setup_logging(verbose, log_file)
    credentials = resolve_credentials(username, password, password_stdin, no_color=no_color)
    api_client = APIClient(credentials.username, credentials.password)
    api_client.login()
    api_client.logout()

    typer.echo(f"Login OK for {credentials.username}")


# ------------------------------------------------------------------------------------------------------------
@app.command()
@handle_errors
def version(
    fmt: FormatOption = None,
    output: OutputOption = None,
    no_color: NoColorOption = False,
) -> None:
    """Show the PyGazpar version and the environment it runs in."""

    row: Row = {"pygazpar": __version__, "python": platform.python_version(), "platform": platform.platform()}
    write({UNTITLED: [row]}, fmt, output, no_color)


# ------------------------------------------------------------------------------------------------------------
# api: the GrDF API as it answers.
# ------------------------------------------------------------------------------------------------------------
def logged_in_api_client(
    username: str | None, password: str | None, password_stdin: bool, retry_count: int, no_color: bool
) -> APIClient:
    credentials = resolve_credentials(username, password, password_stdin, no_color=no_color)
    api_client = APIClient(credentials.username, credentials.password, retry_count)
    api_client.login()

    return api_client


# ------------------------------------------------------------------------------------------------------------
def api_pce_of(api_client: APIClient, pce: str | None, no_color: bool) -> str:
    return pick_pce(pce, [] if pce else [item.id_object for item in api_client.get_pce_list()], no_color)


# ------------------------------------------------------------------------------------------------------------
@api_app.command("pce")
@handle_errors
def api_pce(
    username: UsernameOption = None,
    password: PasswordOption = None,
    password_stdin: PasswordStdinOption = False,
    details: Annotated[
        bool, typer.Option("--details", help="Ask GrDF for the details of each PCE (contract, address...).")
    ] = False,
    fmt: FormatOption = None,
    output: OutputOption = None,
    retry_count: RetryCountOption = 10,
    no_color: NoColorOption = False,
    verbose: VerboseOption = 0,
    log_file: LogFileOption = None,
) -> None:
    """The PCE list as GrDF sends it, with every field it gives (unknown ones included)."""

    setup_logging(verbose, log_file)
    api_client = logged_in_api_client(username, password, password_stdin, retry_count, no_color)
    try:
        rows: list[Row] = [item.model_dump(by_alias=True) for item in api_client.get_pce_list(details)]
    finally:
        api_client.logout()

    write({UNTITLED: rows}, fmt, output, no_color)


# ------------------------------------------------------------------------------------------------------------
@api_app.command("consumption")
@handle_errors
def api_consumption(
    username: UsernameOption = None,
    password: PasswordOption = None,
    password_stdin: PasswordStdinOption = False,
    pce: PceOption = None,
    consumption_type: Annotated[
        str, typer.Option("--type", help="informative (one record per gas day) or published (billing periods).")
    ] = "informative",
    last_days: LastDaysOption = None,
    start: StartOption = None,
    end: EndOption = None,
    raw: Annotated[bool, typer.Option("--raw", help="Print the response untouched (JSON).")] = False,
    fmt: FormatOption = None,
    output: OutputOption = None,
    retry_count: RetryCountOption = 10,
    no_color: NoColorOption = False,
    verbose: VerboseOption = 0,
    log_file: LogFileOption = None,
) -> None:
    """The consumption records of GrDF (journeeGaziere, indexDebut, volumeBrutConsomme, ...), with their GrDF names.

    Examples:

      pygazpar api consumption -d 7

      pygazpar api consumption --type published --raw
    """

    setup_logging(verbose, log_file)
    selected_type = consumption_type_of(consumption_type)
    start_date, end_date = resolve_period(last_days, start, end)
    if raw and fmt not in (None, "json"):
        raise fail("--raw only writes json", EXIT_USAGE, no_color=no_color)

    api_client = logged_in_api_client(username, password, password_stdin, retry_count, no_color)
    try:
        selected_pce = api_pce_of(api_client, pce, no_color)
        if raw:
            payload: Any = api_client.get_pce_consumption_raw(selected_type, start_date, end_date, [selected_pce])
        else:
            payload = api_client.get_pce_consumption(selected_type, start_date, end_date, [selected_pce])
    finally:
        api_client.logout()

    if raw:
        with open_output(output, "json") as (stream, _):
            stream.write(to_json(payload) + "\n")
        return

    rows: list[Row] = []
    for consumption in payload.values():
        for record in consumption.releves:
            try:
                rows.append(GrdfRecord.model_validate(record).model_dump(by_alias=True))
            except ValidationError:
                Logger.warning("A record does not match the expected shape, kept as GrDF sent it: %s", record)
                rows.append(dict(record))

    write({UNTITLED: rows}, fmt, output, no_color)


# ------------------------------------------------------------------------------------------------------------
@api_app.command("meteo")
@handle_errors
def api_meteo(
    username: UsernameOption = None,
    password: PasswordOption = None,
    password_stdin: PasswordStdinOption = False,
    pce: PceOption = None,
    last_days: LastDaysOption = None,
    start: StartOption = None,
    end: EndOption = None,
    raw: Annotated[bool, typer.Option("--raw", help="Print the response untouched (JSON).")] = False,
    fmt: FormatOption = None,
    output: OutputOption = None,
    retry_count: RetryCountOption = 10,
    no_color: NoColorOption = False,
    verbose: VerboseOption = 0,
    log_file: LogFileOption = None,
) -> None:
    """The daily temperatures GrDF holds for a PCE (the end date is capped at yesterday, 10 to 730 days)."""

    setup_logging(verbose, log_file)
    start_date, end_date = resolve_period(last_days, start, end)
    if raw and fmt not in (None, "json"):
        raise fail("--raw only writes json", EXIT_USAGE, no_color=no_color)

    meteo_end_date, meteo_days = meteo_window(start_date, end_date)
    api_client = logged_in_api_client(username, password, password_stdin, retry_count, no_color)
    try:
        selected_pce = api_pce_of(api_client, pce, no_color)
        if raw:
            payload: Any = api_client.get_pce_meteo_raw(meteo_end_date, meteo_days, selected_pce)
        else:
            payload = api_client.get_pce_meteo(meteo_end_date, meteo_days, selected_pce)
    finally:
        api_client.logout()

    if raw:
        with open_output(output, "json") as (stream, _):
            stream.write(to_json(payload) + "\n")
        return

    rows: list[Row] = [{"date": day, "temperature_degC": temperature} for day, temperature in sorted(payload.items())]
    write({UNTITLED: rows}, fmt, output, no_color)


# ------------------------------------------------------------------------------------------------------------
@api_app.command("excel")
@handle_errors
def api_excel(
    username: UsernameOption = None,
    password: PasswordOption = None,
    password_stdin: PasswordStdinOption = False,
    pce: PceOption = None,
    consumption_type: Annotated[str, typer.Option("--type", help="informative or published.")] = "informative",
    frequency: Annotated[
        str,
        typer.Option("--frequency", "-f", help="GrDF frequency: horaire, journalier, hebdomadaire, mensuel, annuel."),
    ] = "journalier",
    last_days: LastDaysOption = None,
    start: StartOption = None,
    end: EndOption = None,
    output: Annotated[
        str | None,
        typer.Option(
            "--output",
            "-o",
            help="File to write (default: the name GrDF gives, in the current directory).",
            show_default=False,
        ),
    ] = None,
    retry_count: RetryCountOption = 10,
    no_color: NoColorOption = False,
    verbose: VerboseOption = 0,
    log_file: LogFileOption = None,
) -> None:
    """Download the Excel file of GrDF, untouched. Prints the path of the file written."""

    setup_logging(verbose, log_file)
    selected_type = consumption_type_of(consumption_type)
    start_date, end_date = resolve_period(last_days, start, end)
    frequencies = {item.value.lower(): item for item in GrdfFrequency}
    selected_frequency = frequencies.get(frequency.lower())
    if selected_frequency is None:
        raise fail(
            f"--frequency: invalid value {frequency!r} (choose from {', '.join(frequencies)})",
            EXIT_USAGE,
            no_color=no_color,
        )

    api_client = logged_in_api_client(username, password, password_stdin, retry_count, no_color)
    try:
        selected_pce = api_pce_of(api_client, pce, no_color)
        sheet = api_client.get_pce_consumption_excelsheet(
            selected_type, start_date, end_date, selected_frequency, [selected_pce]
        )
    finally:
        api_client.logout()

    target = Path(output) if output else Path(sheet.filename)
    target.write_bytes(sheet.content)

    typer.echo(str(target))


# ------------------------------------------------------------------------------------------------------------
# file: readings from local files.
# ------------------------------------------------------------------------------------------------------------
def file_readings(
    data_source: IDataSource, pce: str, frequency: list[str] | None, fmt: str | None, output: str | None, no_color: bool
) -> None:
    frequencies = parse_frequencies(frequency)
    start_date, end_date = resolve_period(None, None, None, default_days=None)
    result = data_source.readings(pce, start_date, end_date, frequencies)

    write(readings_dataset(result, frequencies), fmt, output, no_color, READINGS_TABLE_HIDE)


# ------------------------------------------------------------------------------------------------------------
@file_app.command("excel")
@handle_errors
def file_excel(
    path: Annotated[
        Path,
        typer.Argument(
            exists=True,
            dir_okay=False,
            readable=True,
            help="Excel file downloaded from GrDF (daily, weekly, monthly or hourly).",
        ),
    ],
    frequency: FrequencyOption = None,
    fmt: FormatOption = None,
    output: OutputOption = None,
    no_color: NoColorOption = False,
    verbose: VerboseOption = 0,
    log_file: LogFileOption = None,
) -> None:
    """Readings from an Excel file of GrDF. The frequency must match the file (see `pygazpar api excel`)."""

    setup_logging(verbose, log_file)
    data_source = ExcelFileDataSource(str(path))
    file_readings(data_source, data_source.get_pce_identifiers()[0], frequency, fmt, output, no_color)


# ------------------------------------------------------------------------------------------------------------
@file_app.command("json")
@handle_errors
def file_json(
    consumption: Annotated[
        Path,
        typer.Argument(
            exists=True, dir_okay=False, readable=True, help="Consumption JSON (`pygazpar api consumption --raw`)."
        ),
    ],
    temperature: Annotated[
        Path,
        typer.Argument(
            exists=True, dir_okay=False, readable=True, help="Temperature JSON (`pygazpar api meteo --raw`)."
        ),
    ],
    pce: Annotated[
        str | None,
        typer.Option(
            "--pce",
            "-c",
            help="PCE key in the consumption file. Default: the only one of the file.",
            show_default=False,
        ),
    ] = None,
    frequency: FrequencyOption = None,
    fmt: FormatOption = None,
    output: OutputOption = None,
    no_color: NoColorOption = False,
    verbose: VerboseOption = 0,
    log_file: LogFileOption = None,
) -> None:
    """Readings from a consumption JSON and a temperature JSON saved with `pygazpar api ... --raw`."""

    setup_logging(verbose, log_file)
    with open(consumption, encoding="utf-8") as consumption_file:
        keys = list(json.load(consumption_file))
    if pce and pce not in keys:
        raise fail(f"the PCE {pce} is not in {consumption}: {', '.join(keys)}", EXIT_USAGE, no_color=no_color)
    pce = pick_pce(pce, keys, no_color)

    file_readings(JsonFileDataSource(str(consumption), str(temperature)), pce, frequency, fmt, output, no_color)


# ------------------------------------------------------------------------------------------------------------
def run() -> None:
    """Runs the CLI. Credentials missing from the command line come from the environment or a .env file."""

    load_dotenv(find_dotenv(usecwd=True))
    code: Any = 0
    try:
        app(prog_name="pygazpar")
    except SystemExit as error:
        code = error.code
    try:
        sys.stdout.flush()
    except BrokenPipeError:
        # The reader of the pipe (head, for instance) left early: not an error. Python would flush again at exit.
        os.dup2(os.open(os.devnull, os.O_WRONLY), sys.stdout.fileno())
    sys.exit(code)


if __name__ == "__main__":
    run()
