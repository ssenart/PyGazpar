# PyGazpar

[![PyPI](https://img.shields.io/pypi/v/pygazpar)](https://pypi.org/project/pygazpar/)
[![Python versions](https://img.shields.io/pypi/pyversions/pygazpar)](https://pypi.org/project/pygazpar/)
[![CI](https://github.com/ssenart/pygazpar/actions/workflows/ci.yaml/badge.svg)](https://github.com/ssenart/pygazpar/actions/workflows/ci.yaml)
[![License: MIT](https://img.shields.io/github/license/ssenart/pygazpar)](LICENSE)

Python library and command line to get your natural gas consumption from GrDF, the French gas provider.

The Gazpar gas meter is wireless and transmits the consumption once per day. All the data is available on your account at the GrDF web site (https://monespace.grdf.fr). PyGazpar goes through the web site for you, downloads the consumption data and makes it available as Python objects, or as a table, JSON, NDJSON or CSV on the command line. It does not need Selenium or a browser driver.

## Contents

- [Quick start](#quick-start)
- [Installation](#installation)
- [Command line](#command-line)
- [Library](#library)
- [Output](#output)
- [Data model](#data-model)
- [Temperatures](#temperatures)
- [Errors](#errors)
- [Security](#security)
- [More documentation](#more-documentation)
- [Limitation](#limitation)
- [Contributing](#contributing)
- [License](#license)
- [Project status](#project-status)

## Quick start

```bash
pip install "pygazpar[cli]"

export GRDF_USERNAME='your login'
export GRDF_PASSWORD='your password'

pygazpar readings -d 30
```

The last 30 days of your consumption are shown as a table. No account at hand? Try `pygazpar readings --datasource test`, which uses bundled sample data and needs no credentials.

From Python:

```python
import pygazpar

with pygazpar.Client(pygazpar.JsonWebDataSource('your login', 'your password')) as client:
    readings = client.load_readings_since(pce_identifier='12345678901234', last_n_days=30)

for reading in readings[pygazpar.Frequency.DAILY]:
    print(reading.start_date, reading.volume_m3, reading.energy_kwh)
```

A PCE identifier is the 14-digit number of your gas meter point. The examples use `12345678901234` as a dummy value.

## Installation

PyGazpar needs Python 3.10 or later.

```bash
# The library only
pip install pygazpar

# The library and the pygazpar command
pip install "pygazpar[cli]"
```

The command line is an optional extra, so that applications that only import PyGazpar do not install its dependencies (typer and rich). Without the extra, running `pygazpar` tells you what to install.

### Development

PyGazpar uses [uv](https://docs.astral.sh/uv/) for dependency and package management. `uv sync` installs PyGazpar and its development tools in a `.venv` directory, from the versions locked in `uv.lock`. Run the checks and the tests with `uv run`:

```bash
git clone https://github.com/ssenart/pygazpar.git
cd pygazpar
uv sync --extra cli

uv run ruff format --check .
uv run ruff check .
uv run mypy .
uv run pytest tests
```

## Command line

Run `pygazpar --help`, or `pygazpar <command> --help` for the options and examples of a command. `pygazpar --install-completion` sets up tab completion in your shell.

| Command | What it does |
|---|---|
| `pygazpar readings` | Normalized readings: index, volume (m³), energy (kWh) and, daily, converter factor, temperature and GrDF type of the day. |
| `pygazpar pce` | The PCE identifiers of the account. |
| `pygazpar auth check` | Logs in and out. Exit code 0 when the credentials work. |
| `pygazpar api pce [--details]` | The PCE list as GrDF sends it, with every field (contract, address, ...). |
| `pygazpar api consumption [--type informative\|published] [--raw]` | The GrDF consumption records with GrDF's own field names (`journeeGaziere`, `indexDebut`, `volumeBrutConsomme`, ...). `--raw` prints the response untouched. |
| `pygazpar api meteo [--raw]` | The daily temperatures GrDF holds. |
| `pygazpar api excel -f journalier` | Downloads GrDF's Excel file untouched, and prints its path. |
| `pygazpar file excel PATH` | Readings from a downloaded Excel file, offline. |
| `pygazpar file json CONSUMPTION TEMPERATURE` | Readings from the files saved by `api consumption --raw` and `api meteo --raw`, offline. |
| `pygazpar version` | PyGazpar and Python versions. |

Credentials are read from the options, then from `GRDF_USERNAME`, `GRDF_PASSWORD` and `PCE_IDENTIFIER` in the environment or in a `.env` file in the working directory. If the account has only one PCE, `--pce` can be omitted.

Options of `readings` (the other commands take the ones that apply):

| Option | Meaning |
|---|---|
| `-u`, `-p`, `--password-stdin`, `-c` | GRDF login, password and PCE identifier. See [Security](#security) for the password. |
| `--datasource` | `json` (default, GrDF JSON API), `excel` (GrDF Excel export) or `test` (offline samples, no credentials). |
| `--consumption-type` | `informative` (default) or `published`. Only for `json`. |
| `-f`, `--frequency` | `hourly`, `daily`, `weekly`, `monthly`, `yearly` or `all` (all but hourly). Repeatable. Default `daily`. |
| `-d`, `--last-days` | Last N days up to today (default 365). Excludes `--start` and `--end`. |
| `--start`, `--end` | Period, `YYYY-MM-DD`. `--end` defaults to today. |
| `--format` | `table`, `json`, `ndjson` or `csv`. Default: table in a terminal, json when piped or written with `-o`. |
| `-o`, `--output` | Write the data to a file instead of stdout. |
| `--no-color` | Disable colors. `NO_COLOR` is honored too, and there is no color when not in a terminal. |
| `-v`, `-vv` | Log on stderr at info, then debug level. `--log-file` also writes a debug log to a file. |

The data goes to stdout and nothing else: logs, warnings and errors go to stderr, so `pygazpar readings --format csv > readings.csv` and pipes are safe.

Exit codes: `0` success, `1` error (GrDF or local), `2` usage error, `3` login refused, `4` unknown PCE, `5` rate limited by GrDF.

```bash
# Last 30 days, as a table
pygazpar readings -d 30

# Every frequency of the first half of the year, as CSV
pygazpar readings -f all --start 2026-01-01 --end 2026-06-30 --format csv -o readings.csv

# Offline, with the bundled samples
pygazpar readings --datasource test -f monthly

# What GrDF knows about your PCE, and its raw consumption response
pygazpar api pce --details
pygazpar api consumption --type published --raw -d 90

# Save the raw responses, then work offline from them
pygazpar api consumption --raw -d 365 -o consumption.json
pygazpar api meteo --raw -d 365 -o temperature.json
pygazpar file json consumption.json temperature.json -f monthly
```

## Library

The entry point is `pygazpar.Client`, built on a datasource:

| Datasource | What it returns |
|---|---|
| `JsonWebDataSource` | Daily, weekly, monthly and yearly data from the GrDF JSON API. The usual choice. |
| `ExcelWebDataSource` | The same data from GrDF's Excel export. |
| `TestDataSource` | Offline sample data, with no connection to GrDF. |
| `JsonFileDataSource`, `ExcelFileDataSource` | The same data from local files, offline. |

### With the JSON API

```python
import pygazpar

client = pygazpar.Client(pygazpar.JsonWebDataSource(
    username='your login',
    password='your password')
)

# Returns the list of your PCE identifiers attached to your account.
pce_identifiers = client.get_pce_identifiers()

# Returns the daily and monthly consumptions for the last 60 days on your PCE identifier.
data = client.load_since(pce_identifier='12345678901234',
                        last_n_days=60,
                        frequencies=[pygazpar.Frequency.DAILY, pygazpar.Frequency.MONTHLY])
```
See [samples/jsonSample.py](samples/jsonSample.py) for the full example. `load_date_range(pce_identifier, start_date, end_date, frequencies)` takes explicit dates instead of a number of days.

By default, `JsonWebDataSource` requests GrDF's **informative** consumption readings. Some PCE identifiers do not expose any (or only the latest) history through that endpoint, while a longer history remains available as **published** consumption on the GrDF customer portal. In that case, pass `consumption_type=pygazpar.ConsumptionType.PUBLISHED` to read from the published readings instead:

```python
client = pygazpar.Client(pygazpar.JsonWebDataSource(
    username='your login',
    password='your password',
    consumption_type=pygazpar.ConsumptionType.PUBLISHED)
)
```

A published reading covers a period of several days. PyGazpar spreads its volume evenly across the days of the period, and its energy in proportion to that volume, so the totals match GrDF's publication. A day's energy can differ from its volume times the coefficient by a little more than 1 kWh, because of whole-kWh rounding and small differences in the publication itself. The indexes of those days are interpolated, and their `type` is `Calculé`, meaning calculated rather than measured. The rules and examples are in [Published readings: period computation](docs/published-readings.md).

### With the Excel export

```python
client = pygazpar.Client(pygazpar.ExcelWebDataSource(
    username='your login',
    password='your password',
    tmp_directory='/tmp')
)

data = client.load_since(pce_identifier='12345678901234',
                        last_n_days=60,
                        frequencies=[pygazpar.Frequency.DAILY, pygazpar.Frequency.MONTHLY])
```
See [samples/excelSample.py](samples/excelSample.py) for the full example.

### Offline, with sample data

```python
client = pygazpar.Client(pygazpar.TestDataSource())

data = client.load_since(pce_identifier='12345678901234',
                        last_n_days=10,
                        frequencies=[pygazpar.Frequency.DAILY, pygazpar.Frequency.MONTHLY])
```
See [samples/testSample.py](samples/testSample.py) for the full example.

### Typed readings

`load_readings_since` and `load_readings_date_range` return the models instead of dicts, so the fields are attributes with their types:

```python
client = pygazpar.Client(pygazpar.JsonWebDataSource(username='your login', password='your password'))

readings = client.load_readings_since(pce_identifier='12345678901234', last_n_days=60,
                                      frequencies=[pygazpar.Frequency.DAILY])
for reading in readings[pygazpar.Frequency.DAILY]:
    print(reading.start_date, reading.volume_m3, reading.energy_kwh)
```

The result is keyed by frequency. `pygazpar.Frequency` is also a string, so `readings['daily']` and `readings[pygazpar.Frequency.DAILY.value]` read the same list, and the dict form of `load_since` has the same keys in its JSON. The models are exported by `pygazpar` as `pygazpar.PeriodReading` and `pygazpar.DailyReading`.

`Client` is a context manager: it logs in when the block starts, and logs out when it ends, even after an error.

```python
with pygazpar.Client(pygazpar.JsonWebDataSource(username='your login', password='your password')) as client:
    readings = client.load_readings_since(pce_identifier='12345678901234', last_n_days=60)
```

### Raw sources

The raw sources return the GrDF API responses as received, without PyGazpar's post processing. The command line equivalent is `pygazpar api consumption --raw` and `pygazpar api meteo --raw`.

```python
from datetime import date, timedelta

import pygazpar

end_date = date.today()
start_date = end_date - timedelta(days=30)

consumption = pygazpar.RawConsumptionWebDataSource(
    'your login', 'your password', pygazpar.ConsumptionType.PUBLISHED
).load('12345678901234', start_date, end_date)

temperatures = pygazpar.RawTemperatureWebDataSource(
    'your login', 'your password'
).load('12345678901234', start_date, end_date)
```

`consumption` is the consumption response and `temperatures` is the meteo response. Both are dictionaries, as returned by GrDF. A raw source logs in by itself on the first `load()`, and `logout()` closes its session.

## Output

The dict form returned by `load_since` and `load_date_range`, and printed by `pygazpar readings --format json`, is keyed by frequency:

```json
{
  "daily": [
    {
      "start_date": "2022-12-11",
      "end_date": "2022-12-12",
      "frequency": "daily",
      "time_period": "11/12/2022",
      "start_index_m3": 16081,
      "end_index_m3": 16098,
      "volume_m3": 18,
      "energy_kwh": 201,
      "timestamp": "2022-12-13T23:58:35.606763",
      "converter_factor_kwh/m3": 11.27,
      "temperature_degC": -1.47,
      "type": "Mesuré"
    }
  ],
  "monthly": [
    {
      "start_date": "2022-12-01",
      "end_date": "2023-01-01",
      "frequency": "monthly",
      "time_period": "Décembre 2022",
      "start_index_m3": 15950,
      "end_index_m3": 16098,
      "volume_m3": 148,
      "energy_kwh": 1664,
      "timestamp": "2022-12-13T23:58:35.606763"
    }
  ]
}
```

The command line (`readings`, in every format) names the converter factor `converter_factor_kwh_m3`. The library's dict form keeps `converter_factor_kwh/m3`, so that code written for earlier versions keeps working. The typed models use `converter_factor_kwh_m3` too.

| Field | Meaning |
|---|---|
| `frequency` | The frequency of the reading: `daily`, `weekly`, `monthly` or `yearly`. |
| `start_date`, `end_date` | The period of the reading, from `start_date` (included) to `end_date` (excluded), as ISO dates. |
| `time_period` | The day (`dd/mm/yyyy`) for `daily`, or the bucket label for `weekly`, `monthly` and `yearly`. |
| `start_index_m3`, `end_index_m3` | Meter index at the start and at the end of the day or bucket. |
| `volume_m3`, `energy_kwh` | Consumption over the day or bucket. |
| `converter_factor_kwh/m3` | Conversion coefficient of the reading. Daily rows only. |
| `temperature_degC` | Temperature of the day. Daily rows only. |
| `type` | Quality of the daily row. Daily rows only. |
| `timestamp` | When the data was read. |
| Empty values | `null` when the source has no value: a day without data, or an Excel row without a start index. |

The `type` values are:

| Value | Meaning |
|---|---|
| `Mesuré` | Measured by GrDF. |
| `Absence de Données` | GrDF reports no data for the day. It is rebuilt as `Calculé` when the indexes on both sides are known (see step 7 of the [period computation](docs/published-readings.md#steps)), and kept as it is otherwise. |
| `Calculé` | Derived by PyGazpar from a published period, or from a gap between periods. See [Published readings](docs/published-readings.md). |

## Data model

The readings are models, shared by the parser, the converters and the Excel and test datasources. `load_since` and `load_date_range` return them in the dict form shown above, and `load_readings_since` and `load_readings_date_range` return the models.

- **`PeriodReading`** covers a period of any frequency: `start_date` (included), `end_date` (excluded), the frequency, the time period label, the indexes, the volume, the energy and the timestamp.
- **`DailyReading`** adds the converter factor, the temperature and the GrDF type of the day.

The rules are checked when a reading is built:
- A period lies inside one bucket of its frequency: a day, a week from Monday to Sunday (a partial first or last week keeps the days it covers), a calendar month or a calendar year.
- The `time_period` label is computed from the dates. A label given by a source must match the dates.
- A GrDF record is checked when it is read. A published period must give its indexes, volume, energy and coefficient, and negative consumption or an empty period is refused. An invalid record is skipped with a warning.
- A GrDF response is checked as it arrives. A malformed response raises an error that names the field at fault.
- An Excel file gives the dates through its labels, and an empty cell stays empty.

## Temperatures

Temperatures come from GrDF's meteo data. PyGazpar asks for the period ending yesterday at the latest, and for 10 to 730 days, to avoid HTTP 500 errors. For the JSON datasource, a failed meteo request is not an error: a warning is logged and the temperatures are `null`. `RawTemperatureWebDataSource` (and `pygazpar api meteo`) raises the error instead.

Each daily row takes its temperature as follows:

- A record that covers exactly one day, such as an informative reading, keeps GrDF's own temperature when it has one. Otherwise, the day takes its meteo value.
- A record that covers several days, such as a published period, never gives its temperature to each day. Each day takes its meteo value, or stays empty when meteo has none.
- A gap day takes its meteo value.

```python
# Informative reading (journeeGaziere is set)
temperature = releve["temperature"]
if temperature is None:
    temperature = meteo.get(reading_date)

# Published period (journeeGaziere is null): the period's own temperature is ignored
temperature = meteo.get(day)
```

| Case | Own temperature | Meteo value of the day | Result |
|---|---|---|---|
| Informative reading on 23 July | 24.29 | 19.0 | 24.29 |
| Informative reading without own temperature | null | 19.0 | 19.0 |
| Published period, 1 January | 12.0 (the period) | none | null |
| Published period, 2 January | 12.0 (the period) | 5.5 | 5.5 |

## Errors

If the PCE identifier is not one of the PCEs of the account, the web sources raise `pygazpar.UnknownPceError` (a `LookupError`) instead of returning no data. A PCE of the account that has no data for the period returns no readings.

The other errors come from GrDF. They are `pygazpar.ServerError` and its subclasses `LoginError` (GrDF refuses the login) and `RateLimitError` (GrDF keeps refusing the calls sent back to back). Calling the API before logging in raises `pygazpar.NotLoggedInError`. All of them derive from `pygazpar.PyGazparError`. On the command line they become a one line message on stderr and an [exit code](#command-line); add `-vv` for the traceback.

PyGazpar protects you from the usual hiccups of the GrDF web site:

- A request waits at most 10 seconds to connect and 60 seconds for the answer.
- GrDF answers HTTP 429 when calls follow each other too closely, and sometimes an HTML page instead of data. Those answers and the network errors are retried, for 10 attempts in all, waiting 3, 6, 12 and then 15 seconds between them, or the `Retry-After` delay when GrDF gives one. When the attempts are used up, the last error is raised.
- When the session has expired, PyGazpar logs in again once and repeats the call.

## Security

Your GrDF password gives access to your account. Keep it out of scripts and shell history:

- The password given with `-p` is visible in the process list of the machine. Prefer `GRDF_PASSWORD` in the environment, `--password-stdin` (it reads the first line of stdin), or the prompt shown when `pygazpar` runs in a terminal.
- A `.env` file in the working directory is read automatically. Do not commit it.
- The DEBUG log (`-vv`, `--log-file`) removes the login state handles from what it records, but review a log before sharing it in an issue.

## More documentation

- [Published readings: period computation](docs/published-readings.md): how a published period becomes daily rows, with examples, invariants and the tests that check them.
- [CHANGELOG](CHANGELOG.md): what changed in each version, and what breaks.
- [samples/](samples): complete, tested scripts. Run them from the project folder with `python -m samples.<name>`:
  - [jsonSample.py](samples/jsonSample.py) and [excelSample.py](samples/excelSample.py): the web datasources, with logout and error handling.
  - [publishedSample.py](samples/publishedSample.py): published consumption over explicit dates.
  - [rawSample.py](samples/rawSample.py): the GrDF responses as received.
  - [testSample.py](samples/testSample.py) and [offlineFilesSample.py](samples/offlineFilesSample.py): no account needed.

## Limitation

PyGazpar relies on how the GrDF web site is built. Any change in the web site may break this library. We expect GrDF to make an open API available in the near future, from which their data can be obtained safely.

## Contributing

Pull requests are welcome. For major changes, please open an issue first to discuss what you would like to change.

Please make sure to update tests as appropriate. See [Development](#development) to run the checks.

## License

[MIT](LICENSE)

## Project status

PyGazpar has been initiated for integration with [Home Assistant](https://www.home-assistant.io/). The corresponding Home Assistant custom component is [home-assistant-gazpar](https://github.com/ssenart/home-assistant-gazpar).
