# PyGazpar
PyGazpar is a Python library for getting natural gas consumption from GrDF French provider.

Their natural gas meter is called Gazpar. It is wireless and transmit the gas consumption once per day.

All consumption data is available on the client account at GrDF Web Site (https://monespace.grdf.fr).

PyGazpar automatically goes through the Web Site and download the consumption data Excel file, and make it available in a Python structure (list of dictionaries).

## Installation

### Requirements
PyGazpar does not require Selenium and corresponding geckodriver to work.

With the new GrDF web site, it is possible to load the consumption data far easily than before.

### Create your virtual environment
```bash
$ cd /path/to/my_project_folder/

$ python3 -m venv .venv
```

### PyGazpar installation
Activate your virtual environment.
```bash
source .venv/bin/activate
```

Use the package manager [pip](https://pip.pypa.io/en/stable/) to install PyGazpar.
```bash
pip install pygazpar
```

You can also download the source code and install it manually.
```bash
cd /path/to/pygazpar/
python setup.py install
```

## Usage

#### Command line:

```bash
$ pygazpar -u 'your login' -p 'your password' -c 'your PCE identifier' -t 'temporary directory where to store XSLX file (ex: /tmp)'
```

#### Library:

```python
import pygazpar

client = pygazpar.Client(username='your login',
                         password='your password',
                         pceIdentifier='your PCE identifier',
                         meterReadingFrequency=pygazpar.Frequency.DAILY,
                         lastNDays=10,
                         tmpDirectory='/tmp/pygazpar')

client.update()

data = client.data()
```

#### Output:

```json
data =>
[
  {
    "time_period": "16/04/2021",
    "start_index_m3": 13685.0,
    "end_index_m3": 13695.0,
    "volume_m3": 9.9,
    "energy_kwh": 111.0,
    "converter_factor_kwh/m3": 11.268,
    "temperature_degC": 8.0,
    "type": "MES",
    "timestamp": "2021-04-20T10:21:46.265119"
  },
  {
    "time_period": "17/04/2021",
    "start_index_m3": 13695.0,
    "end_index_m3": 13702.0,
    "volume_m3": 7.7,
    "energy_kwh": 86.0,
    "converter_factor_kwh/m3": 11.268,
    "temperature_degC": 9.0,
    "type": "MES",
    "timestamp": "2021-04-20T10:21:46.265119"
  },
  {
    "time_period": "18/04/2021",
    "start_index_m3": 13702.0,
    "end_index_m3": 13708.0,
    "volume_m3": 6.2,
    "energy_kwh": 69.0,
    "converter_factor_kwh/m3": 11.268,
    "temperature_degC": 10.0,
    "type": "MES",
    "timestamp": "2021-04-20T10:21:46.265119"
  }
]
```

## More features
By default, PyGazpar queries for daily consumption data.

However, it is also possible to get weekly or monthly consumption data :

### Weekly

#### Command line:
```bash
$ pygazpar -u 'your login' -p 'your password' -c 'your PCE identifier' -t 'temporary directory where to store XSLX file (ex: /tmp)' -f WEEKLY
```

#### Library:
```python
import pygazpar

client = pygazpar.Client(username='your login',
                         password='your password',
                         pceIdentifier='your PCE identifier',
                         meterReadingFrequency=pygazpar.Frequency.WEEKLY,
                         lastNDays=10,
                         tmpDirectory='/tmp/pygazpar')

client.update()

data = client.data()
```

#### Output:

```json
data =>
[
  {
    "time_period": "Du 29/03/2021 au 04/04/2021",
    "volume_m3": 21.4,
    "energy_kwh": 240.0,
    "timestamp": "2021-04-20T09:22:12.166500"
  },
  {
    "time_period": "Du 05/04/2021 au 11/04/2021",
    "volume_m3": 58.9,
    "energy_kwh": 663.0,
    "timestamp": "2021-04-20T09:22:12.166500"
  },
  {
    "time_period": "Du 12/04/2021 au 18/04/2021",
    "volume_m3": 57.1,
    "energy_kwh": 643.0,
    "timestamp": "2021-04-20T09:22:12.166500"
  }
]
```

### Monthly

#### Command line:
```bash
$ pygazpar -u 'your login' -p 'your password' -c 'your PCE identifier' -t 'temporary directory where to store XSLX file (ex: /tmp)' -f MONTHLY
```

#### Library:
```python
import pygazpar

client = pygazpar.Client(username='your login',
                         password='your password',
                         pceIdentifier='your PCE identifier',
                         meterReadingFrequency=pygazpar.Frequency.MONTHLY,
                         lastNDays=10,
                         tmpDirectory='/tmp/pygazpar')

client.update()

data = client.data()
```

#### Output:

```json
data =>
[
  {
    "time_period": "F\u00e9vrier 2021",
    "volume_m3": 317.6,
    "energy_kwh": 3547.0,
    "timestamp": "2021-04-20T09:34:31.728125"
  },
  {
    "time_period": "Mars 2021",
    "volume_m3": 261.1,
    "energy_kwh": 2937.0,
    "timestamp": "2021-04-20T09:34:31.728125"
  },
  {
    "time_period": "Avril 2021",
    "volume_m3": 130.7,
    "energy_kwh": 1472.0,
    "timestamp": "2021-04-20T09:34:31.728125"
  }
]
```

### Test mode

In testing environment (unit test or debugging), it may be cumbersome to work with live data: slowness, values are always changing.

There is a test mode that permits to work with static data. Those data are taken from internal resource files.

#### Command line:
```bash
$ pygazpar -u 'your login' -p 'your password' -c 'your PCE identifier' -t 'temporary directory where to store XSLX file (ex: /tmp)' --testMode
```

#### Library:
```python
import pygazpar

client = pygazpar.Client(username='your login',
                         password='your password',
                         pceIdentifier='your PCE identifier',
                         tmpDirectory='/tmp/pygazpar',
                         testMode = True)

client.update()

data = client.data()
```

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