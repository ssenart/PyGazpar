from pygazpar.client import Client
import pytest


class TestClient:

    username = ""
    password = ""
    webdriver = ""
    wait_time = 30
    tmp_directory = ""

    @pytest.mark.skip(reason="Requires credentials")
    def test_client(self):
        client = Client(self.username, self.password, self.webdriver, self.wait_time, self.tmp_directory)
        client.update()

        assert len(client.data()) != 0

    def test_empty(self):
        assert 1 == 1
