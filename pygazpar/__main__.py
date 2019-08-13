import argparse
import sys
import json

from pygazpar.client import Client

def main():
    """Main function"""
    parser = argparse.ArgumentParser()
    parser.add_argument("--username",
                      action="store",
                      dest="username",
                      help="GRDF username (email)")    
    parser.add_argument("--password",
                      action="store",
                      dest="password",
                      help="GRDF password")    
    parser.add_argument("--webdriver",
                      action="store",
                      dest="webdriver",
                      help="Firefox webdriver executable")    
    parser.add_argument("--tmpdir",
                      action="store",
                      dest="tmpdir",
                      help="tmp directory")    

    args = parser.parse_args()

    client = Client(args.username, args.password, args.webdriver, args.tmpdir)

    try:
        client.update()
    except BaseException as exp:
        print(exp)
        return 1

    print(json.dumps(client.data, indent=2))


if __name__ == '__main__':
    sys.exit(main())
