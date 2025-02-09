import json
import os
import sys

import dotenv

import pygazpar


def main():

    # Load environment variables GRDF_USERNAME, GRDF_PASSWORD, PCE_IDENTIFIER from .env file.
    dotenv.load_dotenv()

    username = os.environ["GRDF_USERNAME"]
    password = os.environ["GRDF_PASSWORD"]
    pce_identifier = os.environ["PCE_IDENTIFIER"]

    client = pygazpar.Client(pygazpar.JsonWebDataSource(username=username, password=password))

    data = client.load_since(
        pce_identifier=pce_identifier, last_n_days=60, frequencies=[pygazpar.Frequency.DAILY, pygazpar.Frequency.MONTHLY]
    )

    print(json.dumps(data, indent=2))


if __name__ == "__main__":
    sys.exit(main())
