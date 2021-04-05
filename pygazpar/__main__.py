import argparse
import sys
import json
import traceback
import os
import logging

from pygazpar.client import Client

def main():
    """Main function"""
    parser = argparse.ArgumentParser()
    parser.add_argument("-u", "--username",
                      required=True,
                      help="GRDF username (email)")    
    parser.add_argument("-p", "--password",
                      required=True,
                      help="GRDF password")    
    parser.add_argument("-w", "--webdriver",
                      required=True,
                      help="Firefox webdriver executable (geckodriver)")    
    parser.add_argument("-s", "--wait_time",
                      required=False,
                      type=int,
                      default=30,
                      help="Wait time in seconds (see https://selenium-python.readthedocs.io/waits.html for details)")    
    parser.add_argument("-t", "--tmpdir",
                      required=False,
                      default="/tmp",
                      help="tmp directory (default is /tmp)")
    parser.add_argument("-l", "--lastNRows",
                      required=False,
                      type=int,
                      default=0,
                      help="Get only the last N rows (default is 0: it means all rows are retrieved)")                           

    args = parser.parse_args()

    # We remove the pygazpar log file.
    geckodriverLogFile = f"{args.tmpdir}/pygazpar.log"
    if os.path.isfile(geckodriverLogFile):
        os.remove(geckodriverLogFile)

    # Setup logging.
    logging.basicConfig(filename=f"{args.tmpdir}/pygazpar.log", level=logging.DEBUG, format="%(asctime)s %(levelname)s [%(name)s] %(message)s")

    client = Client(args.username, args.password, args.webdriver, int(args.wait_time), args.tmpdir, int(args.lastNRows))

    try:
        client.update()
    except BaseException:
        print('An error occured while querying PyGazpar library : %s', traceback.format_exc())
        return 1

    print(json.dumps(client.data(), indent=2))

if __name__ == '__main__':
    sys.exit(main())
