"""The errors of PyGazpar. Every one of them is a PyGazparError."""


# ------------------------------------------------------------------------------------------------------------
class PyGazparError(Exception):
    """The base of the errors that PyGazpar raises on its own."""


# ------------------------------------------------------------------------------------------------------------
class ServerError(PyGazparError):
    """GrDF answered with an error, or did not answer as expected."""

    def __init__(self, message: str, status_code: int):
        super().__init__(message)
        self.status_code = status_code


# ------------------------------------------------------------------------------------------------------------
class InternalServerError(ServerError):
    """GrDF answered with an HTML page instead of data: it did not understand the query, or it failed."""

    def __init__(self, message: str):
        super().__init__(message, 500)


# ------------------------------------------------------------------------------------------------------------
class LoginError(ServerError):
    """GrDF refused the login: the credentials are wrong, or the login page changed."""


# ------------------------------------------------------------------------------------------------------------
class RateLimitError(ServerError):
    """GrDF refused the calls sent back to back (HTTP 429), and kept refusing them after the retries."""

    def __init__(self, message: str):
        super().__init__(message, 429)


# ------------------------------------------------------------------------------------------------------------
class NotLoggedInError(PyGazparError, ConnectionError):
    """A call needs a session: the client has not logged in, or has logged out."""


# ------------------------------------------------------------------------------------------------------------
class UnknownPceError(PyGazparError, LookupError):
    """The PCE identifier is not one of the PCEs of the account."""

    def __init__(self, pce_identifier: str):
        super().__init__(f"The PCE {pce_identifier} does not exist in this account.")
        self.pce_identifier = pce_identifier
