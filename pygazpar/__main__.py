import argparse
import json
import logging
import os
import sys
import traceback
from datetime import date, timedelta

from dotenv import find_dotenv, load_dotenv

import pygazpar

Logger = logging.getLogger(__name__)

RAW_DATASOURCES = ("raw-consumption", "raw-temperature")


def consumption_type_of(args) -> pygazpar.ConsumptionType:
    """Returns the consumption type selected with --consumption-type (INFORMATIVE by default)."""
    return pygazpar.ConsumptionType[args.consumption_type or "INFORMATIVE"]


def fill_credentials_from_env(args, parser: argparse.ArgumentParser) -> None:
    """Fills the credentials missing from the command line with GRDF_USERNAME, GRDF_PASSWORD and PCE_IDENTIFIER."""
    args.username = args.username or os.environ.get("GRDF_USERNAME")
    args.password = args.password or os.environ.get("GRDF_PASSWORD")
    args.pce = args.pce or os.environ.get("PCE_IDENTIFIER")

    if not all((args.username, args.password, args.pce)):
        parser.error(
            "credentials are required: pass -u, -p and -c, or set GRDF_USERNAME, GRDF_PASSWORD and PCE_IDENTIFIER"
        )


def load_raw(args) -> int:
    """Prints the GrDF API response of a raw datasource as received, bypassing the Client."""
    end_date = date.today()
    start_date = end_date - timedelta(days=int(args.lastNDays))
    try:
        if args.datasource == "raw-consumption":
            raw_data = pygazpar.RawConsumptionWebDataSource(
                args.username, args.password, consumption_type_of(args)
            ).load(args.pce, start_date, end_date)
        else:
            raw_data = pygazpar.RawTemperatureWebDataSource(args.username, args.password).load(
                args.pce, start_date, end_date
            )
    except BaseException:  # noqa: BLE001
        print(f"An error occured while querying PyGazpar library : {traceback.format_exc()}", file=sys.stderr)
        return 1

    print(json.dumps(raw_data, indent=2))
    return 0


def main():
    """Main function"""
    parser = argparse.ArgumentParser()
    parser.add_argument("-v", "--version", action="version", version=f"PyGazpar {pygazpar.__version__}")
    parser.add_argument("-u", "--username", required=False, help="GRDF username (email), or GRDF_USERNAME")
    parser.add_argument("-p", "--password", required=False, help="GRDF password, or GRDF_PASSWORD")
    parser.add_argument("-c", "--pce", required=False, help="GRDF PCE identifier, or PCE_IDENTIFIER")
    parser.add_argument("-t", "--tmpdir", required=False, default="/tmp", help="tmp directory (default is /tmp)")
    parser.add_argument(
        "-f",
        "--frequency",
        required=False,
        type=lambda frequency: pygazpar.Frequency[frequency],
        choices=list(pygazpar.Frequency),
        default="DAILY",
        help="Meter reading frequency (DAILY, WEEKLY, MONTHLY, YEARLY)",
    )
    parser.add_argument(
        "-d",
        "--lastNDays",
        required=False,
        type=int,
        default=365,
        help="Get only the last N days of records (default: 365 days)",
    )
    parser.add_argument(
        "--datasource",
        required=False,
        choices=["json", "excel", "test", "raw-consumption", "raw-temperature"],
        default="json",
        help="Datasource: json | excel | test | raw-consumption | raw-temperature "
        "(raw sources print the GrDF API response without post processing and ignore --frequency)",
    )
    parser.add_argument(
        "--consumption-type",
        required=False,
        choices=[consumption_type.name for consumption_type in pygazpar.ConsumptionType],
        default=None,
        help="Consumption type (INFORMATIVE by default), for --datasource json or raw-consumption",
    )

    args = parser.parse_args()

    # Credentials missing from the command line come from the environment, or from a .env file in the working directory.
    load_dotenv(find_dotenv(usecwd=True))
    fill_credentials_from_env(args, parser)

    if args.consumption_type is not None and args.datasource not in ("json", "raw-consumption"):
        parser.error("--consumption-type requires --datasource json or raw-consumption")

    # In raw mode, stdout is reserved for the JSON payload.
    info_stream = sys.stderr if args.datasource in RAW_DATASOURCES else sys.stdout

    print(f"PyGazpar version: {pygazpar.__version__}", file=info_stream)
    print(f"Running on Python version: {sys.version}", file=info_stream)

    # We create the tmp directory if not already exists.
    if not os.path.exists(args.tmpdir):
        os.mkdir(args.tmpdir)

    # We remove the pygazpar log file.
    pygazparLogFile = f"{args.tmpdir}/pygazpar.log"
    if os.path.isfile(pygazparLogFile):
        os.remove(pygazparLogFile)

    # Setup logging.
    logging.basicConfig(
        filename=f"{pygazparLogFile}", level=logging.DEBUG, format="%(asctime)s %(levelname)s [%(name)s] %(message)s"
    )

    Logger.info(f"PyGazpar version: {pygazpar.__version__}")
    Logger.info(f"Running on Python version: {sys.version}")
    Logger.info(f"--tmpdir {args.tmpdir}")
    Logger.info(f"--frequency {args.frequency}")
    Logger.info(f"--lastNDays {args.lastNDays}")
    Logger.info(f"--datasource {args.datasource}")

    if args.datasource in RAW_DATASOURCES:
        return load_raw(args)

    if args.datasource == "json":
        client = pygazpar.Client(pygazpar.JsonWebDataSource(args.username, args.password, consumption_type_of(args)))
    elif args.datasource == "excel":
        client = pygazpar.Client(pygazpar.ExcelWebDataSource(args.username, args.password, args.tmpdir))
    else:
        client = pygazpar.Client(pygazpar.TestDataSource())

    try:
        data = client.load_since(args.pce, int(args.lastNDays), [args.frequency])
    except BaseException:  # noqa: BLE001
        print(f"An error occured while querying PyGazpar library : {traceback.format_exc()}", file=sys.stderr)
        return 1

    Logger.info(f"Data loaded: {len(data)} records")
    Logger.debug(f"Data: {data}")
    print(json.dumps(data, indent=2))

    return 0


if __name__ == "__main__":
    sys.exit(main())
