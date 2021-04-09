import os
import argparse


# -------------------------------------------------------------------------------------------------
def updateVersion(currentVersion: str, nextVersion: str):

    file = f"{os.path.dirname(os.path.realpath(__file__))}/pygazpar/version.py"

    print(f"file={file}")

    # read input file
    fin = open(file, "rt")
    # read file contents to string
    data = fin.read()
    # replace all occurrences of the required string
    data = data.replace(currentVersion, nextVersion)
    # close the input file
    fin.close()
    # open the input file in write mode
    fin = open(file, "wt")
    # overrite the input file with the resulting data
    fin.write(data)
    # close the file
    fin.close()


# -------------------------------------------------------------------------------------------------
if __name__ == "__main__":
    # Execute only if run as a script

    parser = argparse.ArgumentParser()

    parser.add_argument("-c", "--currentVersion",
                        required=False,
                        type=str,
                        default="0.0.0-initial",
                        help="Current version number to be replaced in the file version.py")

    parser.add_argument("-n", "--nextVersion",
                        required=True,
                        type=str,
                        help="Next version number to place in the file version.py")

    args = parser.parse_args()

    updateVersion(args.currentVersion, args.nextVersion)
