import sys
import json
import pygazpar


def main():

    client = pygazpar.Client(pygazpar.TestDataSource())

    data = client.loadSince(pceIdentifier="xxx",
                            lastNDays=60,
                            frequencies=[pygazpar.Frequency.DAILY, pygazpar.Frequency.MONTHLY])

    print(json.dumps(data, indent=2))


if __name__ == '__main__':
    sys.exit(main())
