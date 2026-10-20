"""Reads the published consumption of the last year, with explicit dates.

Some PCEs expose no (or only the latest) history as informative consumption, but a longer one as published consumption:
GrDF publishes periods of several days, which PyGazpar turns into one row per day. Those days have the type `Calculé`.
See docs/published-readings.md.

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
    start_date = end_date - timedelta(days=365)

    data_source = pygazpar.JsonWebDataSource(
        username=username, password=password, consumption_type=pygazpar.ConsumptionType.PUBLISHED
    )

    try:
        with pygazpar.Client(data_source) as client:
            # load_readings_date_range takes explicit dates, where load_readings_since counts back from today.
            readings = client.load_readings_date_range(
                pce_identifier=pce_identifier,
                start_date=start_date,
                end_date=end_date,
                frequencies=[pygazpar.Frequency.DAILY],
            )
    except pygazpar.PyGazparError as error:
        print(f"GrDF error: {error}", file=sys.stderr)
        return 1

    daily = readings[pygazpar.Frequency.DAILY]
    calculated = [
        reading for reading in daily if isinstance(reading, pygazpar.DailyReading) and reading.type_ == "Calculé"
    ]
    print(f"{len(daily)} days from {start_date} to {end_date}, {len(calculated)} of them calculated from a period")

    return 0


if __name__ == "__main__":
    sys.exit(main())
