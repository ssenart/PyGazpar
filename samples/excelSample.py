"""Reads the daily and monthly consumption of the last 60 days from GrDF's Excel export.

Same environment as jsonSample.py. The Excel files GrDF sends are stored in a temporary directory.
"""

import logging
import os
import sys
import tempfile

import dotenv

import pygazpar


def main() -> int:

    logging.basicConfig(level=logging.WARNING)

    # Load environment variables GRDF_USERNAME, GRDF_PASSWORD, PCE_IDENTIFIER from .env file.
    dotenv.load_dotenv()

    try:
        username = os.environ["GRDF_USERNAME"]
        password = os.environ["GRDF_PASSWORD"]
    except KeyError as error:
        print(f"Set {error.args[0]} in the environment or in a .env file.", file=sys.stderr)
        return 2

    try:
        # A temporary directory is created for the Excel files, and removed at the end.
        with tempfile.TemporaryDirectory() as tmp_directory:
            data_source = pygazpar.ExcelWebDataSource(username=username, password=password, tmp_directory=tmp_directory)

            with pygazpar.Client(data_source) as client:
                pce_identifiers = client.get_pce_identifiers()
                pce_identifier = os.environ.get("PCE_IDENTIFIER") or (
                    pce_identifiers[0] if len(pce_identifiers) == 1 else ""
                )
                if not pce_identifier:
                    print(f"Set PCE_IDENTIFIER to one of: {', '.join(pce_identifiers)}", file=sys.stderr)
                    return 2

                readings = client.load_readings_since(
                    pce_identifier=pce_identifier,
                    last_n_days=60,
                    frequencies=[pygazpar.Frequency.DAILY, pygazpar.Frequency.MONTHLY],
                )
    except pygazpar.LoginError as error:
        print(f"GrDF refused the login: {error}", file=sys.stderr)
        return 1
    except pygazpar.UnknownPceError as error:
        print(error, file=sys.stderr)
        return 1
    except pygazpar.RateLimitError:
        print("GrDF is limiting the calls: wait a few minutes and try again.", file=sys.stderr)
        return 1
    except pygazpar.PyGazparError as error:
        print(f"GrDF error: {error}", file=sys.stderr)
        return 1

    for frequency, rows in readings.items():
        print(f"{frequency.value}: {len(rows)} readings")
        for reading in rows:
            print(f"  {reading.time_period}: {reading.volume_m3} m3, {reading.energy_kwh} kWh")

    return 0


if __name__ == "__main__":
    sys.exit(main())
