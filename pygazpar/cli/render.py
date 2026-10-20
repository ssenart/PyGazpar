"""Output of the CLI: table (rich), JSON, NDJSON and CSV.

A dataset is a mapping of a title (a frequency, for instance) to the rows under it, each row being a flat dict. The
data goes to the stream given (stdout), never mixed with messages, which go to stderr.
"""

import csv
import io
import json
import sys
from collections.abc import Mapping, Sequence
from datetime import date, datetime
from decimal import Decimal
from enum import Enum
from typing import Any, TextIO

from rich.console import Console
from rich.markup import escape
from rich.table import Table

Row = dict[str, Any]
Dataset = Mapping[str, Sequence[Row]]

FORMATS = ("table", "json", "ndjson", "csv")

# A dataset made of one untitled group is written as a plain list in JSON.
UNTITLED = ""

EMPTY_CELL = "–"

# Short headers of the tables, where the keys of json and csv would not fit an 80 columns terminal.
TABLE_LABELS = {
    "time_period": "period",
    "start_index_m3": "index start (m³)",
    "end_index_m3": "index end (m³)",
    "volume_m3": "m³",
    "energy_kwh": "kWh",
    "converter_factor_kwh_m3": "kWh/m³",
    "temperature_degC": "°C",
}

# Above this number of columns, a table is unreadable: each row is shown as a list of fields instead.
MAX_TABLE_COLUMNS = 12


# ------------------------------------------------------------------------------------------------------------
def default_format(stream: TextIO) -> str:
    """Returns table on a terminal, JSON when the output is piped or redirected."""

    return "table" if stream.isatty() else "json"


# ------------------------------------------------------------------------------------------------------------
def json_default(value: Any) -> Any:
    """Writes the values that JSON does not know: dates, decimals, enums."""

    if isinstance(value, Decimal):
        return int(value) if value == value.to_integral_value() else float(value)
    if isinstance(value, datetime | date):
        return value.isoformat()
    if isinstance(value, Enum):
        return value.value
    if isinstance(value, bytes):
        return value.decode("utf-8", errors="replace")

    raise TypeError(f"Object of type {type(value).__name__} is not JSON serializable")


# ------------------------------------------------------------------------------------------------------------
def to_json(payload: Any) -> str:
    """Returns the JSON text of a payload."""

    return json.dumps(payload, indent=2, ensure_ascii=False, default=json_default)


# ------------------------------------------------------------------------------------------------------------
def columns_of(rows: Sequence[Row]) -> list[str]:
    """Returns the column names of the rows: the keys, in order of first appearance."""

    columns: dict[str, None] = {}
    for row in rows:
        for key in row:
            columns.setdefault(key, None)

    return list(columns)


# ------------------------------------------------------------------------------------------------------------
def cell(value: Any) -> str:
    """Returns the text of a table or CSV cell."""

    if value is None:
        return ""
    if isinstance(value, Decimal):
        return str(json_default(value))
    if isinstance(value, datetime | date):
        return value.isoformat()
    if isinstance(value, Enum):
        return str(value.value)
    if isinstance(value, Mapping | list | tuple):
        return json.dumps(value, ensure_ascii=False, default=json_default)

    return str(value)


# ------------------------------------------------------------------------------------------------------------
def render_json(dataset: Dataset) -> str:
    """Returns a list when the dataset has one untitled group, else an object keyed by title."""

    if list(dataset) == [UNTITLED]:
        return to_json(list(dataset[UNTITLED]))

    return to_json({title: list(rows) for title, rows in dataset.items()})


# ------------------------------------------------------------------------------------------------------------
def render_ndjson(dataset: Dataset) -> str:
    """Returns one JSON object per line, in the order of the dataset."""

    lines = [json.dumps(row, ensure_ascii=False, default=json_default) for rows in dataset.values() for row in rows]

    return "\n".join(lines)


# ------------------------------------------------------------------------------------------------------------
def render_csv(dataset: Dataset) -> str:
    """Returns one CSV with the rows of every group, under the union of their columns."""

    rows = [row for group in dataset.values() for row in group]
    buffer = io.StringIO()
    writer = csv.writer(buffer, lineterminator="\n")
    columns = columns_of(rows)
    writer.writerow(columns)
    for row in rows:
        writer.writerow([cell(row.get(column)) for column in columns])

    return buffer.getvalue().rstrip("\n")


# ------------------------------------------------------------------------------------------------------------
def render_records(console: Console, title: str, rows: Sequence[Row], columns: Sequence[str]) -> None:
    """Writes each row as a field/value table, for the rows that have too many columns."""

    for number, row in enumerate(rows, start=1):
        table = Table(
            title=f"{title} {number}/{len(rows)}" if title else f"{number}/{len(rows)}",
            title_style="bold",
            show_header=False,
        )
        table.add_column(style="cyan", no_wrap=True)
        table.add_column()
        for column in columns:
            table.add_row(column, escape(cell(row.get(column))) or f"[dim]{EMPTY_CELL}[/dim]")
        console.print(table)


# ------------------------------------------------------------------------------------------------------------
def render_table(dataset: Dataset, stream: TextIO, no_color: bool = False, hide: Sequence[str] = ()) -> None:
    """Writes one rich table per group, without the columns hidden. Colors are off when the stream is not a terminal,
    or on NO_COLOR."""

    console = Console(file=stream, no_color=no_color, highlight=False)

    for title, rows in dataset.items():
        if not rows:
            console.print(f"[dim]{title}: no data[/dim]" if title else "[dim]No data[/dim]")
            continue

        columns = [column for column in columns_of(rows) if column not in hide]

        if len(columns) > MAX_TABLE_COLUMNS:
            render_records(console, title, rows, columns)
            continue

        table = Table(title=f"{title} ({len(rows)})" if title else None, title_style="bold", header_style="bold cyan")
        for column in columns:
            numeric = all(
                isinstance(row.get(column), int | float | Decimal) for row in rows if row.get(column) is not None
            )
            table.add_column(TABLE_LABELS.get(column, column), justify="right" if numeric else "left", no_wrap=False)
        for row in rows:
            table.add_row(*[escape(cell(row.get(column))) or f"[dim]{EMPTY_CELL}[/dim]" for column in columns])

        console.print(table)


# ------------------------------------------------------------------------------------------------------------
def emit(
    dataset: Dataset,
    fmt: str,
    stream: TextIO | None = None,
    no_color: bool = False,
    table_hide: Sequence[str] = (),
) -> None:
    """Writes the dataset to the stream (stdout by default) in the format asked.

    table_hide lists the columns left out of a table to keep it readable: json, ndjson and csv always have them all.
    """

    stream = stream or sys.stdout

    if fmt == "table":
        render_table(dataset, stream, no_color, table_hide)
        return

    text = {"json": render_json, "ndjson": render_ndjson, "csv": render_csv}[fmt](dataset)
    stream.write(text + "\n")
