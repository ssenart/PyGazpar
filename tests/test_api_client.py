import os
from datetime import date

import pytest

from pygazpar.api_client import APIClient, ConsumptionType, Frequency, ServerError


class TestAPIClient:

    # ------------------------------------------------------
    @classmethod
    def setup_class(cls):
        """setup any state specific to the execution of the given class (which
        usually contains tests).
        """
        cls._username = os.environ["GRDF_USERNAME"]
        cls._password = os.environ["GRDF_PASSWORD"]
        cls._pceIdentifier = os.environ["PCE_IDENTIFIER"]

        cls._client = APIClient(cls._username, cls._password)
        cls._client.login()

    # ------------------------------------------------------
    @classmethod
    def teardown_class(cls):
        """teardown any state that was previously setup with a call to
        setup_class.
        """
        cls._client.logout()

    # ------------------------------------------------------
    def setup_method(self):
        """setup any state tied to the execution of the given method in a
        class.  setup_method is invoked for every test method of a class.
        """

    # ------------------------------------------------------
    def teardown_method(self):
        """teardown any state that was previously setup with a setup_method
        call.
        """

    # ------------------------------------------------------
    def test_login_logout(self):

        client = APIClient(self._username, self._password)

        client.login()

        assert client.is_logged_in() is True

        client.logout()

        assert client.is_logged_in() is False

    # ------------------------------------------------------
    def test_login_error(self):

        client = APIClient("WrongUsername", "WrongPassword")

        with pytest.raises(ServerError, match="Authentication failed"):
            client.login()

    # ------------------------------------------------------
    def test_get_pce_list(self):

        pce_list_no_details = TestAPIClient._client.get_pce_list()

        assert len(pce_list_no_details) > 0

        pce_list_details = TestAPIClient._client.get_pce_list(True)

        assert len(pce_list_details) > 0

    # ------------------------------------------------------
    def test_get_pce_consumption(self):

        start_date = date(2025, 1, 1)
        end_date = date(2025, 1, 7)

        pce_consumption_informative = TestAPIClient._client.get_pce_consumption(
            ConsumptionType.INFORMATIVE, start_date, end_date, [TestAPIClient._pceIdentifier]
        )

        assert len(pce_consumption_informative) > 0

        pce_consumption_published = TestAPIClient._client.get_pce_consumption(
            ConsumptionType.PUBLISHED, start_date, end_date, [TestAPIClient._pceIdentifier]
        )

        assert len(pce_consumption_published) > 0

        no_result = TestAPIClient._client.get_pce_consumption(
            ConsumptionType.INFORMATIVE, date(2010, 1, 1), date(2010, 1, 7), [TestAPIClient._pceIdentifier]
        )

        assert len(no_result) == 0

        no_result = TestAPIClient._client.get_pce_consumption(
            ConsumptionType.INFORMATIVE, start_date, end_date, ["InvalidPceIdentifier"]
        )

        assert len(no_result) == 0

    # ------------------------------------------------------
    def test_get_pce_consumption_excelsheet(self):

        start_date = date(2025, 1, 1)
        end_date = date(2025, 1, 7)

        pce_consumption_informative = TestAPIClient._client.get_pce_consumption_excelsheet(
            ConsumptionType.INFORMATIVE, start_date, end_date, Frequency.DAILY, [TestAPIClient._pceIdentifier]
        )

        assert len(pce_consumption_informative) > 0

    # ------------------------------------------------------
    def test_get_pce_meteo(self):

        end_date = date(2025, 1, 2)

        pce_meteo = TestAPIClient._client.get_pce_meteo(end_date, 2, TestAPIClient._pceIdentifier)

        assert len(pce_meteo) > 0

        pce_meteo_no_result = TestAPIClient._client.get_pce_meteo(date(2010, 1, 2), 7, TestAPIClient._pceIdentifier)

        assert len(pce_meteo_no_result) == 0

        with pytest.raises(ServerError, match="Le pce InvalidPceIdentifier n'existe pas !"):
            TestAPIClient._client.get_pce_meteo(end_date, 7, "InvalidPceIdentifier")
