# PyGazpar

PyGazpar is a Python library for getting natural gas consumption from GrDF French provider.

Their natural gas meter is called Gazpar. It is wireless and transmit the gas consumption once per day.

All consumption data is available on the client account at GrDF Web Site (https://monespace.grdf.fr).

PyGazpar automatically goes through the Web Site and download the consumption data, and make it available in a Python structure.

## Installation

### Requirements
PyGazpar does not require Selenium and corresponding geckodriver to work.

With the new GrDF web site, it is possible to load the consumption data far easily than before.

PyGazpar uses [Poetry](https://python-poetry.org/) for dependency and package management.

### Create your virtual environment

```bash
$ cd /path/to/my_project_folder/

$ poetry install
```

### PyGazpar installation

Use the package manager [pip](https://pip.pypa.io/en/stable/) to install PyGazpar.

```bash
pip install pygazpar
```

You can also download the source code and install it manually.
```bash
cd /path/to/pygazpar/

$ poetry install
```

## Usage

#### Command line:

Credentials can be omitted from the command line. PyGazpar then reads `GRDF_USERNAME`, `GRDF_PASSWORD` and `PCE_IDENTIFIER` from the environment, or from a `.env` file in the working directory. Command line options take precedence. A PCE identifier is a 14-digit number; the examples use `12345678901234` as a dummy value.

| Option | Meaning |
|---|---|
| `-u`, `-p`, `-c` | GRDF login, password and PCE identifier. Optional when `GRDF_USERNAME`, `GRDF_PASSWORD` and `PCE_IDENTIFIER` are set. |
| `-t` | Directory for temporary files and the log (default `/tmp`). |
| `-f`, `--frequency` | Frequency for the `json`, `excel` and `test` datasources: `daily`, `weekly`, `monthly` or `yearly`, in lowercase or uppercase (default `daily`). Ignored by the raw datasources. |
| `-d`, `--lastNDays` | Number of days to load, counted back from today (default 365). |
| `--datasource` | `json` (default), `excel`, `test`, `raw-consumption` or `raw-temperature`. See below. |
| `--consumption-type` | `INFORMATIVE` (default) or `PUBLISHED`. Only for `json` and `raw-consumption`. |
| `-v` | Prints the PyGazpar version. |

| Datasource | What it returns |
|---|---|
| `json` | Daily, weekly, monthly and yearly data from the GrDF JSON API. This is the default. |
| `excel` | The same data from GrDF's Excel export. |
| `test` | Offline sample data, with no connection to GrDF. |
| `raw-consumption` | The GrDF consumption response as received, printed as JSON. |
| `raw-temperature` | The GrDF temperature response as received, printed as JSON. |

For the raw datasources, the version banner goes to stderr, so stdout only contains the JSON payload.

1. Standard usage (using Json GrDF API).

```bash
$ pygazpar -u 'your login' -p 'your password' -c '12345678901234' --datasource 'json'
```

2. Alternate usage (using Excel GrDF document).

```bash
$ pygazpar -u 'your login' -p 'your password' -c '12345678901234' -t 'temporary directory where to store Excel file (ex: /tmp)' --datasource 'excel'
```

3. Test usage (using local static data files, do not connect to GrDF site).

```bash
$ pygazpar -u 'your login' -p 'your password' -c '12345678901234' --datasource 'test'
```

4. Raw usage (output the GrDF API response as received, without PyGazpar post processing; `--frequency` is ignored).

```bash
# Consumption (informative data by default, use --consumption-type PUBLISHED for published data)
$ pygazpar -u 'your login' -p 'your password' -c '12345678901234' --datasource 'raw-consumption'
$ pygazpar -u 'your login' -p 'your password' -c '12345678901234' --datasource 'raw-consumption' --consumption-type 'PUBLISHED'

# Temperatures (meteo)
$ pygazpar -u 'your login' -p 'your password' -c '12345678901234' --datasource 'raw-temperature'
```

#### Library:

1. Standard usage (using Json GrDF API).

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
See [samples/jsonSample.py](samples/jsonSample.py) file for the full example.

By default, `JsonWebDataSource` requests GrDF's **informative** consumption readings. Some PCE identifiers do not expose any (or only the latest) history through that endpoint, while a longer history remains available as **published** consumption on the GrDF customer portal. In that case, pass `consumption_type=pygazpar.ConsumptionType.PUBLISHED` to read from the published readings instead:

```python
import pygazpar

client = pygazpar.Client(pygazpar.JsonWebDataSource(
    username='your login',
    password='your password',
    consumption_type=pygazpar.ConsumptionType.PUBLISHED)
)
```

A published reading covers a period of several days. PyGazpar spreads its volume evenly across the days of the period, and its energy in proportion to that volume, so the totals match GrDF's publication. A day's energy can differ from its volume times the coefficient by a little more than 1 kWh, because of whole-kWh rounding and small differences in the publication itself. The indexes of those days are interpolated, and their `type` is `Calculé`, meaning calculated rather than measured. The rules and examples are in [Published readings: period computation](#published-readings-period-computation).

2. Alternate usage (using Excel GrDF document).

```python
import pygazpar

client = pygazpar.Client(pygazpar.ExcelWebDataSource(
    username='your login',
    password='your password',
    tmp_directory='/tmp')
)

# Returns the list of your PCE identifiers attached to your account.
pce_identifiers = client.get_pce_identifiers()

# Returns the daily and monthly consumptions for the last 60 days on your PCE identifier.
data = client.load_since(pce_identifier='12345678901234',
                        last_n_days=60,
                        frequencies=[pygazpar.Frequency.DAILY, pygazpar.Frequency.MONTHLY])
```
See [samples/excelSample.py](samples/excelSample.py) file for the full example.

3. Test usage (using local static data files, do not connect to GrDF site).

```python
import pygazpar

client = pygazpar.Client(pygazpar.TestDataSource())

data = client.load_since(pce_identifier='12345678901234',
                        last_n_days=10,
                        frequencies=[pygazpar.Frequency.DAILY, pygazpar.Frequency.MONTHLY])
```
See [samples/testSample.py](samples/testSample.py) file for the full example.

#### Typed readings:

`load_readings_since` and `load_readings_date_range` return the models instead of dicts, so the fields are attributes with their types:

```python
import pygazpar

client = pygazpar.Client(pygazpar.JsonWebDataSource(username='your login', password='your password'))

readings = client.load_readings_since(pce_identifier='12345678901234', last_n_days=60,
                                      frequencies=[pygazpar.Frequency.DAILY])
for reading in readings[pygazpar.Frequency.DAILY]:
    print(reading.start_date, reading.volume_m3, reading.energy_kwh)
```

The result is keyed by frequency. `pygazpar.Frequency` is also a string, so `readings['daily']` and `readings[pygazpar.Frequency.DAILY.value]` read the same list, and the dict form of `load_since` has the same keys in its JSON. The models are exported by `pygazpar` as `pygazpar.PeriodReading` and `pygazpar.DailyReading`.

`Client` is a context manager: it logs in when the block starts, and logs out when it ends, even after an error.

```python
import pygazpar

with pygazpar.Client(pygazpar.JsonWebDataSource(username='your login', password='your password')) as client:
    readings = client.load_readings_since(pce_identifier='12345678901234', last_n_days=60)
```

#### Errors:

If the PCE identifier is not one of the PCEs of the account, the web sources raise `pygazpar.UnknownPceError` (a `LookupError`) instead of returning no data. A PCE of the account that has no data for the period returns no readings.

The other errors come from GrDF. They are `pygazpar.ServerError` and its subclasses `LoginError` (GrDF refuses the login) and `RateLimitError` (GrDF keeps refusing the calls sent back to back). Calling the API before logging in raises `pygazpar.NotLoggedInError`. All of them derive from `pygazpar.PyGazparError`.

PyGazpar protects you from the usual hiccups of the GrDF web site:

- A request waits at most 10 seconds to connect and 60 seconds for the answer.
- GrDF answers HTTP 429 when calls follow each other too closely, and sometimes an HTML page instead of data. Those answers and the network errors are retried, for 10 attempts in all, waiting 3, 6, 12 and then 15 seconds between them, or the `Retry-After` delay when GrDF gives one. When the attempts are used up, the last error is raised.
- When the session has expired, PyGazpar logs in again once and repeats the call.

#### Raw sources:

The raw sources return the GrDF API responses as received, without PyGazpar's post processing:

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

#### Output:

```json
data =>
{
  "daily": [
    {
      "start_date": "2022-10-13",
      "end_date": "2022-10-14",
      "frequency": "daily",
      "time_period": "13/10/2022",
      "start_index_m3": 15724,
      "end_index_m3": 15725,
      "volume_m3": 2,
      "energy_kwh": 17,
      "timestamp": "2022-12-13T23:58:35.606763",
      "converter_factor_kwh/m3": 11.16,
      "temperature_degC": null,
      "type": "Mesur\u00e9"
    },
    ...
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
      "type": "Mesur\u00e9"
    }
  ],
  "monthly": [
    {
      "start_date": "2022-11-01",
      "end_date": "2022-12-01",
      "frequency": "monthly",
      "time_period": "Novembre 2022",
      "start_index_m3": 15750,
      "end_index_m3": 15950,
      "volume_m3": 204,
      "energy_kwh": 2227,
      "timestamp": "2022-12-13T23:58:35.606763"
    },
    {
      "start_date": "2022-12-01",
      "end_date": "2023-01-01",
      "frequency": "monthly",
      "time_period": "D\u00e9cembre 2022",
      "start_index_m3": 15950,
      "end_index_m3": 16098,
      "volume_m3": 148,
      "energy_kwh": 1664,
      "timestamp": "2022-12-13T23:58:35.606763"
    }
  ]
}
```

#### Output fields:

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
| `Absence de Données` | GrDF reports no data for the day. It is rebuilt as `Calculé` when the indexes on both sides are known (see step 7), and kept as it is otherwise. |
| `Calculé` | Derived by PyGazpar from a published period, or from a gap between periods. See [Published readings](#published-readings-period-computation). |

#### Data model:

The readings are models, shared by the parser, the converters and the Excel and test datasources. `load_since` and `load_date_range` return them in the dict form shown above, and `load_readings_since` and `load_readings_date_range` return the models.

- **`PeriodReading`** covers a period of any frequency: `start_date` (included), `end_date` (excluded), the frequency, the time period label, the indexes, the volume, the energy and the timestamp.
- **`DailyReading`** adds the converter factor, the temperature and the GrDF type of the day.

The rules are checked when a reading is built:
- A period lies inside one bucket of its frequency: a day, a week from Monday to Sunday (a partial first or last week keeps the days it covers), a calendar month or a calendar year.
- The `time_period` label is computed from the dates. A label given by a source must match the dates.
- A GrDF record is checked when it is read. A published period must give its indexes, volume, energy and coefficient, and negative consumption or an empty period is refused. An invalid record is skipped with a warning.
- A GrDF response is checked as it arrives. A malformed response raises an error that names the field at fault.
- An Excel file gives the dates through its labels, and an empty cell stays empty.

#### Temperatures:

Temperatures come from GrDF's meteo data. PyGazpar asks for the period ending yesterday at the latest, and for 10 to 730 days, to avoid HTTP 500 errors. For the `json` datasource, a failed meteo request is not an error: a warning is logged and the temperatures are `null`. The `raw-temperature` datasource raises the error instead.

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

## Published readings: period computation

GrDF publishes some consumption as periods rather than days. A published reading gives the volume and energy used between `dateDebutReleve` and `dateFinReleve`, and the indexes at both ends. PyGazpar turns each period into one row per calendar day, so published and informative data share the same daily model.

### Steps

For a period from `dateDebutReleve` (included) to `dateFinReleve` (excluded), with `days` calendar days between them, `V` the published volume, `E` the published energy, and `indexDebut` and `indexFin` the published indexes:

1. **Days.** The dates are read as written, with no time zone conversion. GrDF's 06:00 UTC timestamps fall on the same calendar day in France.
2. **Volume** is the reference. It is split in whole units of its published precision: bounds `b_i = V × i ÷ days` (integer division, in those units), so day `i` gets `b_(i+1) − b_i` units. For whole m³ data, each day gets either ⌊V ÷ days⌋ or ⌈V ÷ days⌉ m³.
3. **Energy** follows the volume. It is split the same way, in units of its own published precision, with bounds `e_i = E × b_i ÷ V`, so day `i` gets `e_(i+1) − e_i` units. A period with no volume has its energy spread evenly over the days instead.
4. **Indexes** are interpolated: `start_j = indexDebut + (indexFin − indexDebut) × j ÷ days`. The end of a day is the start of the next day.
5. **Temperature** of each day comes from the meteo data. The period's own temperature is not used.
6. **Type** is `Calculé`, and `converter_factor_kwh/m3` is the period's `coeffConversion`.
7. **Gaps** between two periods are rebuilt as a derived period, and so are the informative days without data (`Absence de Données`) between two known indexes. The volume is the index difference between the end of the previous period and the start of the next one. The energy is that volume times the average of the two coefficients, rounded to whole kWh. When the dates or the indexes cannot be used, nothing is filled, and PyGazpar logs a warning.

Integer division works on whole units, so the parts never drift from the total, and each part is written back with the decimal places of its published total. For example, 10.3 m³ gives parts of 3.4, 3.4 and 3.5 m³. The bounds start at 0 and end at the period total, so the daily differences add up to the published totals exactly.

### Examples

#### 1. Three-day period

Volume 10 m³, energy 100 kWh, indexes 100 → 110, from 1 January to 4 January 2026.

| time_period | start_index_m3 | end_index_m3 | volume_m3 | energy_kwh | converter_factor_kwh/m3 | temperature_degC | type |
|---|---|---|---|---|---|---|---|
| 01/01/2026 | 100 | 103 | 3 | 30 | 11.0 | null | Calculé |
| 02/01/2026 | 103 | 106 | 3 | 30 | 11.0 | null | Calculé |
| 03/01/2026 | 106 | 110 | 4 | 40 | 11.0 | null | Calculé |

The volume bounds are 0, 3, 6 and 10, so the days get 3, 3 and 4 m³. Energy follows: `100 × (0, 3, 6, 10) ÷ 10` gives 0, 30, 60 and 100, so the days get 30, 30 and 40 kWh. The indexes are 100, 103, 106 and 110.

#### 2. Rounding

Volume 7 m³, energy 50 kWh over 3 days, indexes 1000 → 1007, coefficient 7.14.

| time_period | start_index_m3 | end_index_m3 | volume_m3 | energy_kwh | converter_factor_kwh/m3 | temperature_degC | type |
|---|---|---|---|---|---|---|---|
| 01/02/2026 | 1000 | 1002 | 2 | 14 | 7.14 | null | Calculé |
| 02/02/2026 | 1002 | 1004 | 2 | 14 | 7.14 | null | Calculé |
| 03/02/2026 | 1004 | 1007 | 3 | 22 | 7.14 | null | Calculé |

Volume gives 2, 2 and 3 m³. Energy gives `50 × (0, 2, 4, 7) ÷ 7 = 0, 14, 28, 50`, so 14, 14 and 22 kWh. The exact shares are 14.29, 14.29 and 21.43 kWh, so every day is within 1 kWh of its share. The totals are still exactly 7 m³ and 50 kWh.

#### 3. Temperature per day

Volume 4 m³, energy 40 kWh, indexes 100 → 104, from 1 January to 3 January 2026. The meteo data has 5.5 °C for 2 January only.

| time_period | start_index_m3 | end_index_m3 | volume_m3 | energy_kwh | converter_factor_kwh/m3 | temperature_degC | type |
|---|---|---|---|---|---|---|---|
| 01/01/2026 | 100 | 102 | 2 | 20 | 11.0 | null | Calculé |
| 02/01/2026 | 102 | 104 | 2 | 20 | 11.0 | 5.5 | Calculé |

Each day takes its own meteo value. Day 1 has none, so its temperature is `null`.

#### 4. No volume

A period with zero volume and zero energy keeps one row per day, so the days stay visible.

| time_period | start_index_m3 | end_index_m3 | volume_m3 | energy_kwh | converter_factor_kwh/m3 | temperature_degC | type |
|---|---|---|---|---|---|---|---|
| 01/03/2026 | 500 | 500 | 0 | 0 | 11.0 | null | Calculé |
| 02/03/2026 | 500 | 500 | 0 | 0 | 11.0 | null | Calculé |

#### 5. Empty period

When `dateDebutReleve` equals `dateFinReleve`, or either date is missing, the period produces no rows. A warning is written to the log.

#### 6. Informative readings are unchanged

A reading with a `journeeGaziere` date is already one day. It keeps GrDF's own `type`.

| time_period | start_index_m3 | end_index_m3 | volume_m3 | energy_kwh | converter_factor_kwh/m3 | temperature_degC | type |
|---|---|---|---|---|---|---|---|
| 23/07/2026 | 2159 | 2160 | 1 | 11 | 11.29 | 24.29 | Mesuré |

#### 7. A two-day period from the sample

From 1 to 3 December 2019: volume 29 m³, energy 323 kWh, coefficient 11.12, indexes 10380 → 10409.

| time_period | start_index_m3 | end_index_m3 | volume_m3 | energy_kwh | converter_factor_kwh/m3 | temperature_degC | type |
|---|---|---|---|---|---|---|---|
| 01/12/2019 | 10380 | 10394 | 14 | 155 | 11.12 | null | Calculé |
| 02/12/2019 | 10394 | 10409 | 15 | 168 | 11.12 | null | Calculé |

The exact energy shares are 155.9 and 167.1 kWh. Against the coefficient, the first day is 0.7 kWh off and the second is 1.2 kWh off. That second gap is in the publication: its energy is 0.5 kWh above `29 × 11.12`.

#### 8. The first period in the sample

From 10 October 2017 to 9 April 2018 (181 days): volume 2025 m³, energy 22417 kWh, indexes 5089 → 7114. The first two days:

| time_period | start_index_m3 | end_index_m3 | volume_m3 | energy_kwh | converter_factor_kwh/m3 | temperature_degC | type |
|---|---|---|---|---|---|---|---|
| 10/10/2017 | 5089 | 5100 | 11 | 121 | 11.07 | null | Calculé |
| 11/10/2017 | 5100 | 5111 | 11 | 122 | 11.07 | null | Calculé |

Each day gets 11 m³ or 12 m³ over the 181 days, and the energy of the whole period is 22417 kWh.

#### 9. A gap in the publication

Between the period ending on 3 October 2019 and the one starting on 3 November 2019, the publication has no records. The meter indexes still show that 107 m³ were used (10,103 − 9,996). The gap is rebuilt as a period: its volume is that index difference, and its energy is that volume times the average of the two neighbouring coefficients, (11.2 + 11.12) ÷ 2 = 11.16. So the energy is 1,194 kWh.

| time_period | start_index_m3 | end_index_m3 | volume_m3 | energy_kwh | converter_factor_kwh/m3 | temperature_degC | type |
|---|---|---|---|---|---|---|---|
| 02/10/2019 | 9993 | 9996 | 3 | 34 | 11.2 | null | Calculé |
| 03/10/2019 | 9996 | 9999 | 3 | 33 | 11.16 | null | Calculé |
| 02/11/2019 | 10099 | 10103 | 4 | 45 | 11.16 | null | Calculé |
| 03/11/2019 | 10103 | 10112 | 9 | 100 | 11.12 | null | Calculé |

#### 10. Decimal values

Volume 10.3 m³, energy 100.5 kWh, indexes 100 → 110.3, from 1 January to 4 January 2026. Each total is split in its own precision, so the parts keep one decimal place.

| time_period | start_index_m3 | end_index_m3 | volume_m3 | energy_kwh | converter_factor_kwh/m3 | temperature_degC | type |
|---|---|---|---|---|---|---|---|
| 01/01/2026 | 100 | 103.4 | 3.4 | 33.1 | 11.0 | null | Calculé |
| 02/01/2026 | 103.4 | 106.8 | 3.4 | 33.2 | 11.0 | null | Calculé |
| 03/01/2026 | 106.8 | 110.3 | 3.5 | 34.2 | 11.0 | null | Calculé |

The volumes sum to 10.3 m³ and the energies to 100.5 kWh. The energies follow the volumes, so each day is within 0.1 kWh of its share.

### Invariants

These are the rules the code enforces, and what the sample shows for each.

| # | Invariant | Holds because | Sample |
|---|---|---|---|
| 1 | One row per calendar day, for each period (from `dateDebutReleve` to `dateFinReleve` excluded) and each gap between periods | Construction | 1,850 rows: 1,819 for the periods, 31 for the gap |
| 2 | Daily volumes sum to `volumeBrutConsomme` for each period | Exact bounds in published units | 87 of 87 periods |
| 3 | Daily energies sum to `energieConsomme` for each period | Exact bounds in published units | 87 of 87 periods |
| 4 | Daily volumes of a period differ by at most one unit of volume (1 m³ for whole m³ data) | Floor and ceiling of `V ÷ days` | Holds |
| 5 | Each day's energy is within one unit of energy (1 kWh for whole kWh data) of its share `energie_period × volume_day ÷ volume_period` | Integer rounding | Largest gap 0.994 kWh |
| 6 | Each day's `end_index − start_index` equals its volume | Holds when the publication's index difference equals its volume | 1,819 of 1,819 rows |
| 7 | Within a period, each day's end index is the next day's start index | Construction | Holds |
| 8 | A period starts at `indexDebut` and ends at `indexFin` | Construction | Holds |
| 9 | Each day's energy is close to `volume × coeffConversion` | Depends on the publication | Largest gap 1.2 kWh, 1,819 of 1,819 within 1.5 kWh |
| 10 | Zero-volume periods have zero energy | Publication: energy is zero when volume is zero | Holds for the 2 such periods |
| 11 | Informative readings are passed through unchanged | Construction | Not split |
| 12 | Daily volumes sum to the last index minus the first index, over the whole series | Construction: gaps are rebuilt from the indexes | 10,664 m³ = 15,753 − 5,089 |

Invariants 6 and 9 depend on what GrDF publishes, so they are not guaranteed for every period. The code keeps each period's totals exact in all cases.

### Tests for the invariants

| Invariant | Tests in `tests/test_jsonparser.py` |
|---|---|
| 1. One row per day | `test_published_readings_are_split_by_day`, `test_published_period_is_spread_with_exact_sums_and_chained_indexes` |
| 2 and 3. Exact volume and energy sums | `test_each_published_period_keeps_its_exact_volume_and_energy_sums`, `test_random_periods_keep_the_volume_and_energy_invariants` |
| 4. Daily volumes differ by at most one unit of volume | `test_split_volumes_of_a_published_period_differ_by_at_most_one_unit`, `test_random_periods_keep_the_volume_and_energy_invariants` |
| 5. Energy within one unit of energy of its share | `test_split_energy_is_within_one_kwh_of_its_pro_rata_share`, `test_random_periods_keep_the_volume_and_energy_invariants` |
| 6. Index difference equals volume | `test_split_rows_keep_index_difference_equal_to_volume_and_energy_close_to_volume_times_coefficient`, `test_random_periods_keep_the_volume_and_energy_invariants` |
| 7 and 8. Indexes chain and match the period | `test_published_period_is_spread_with_exact_sums_and_chained_indexes`, `test_random_periods_keep_the_volume_and_energy_invariants` |
| 9. Energy close to volume times coefficient | `test_split_rows_keep_index_difference_equal_to_volume_and_energy_close_to_volume_times_coefficient` |
| 10. Zero volume | `test_zero_volume_period_has_zero_energy`, `test_energy_without_volume_is_spread_evenly_over_the_days` |
| 11. Informative readings unchanged | `test_informative_readings_use_gas_day` |
| 12. Whole-series volume | `test_published_readings_are_split_by_day` |

Gaps between periods: `test_gap_between_published_periods_is_rebuilt_from_the_indexes` and `test_synthetic_gap_is_rebuilt_from_the_index_difference`. Days without data: `test_informative_day_without_data_is_rebuilt_from_the_indexes` and `test_informative_day_without_data_at_the_start_stays_without_data`.

Periods with no days, or without dates, produce no rows: `test_published_period_without_days_is_ignored` and `test_readings_without_any_date_are_ignored`.

### Weekly, monthly and yearly buckets

The weekly, monthly and yearly outputs group the daily rows and keep only complete buckets: at least 7 days for a week, 28 days for a month and 360 days for a year. The last bucket is always kept, even when it is incomplete. An incomplete first bucket is dropped.

Weeks run from Monday to Sunday, on the calendar. The week of 30 December 2019 to 5 January 2020 is one week, even though it crosses the new year. Months and years are calendar months and calendar years.

For example, daily data from 20 January to 15 February 2026 at 1 m³ per day gives 27 m³ in total. The monthly output is:

| time_period | volume_m3 |
|---|---|
| Février 2026 | 15 |

January has only 12 days, so it is dropped, and the output totals 15 m³ rather than 27 m³. See [Known exceptions](#known-exceptions).

### Known exceptions

- **Gap energy:** the energy of a gap is an estimate: its volume times the average of the two neighbouring coefficients. In the sample, the coefficients are 11.2 and 11.12, so the estimate is 1,194 kWh.
- **Informative readings:** GrDF's own data does not always satisfy invariants 6 and 9. In the sample, the index difference differs from the volume in 244 of 1,096 rows, and energy differs from `volume × coeffConversion` by up to 6 kWh. PyGazpar passes these values through and does not correct them.
- **Totals at weekly, monthly and yearly frequencies:** these outputs keep only complete buckets, so their totals can be lower than the daily total. In the sample, the yearly total is 9,736 m³ against 10,664 m³ daily, because 2017 is incomplete (see [Weekly, monthly and yearly buckets](#weekly-monthly-and-yearly-buckets)).

## Limitation
PyGazpar relies on how GrDF Web Site is built.

Any change in the Web site may break this library.

We expect in close Future that GrDF makes available an open API from which we can get safely their data.

## Contributing
Pull requests are welcome. For major changes, please open an issue first to discuss what you would like to change.

Please make sure to update tests as appropriate.

## License
[MIT](https://choosealicense.com/licenses/mit/)

## Project status
PyGazpar has been initiated for integration with [Home Assistant](https://www.home-assistant.io/).

Corresponding Home Assistant integration custom component is available [here](https://github.com/ssenart/home-assistant-gazpar).