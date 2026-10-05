import json
from unittest import mock

import pytest

from pygazpar.api_client import APIClient

USERNAME = "user@example.com"


def fake_response(body=None, text=""):
    response = mock.Mock()
    response.status_code = 200
    response.text = text
    response.json.return_value = body
    return response


def login_with_a_mocked_session(password):
    """Logs in against a mocked session, and returns the bodies sent to the two login POST requests."""

    session = mock.Mock()
    session.get.side_effect = [
        fake_response(text='"stateToken" : "STATE"'),
        fake_response(),
    ]
    session.post.side_effect = [
        fake_response(body={"stateHandle": "HANDLE"}),
        fake_response(body={"success": {"href": "https://monespace.grdf.fr/success"}}),
    ]

    with mock.patch("pygazpar.api_client.Session", return_value=session):
        APIClient(USERNAME, password).login()

    identifier_body, password_body = (call.kwargs["data"] for call in session.post.call_args_list)

    return identifier_body, password_body


class TestLoginPayload:
    # ------------------------------------------------------
    @pytest.mark.parametrize(
        "password",
        ["plain", 'with"quote', "back\\slash", "tab\there", "hash#%&+ok", "accent-é", "euro€"],
    )
    def test_password_is_sent_exactly_as_typed(self, password):
        _, password_body = login_with_a_mocked_session(password)

        assert json.loads(password_body)["credentials"]["passcode"] == password

    # ------------------------------------------------------
    def test_username_is_sent_as_the_identifier(self):
        identifier_body, _ = login_with_a_mocked_session("plain")

        assert json.loads(identifier_body) == {"identifier": USERNAME, "stateHandle": "STATE"}
