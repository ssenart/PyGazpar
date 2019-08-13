import unittest

from pygazpar.client import Client

class ClientTestCase(unittest.TestCase):

    username = ""
    password = ""
    webdriver = ""
    tmp_directory = ""

    def test_client(self):
        client = Client(self.username, self.password, self.webdriver, self.tmp_directory)
        client.update()

        assert len(client.data) != 0

if __name__ == "__main__":

    from argparse import ArgumentParser
    parser = ArgumentParser()
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

    ClientTestCase.username = args.username
    ClientTestCase.password = args.password
    ClientTestCase.webdriver = args.webdriver
    ClientTestCase.tmp_directory = args.tmpdir

    unittest.main()