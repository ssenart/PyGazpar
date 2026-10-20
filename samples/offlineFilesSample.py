"""Reads readings from files saved earlier: no account and no connection to GrDF needed.

    python -m samples.offlineFilesSample consumption.json temperature.json
    python -m samples.offlineFilesSample Donnees_informatives_PCE_DAILY.xlsx

The JSON files are the responses saved with `pygazpar api consumption --raw -o consumption.json` and
`pygazpar api meteo --raw -o temperature.json` (see rawSample.py). The Excel file is one downloaded from GrDF, or with
`pygazpar api excel`. An Excel file holds one frequency: the one of the file.
"""

import json
import sys

import pygazpar


def main(argv: list[str]) -> int:

    if len(argv) == 3 and argv[1].endswith(".json"):
        consumption_file, temperature_file = argv[1], argv[2]
        data_source: pygazpar.IDataSource = pygazpar.JsonFileDataSource(consumption_file, temperature_file)
        frequencies = [pygazpar.Frequency.DAILY, pygazpar.Frequency.MONTHLY]
    elif len(argv) == 2 and argv[1].endswith(".xlsx"):
        consumption_file = ""
        data_source = pygazpar.ExcelFileDataSource(argv[1])
        frequencies = [pygazpar.Frequency.DAILY]
    else:
        print(__doc__, file=sys.stderr)
        return 2

    try:
        if consumption_file:
            # The consumption file is keyed by PCE identifier: read it from there, as the datasource has no account to ask.
            with open(consumption_file, encoding="utf-8") as file:
                pce_identifier = next(iter(json.load(file)))
        else:
            pce_identifier = data_source.get_pce_identifiers()[0]

        with pygazpar.Client(data_source) as client:
            # The dates are ignored: a file holds what it holds.
            readings = client.load_readings_since(pce_identifier, frequencies=frequencies)
    except (pygazpar.PyGazparError, OSError, ValueError) as error:
        print(f"Cannot read the file: {error}", file=sys.stderr)
        return 1

    for frequency, rows in readings.items():
        print(f"{frequency.value}: {len(rows)} readings")

    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
