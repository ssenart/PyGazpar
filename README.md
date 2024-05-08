# PyGazpar

## <span style="color:green">!!! This library is working again. CAPTCHA has been removed !!!</span>

## <span style="color:red">~~!!! This library is broken since CAPTCHA is mandatory on GrDF site !!!~~</span>

PyGazpar is a Python library for getting natural gas consumption from GrDF French provider.

Their natural gas meter is called Gazpar. It is wireless and transmit the gas consumption once per day.

All consumption data is available on the client account at GrDF Web Site (https://monespace.grdf.fr).

PyGazpar automatically goes through the Web Site and download the consumption data, and make it available in a Python structure.

## Installation

### Requirements
PyGazpar does not require Selenium and corresponding geckodriver to work.

With the new GrDF web site, it is possible to load the consumption data far easily than before.

### Create your virtual environment
```bash
$ cd /path/to/my_project_folder/

$ python -m venv .venv
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

1. Standard usage (using Json GrDF API).

```bash
$ pygazpar -u 'your login' -p 'your password' -c 'your PCE identifier' --datasource 'json'
```

2. Alternate usage (using Excel GrDF document).

```bash
$ pygazpar -u 'your login' -p 'your password' -c 'your PCE identifier' -t 'temporary directory where to store Excel file (ex: /tmp)' --datasource 'excel'
```

3. Test usage (using local static data files, do not connect to GrDF site).

```bash
$ pygazpar -u 'your login' -p 'your password' -c 'your PCE identifier' --datasource 'test'
```

#### Library:

1. Standard usage (using Json GrDF API).

```python
import pygazpar

client = pygazpar.Client(pygazpar.JsonWebDataSource(
    username='your login',
    password='your password')
)

data = client.loadSince(pceIdentifier='your PCE identifier',
                        lastNDays=60,
                        frequencies=[pygazpar.Frequency.DAILY, pygazpar.Frequency.MONTHLY])
```
See [samples/jsonSample.py](samples/jsonSample.py) file for the full example.

2. Alternate usage (using Excel GrDF document).

```python
import pygazpar

client = pygazpar.Client(pygazpar.ExcelWebDataSource(
    username='your login',
    password='your password')
)

data = client.loadSince(pceIdentifier='your PCE identifier',
                        lastNDays=60,
                        frequencies=[pygazpar.Frequency.DAILY, pygazpar.Frequency.MONTHLY])
```
See [samples/excelSample.py](samples/jsonSample.py) file for the full example.

3. Test usage (using local static data files, do not connect to GrDF site).

```python
import pygazpar

client = pygazpar.Client(pygazpar.TestDataSource())

data = client.loadSince(pceIdentifier='your PCE identifier',
                        lastNDays=10,
                        frequencies=[pygazpar.Frequency.DAILY, Frequency.MONTHLY])
```
See [samples/testSample.py](samples/jsonSample.py) file for the full example.

#### Output:

```json
data =>
{
  "daily": [
    {
      "time_period": "13/10/2022",
      "start_index_m3": 15724,
      "end_index_m3": 15725,
      "volume_m3": 2,
      "energy_kwh": 17,
      "converter_factor_kwh/m3": 11.16,
      "temperature_degC": null,
      "type": "Mesur\u00e9",
      "timestamp": "2022-12-13T23:58:35.606763"
    },
    ...
    {
      "time_period": "11/12/2022",
      "start_index_m3": 16081,
      "end_index_m3": 16098,
      "volume_m3": 18,
      "energy_kwh": 201,
      "converter_factor_kwh/m3": 11.27,
      "temperature_degC": -1.47,
      "type": "Mesur\u00e9",
      "timestamp": "2022-12-13T23:58:35.606763"
    }
  ],
  "monthly": [
    {
      "time_period": "Novembre 2022",
      "start_index_m3": 15750,
      "end_index_m3": 15950,
      "volume_m3": 204,
      "energy_kwh": 2227,
      "timestamp": "2022-12-13T23:58:35.606763"
    },
    {
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