import json
import sys

import pygazpar


def main():

    client = pygazpar.Client(pygazpar.TestDataSource())

    data = client.load_since(
        pce_identifier="xxx", last_n_days=60, frequencies=[pygazpar.Frequency.DAILY, pygazpar.Frequency.MONTHLY]
    )

    print(json.dumps(data, indent=2))


if __name__ == "__main__":
    sys.exit(main())
