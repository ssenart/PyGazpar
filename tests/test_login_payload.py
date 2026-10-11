import json
from unittest import mock

import pytest

from pygazpar.api_client import PASSWORD_SESSION_TOKEN_URL, APIClient

USERNAME = "user@example.com"

# The remediation GrDF is expected to offer after identify, matching the fixed URL pygazpar posts the password to.
CHALLENGE_AUTHENTICATOR_REMEDIATION = {
    "type": "array",
    "value": [{"rel": ["create-form"], "name": "challenge-authenticator", "href": PASSWORD_SESSION_TOKEN_URL}],
}


def fake_response(body=None, text=""):
    response = mock.Mock()
    response.status_code = 200
    response.text = text
    response.json.return_value = body
    return response


def login_with_a_mocked_session(password, mail_remediation=CHALLENGE_AUTHENTICATOR_REMEDIATION):
    """Logs in against a mocked session, and returns the bodies sent to the two login POST requests."""

    session = mock.Mock()
    session.get.side_effect = [
        fake_response(text='"stateToken" : "STATE"'),
        fake_response(),
    ]
    session.post.side_effect = [
        fake_response(body={"stateHandle": "HANDLE", "remediation": mail_remediation}),
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

    # ------------------------------------------------------
    def test_the_identify_step_answer_is_logged_without_its_state_handle(self, caplog):
        """Whatever GrDF/Okta asks for next (plainly a password challenge, or a different remediation) must reach
        the logs, since the identify step always succeeds in the reported cases - only the next step fails. The
        state handle is a token and must not leak into the logs."""

        with caplog.at_level("DEBUG", logger="pygazpar.api_client"):
            login_with_a_mocked_session("plain")

        identify_logs = [record.message for record in caplog.records if "GrDF identify response body" in record.message]

        assert len(identify_logs) == 1
        assert "HANDLE" not in identify_logs[0]


class TestRemediationCheck:
    """pygazpar still posts the password to its fixed URL regardless (see login_with_a_mocked_session): these
    tests are about what gets logged, i.e. whether the generic, spec-compliant reading of the identify answer
    agrees with that fixed URL - not about changing what pygazpar actually does yet."""

    # ------------------------------------------------------
    def test_a_matching_challenge_authenticator_remediation_logs_no_warning(self, caplog):
        with caplog.at_level("DEBUG", logger="pygazpar.api_client"):
            login_with_a_mocked_session("plain")

        assert not [r for r in caplog.records if r.levelname == "WARNING"]

    # ------------------------------------------------------
    def test_a_different_remediation_is_reported_by_name(self, caplog):
        other_remediation = {"type": "array", "value": [{"name": "select-authenticator-authenticate"}]}

        with caplog.at_level("DEBUG", logger="pygazpar.api_client"):
            login_with_a_mocked_session("plain", mail_remediation=other_remediation)

        warnings = [r.message for r in caplog.records if r.levelname == "WARNING"]

        assert len(warnings) == 1
        assert "select-authenticator-authenticate" in warnings[0]

    # ------------------------------------------------------
    def test_a_challenge_authenticator_remediation_with_a_different_href_is_reported(self, caplog):
        other_href_remediation = {
            "type": "array",
            "value": [{"name": "challenge-authenticator", "href": "https://connexion.grdf.fr/idp/idx/elsewhere"}],
        }

        with caplog.at_level("DEBUG", logger="pygazpar.api_client"):
            login_with_a_mocked_session("plain", mail_remediation=other_href_remediation)

        warnings = [r.message for r in caplog.records if r.levelname == "WARNING"]

        assert len(warnings) == 1
        assert "idp/idx/elsewhere" in warnings[0]
