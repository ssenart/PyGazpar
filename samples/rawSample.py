"""Reads the GrDF API responses as received, without PyGazpar's post processing.

Useful to see what GrDF really sends, to report a problem, or to save a response and work on it offline (see
offlineFilesSample.py). The command line equivalent is `pygazpar api consumption --raw` and `pygazpar api meteo --raw`.

Same environment as jsonSample.py.
"""

import logging
import os
import sys
from datetime import date, timedelta

import dotenv

import pygazpar


def main() -> int:

    logging.basicConfig(level=logging.WARNING)
    dotenv.load_dotenv()

    try:
        username = os.environ["GRDF_USERNAME"]
        password = os.environ["GRDF_PASSWORD"]
        pce_identifier = os.environ["PCE_IDENTIFIER"]
    except KeyError as error:
        print(f"Set {error.args[0]} in the environment or in a .env file.", file=sys.stderr)
        return 2

    end_date = date.today()
    start_date = end_date - timedelta(days=30)

    consumption_source = pygazpar.RawConsumptionWebDataSource(username, password, pygazpar.ConsumptionType.INFORMATIVE)
    temperature_source = pygazpar.RawTemperatureWebDataSource(username, password)

    try:
        try:
            # A raw source logs in by itself on the first load().
            consumption = consumption_source.load(pce_identifier, start_date, end_date)
            temperatures = temperature_source.load(pce_identifier, start_date, end_date)
        finally:
            # logout() closes its session.
            consumption_source.logout()
            temperature_source.logout()
    except pygazpar.PyGazparError as error:
        print(f"GrDF error: {error}", file=sys.stderr)
        return 1

    # Both are dictionaries, as returned by GrDF: the consumption by PCE, the temperatures by day.
    for pce, response in consumption.items():
        print(f"PCE {pce}: {len(response['releves'])} records")
    print(f"{len(temperatures)} days of temperatures")

    return 0


if __name__ == "__main__":
    sys.exit(main())
