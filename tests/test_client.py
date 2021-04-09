from pygazpar.client import Client


class ClientTestCase:

    username = ""
    password = ""
    webdriver = ""
    wait_time = 30
    tmp_directory = ""

    def test_client(self):
        client = Client(self.username, self.password, self.webdriver, self.wait_time, self.tmp_directory)
        client.update()

        assert len(client.data()) != 0
