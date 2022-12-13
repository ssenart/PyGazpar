import sys
import os
import dotenv
import json
import pygazpar


def main():

    # Load environment variables GRDF_USERNAME, GRDF_PASSWORD, PCE_IDENTIFIER from .env file.
    dotenv.load_dotenv()

    username = os.environ["GRDF_USERNAME"]
    password = os.environ["GRDF_PASSWORD"]
    pceIdentifier = os.environ["PCE_IDENTIFIER"]

    client = pygazpar.Client(pygazpar.ExcelWebDataSource(
        username=username,
        password=password,
        tmpDirectory="tmp")
    )

    data = client.loadSince(pceIdentifier=pceIdentifier,
                            lastNDays=60,
                            frequencies=[pygazpar.Frequency.DAILY, pygazpar.Frequency.MONTHLY])

    print(json.dumps(data, indent=2))


if __name__ == '__main__':
    sys.exit(main())
