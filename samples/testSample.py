"""Reads the sample data bundled with PyGazpar: no account and no connection to GrDF needed.

A good way to see what the data looks like, or to try your code before using real credentials.
"""

import json
import sys

import pygazpar


def main() -> int:

    with pygazpar.Client(pygazpar.TestDataSource()) as client:
        # The test datasource ignores the PCE identifier and the dates.
        pce_identifier = client.get_pce_identifiers()[0]

        # The typed form: models with attributes.
        readings = client.load_readings_since(
            pce_identifier=pce_identifier,
            last_n_days=60,
            frequencies=[pygazpar.Frequency.DAILY, pygazpar.Frequency.MONTHLY],
        )

        # The dict form, as JSON-ready data: this is what the command line prints with --format json.
        data = client.load_since(
            pce_identifier=pce_identifier,
            last_n_days=60,
            frequencies=[pygazpar.Frequency.DAILY, pygazpar.Frequency.MONTHLY],
        )

    for frequency, rows in readings.items():
        print(f"{frequency.value}: {len(rows)} readings")

    first_day = readings[pygazpar.Frequency.DAILY][0]
    print(f"First day: {first_day.time_period}, {first_day.volume_m3} m3, {first_day.energy_kwh} kWh")
    print(json.dumps(data[pygazpar.Frequency.DAILY][0], indent=2, ensure_ascii=False))

    return 0


if __name__ == "__main__":
    sys.exit(main())
