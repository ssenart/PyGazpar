# PyGazpar
PyGazpar is a Python library for getting natural gas consumption from GrDF French provider.

Their natural gas meter is called Gazpar. It is wireless and transmit the gas consumption once per day.

All consumption data is available on the client account at GrDF Web Site (https://monespace.grdf.fr).

PyGazpar automatically go through the Web Site and download the consumption data Excel file, and make it available in a Python structure (list of dictionaries).

## Installation

### Requirements
PyGazpar is working with Selenium Python library to automate navigation through GrDF Web site. Selenium requires a WebDriver that acts as gateway between automatic actions from PyGazpar and a native browser already installed on the system.

PyGazpar has been developped and tested with Firefox browser (version 68.8) and its corresponding Web Driver geckodriver (version 0.24).

#### Firefox browser installation
Follow instructions [here](https://www.mozilla.org/fr/firefox/new)

#### Firefox Web Driver (geckodriver) installation
Follow instructions [here](https://github.com/mozilla/geckodriver/releases)

### PyGazpar installation
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

### Command line

```bash

$ pygazpar -u 'your login' -p 'your password' -w 'path/to/Selenium Web Driver' -t 'temporary directory where to store XSLX file (ex: /tmp)'

```

### Library

```python
import pygazpar

client = pygazpar.Client('your login',
                         'your password',
                         'path/to/Selenium Web Driver',
                         'temporary directory where to store XSLX file (ex: /tmp)')

client.update()

data = client.data()
```

```json
data =>
[
  {
    "time": "22/08/2019",
    "total_m3": 9904.0,
    "total_kWh": 111360.576,
    "daily_m3": 1.2,
    "daily_kWh": 13.0
  },
  {
    "time": "23/08/2019",
    "total_m3": 9905.0,
    "total_kWh": 111371.81999999999,
    "daily_m3": 1.1,
    "daily_kWh": 12.0
  },
  {
    "time": "24/08/2019",
    "total_m3": 9906.0,
    "total_kWh": 111383.064,
    "daily_m3": 1.1,
    "daily_kWh": 12.0
  }
]
```

## Limitation
PyGazpar relies on how GrDF Web Site is built. It goes through each Web pages and automatically fill forms, click buttons using their internal identifiers.

Any change in the Web site structure or identifier naming may break this library.

We expect in close Future that GrDF makes available a standard API from which we can get safely their data.

## Contributing
Pull requests are welcome. For major changes, please open an issue first to discuss what you would like to change.

Please make sure to update tests as appropriate.

## License
[MIT](https://choosealicense.com/licenses/mit/)

## Project status
PyGazpar has been initiated for integration with [Home Assistant](https://www.home-assistant.io/). This integration work is still on-going.