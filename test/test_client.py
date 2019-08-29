import unittest

from pygazpar.client import Client

class ClientTestCase(unittest.TestCase):

    username = ""
    password = ""
    webdriver = ""
    wait_time = 30
    tmp_directory = ""

    def test_client(self):
        client = Client(self.username, self.password, self.webdriver, self.wait_time, self.tmp_directory)
        client.update()

        assert len(client.data()) != 0

if __name__ == "__main__":

    from argparse import ArgumentParser
    parser = ArgumentParser()
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
  
    args = parser.parse_args()

    ClientTestCase.username = args.username
    ClientTestCase.password = args.password
    ClientTestCase.webdriver = args.webdriver
    ClientTestCase.wait_time = args.wait_time
    ClientTestCase.tmp_directory = args.tmpdir

    unittest.main()