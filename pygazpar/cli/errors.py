"""Exit codes of the CLI, and the translation of the errors of PyGazpar into them."""

import logging
import sys
import traceback
from collections.abc import Callable
from functools import wraps
from typing import Any

import typer
from rich.console import Console
from rich.markup import escape

from pygazpar.errors import LoginError, PyGazparError, RateLimitError, ServerError, UnknownPceError

EXIT_OK = 0
EXIT_ERROR = 1
EXIT_USAGE = 2
EXIT_LOGIN = 3
EXIT_UNKNOWN_PCE = 4
EXIT_RATE_LIMIT = 5

Logger = logging.getLogger(__name__)


# ------------------------------------------------------------------------------------------------------------
def exit_code_of(error: BaseException) -> int:
    """Returns the exit code of an error: the most specific one first, as LoginError is a ServerError."""

    if isinstance(error, LoginError):
        return EXIT_LOGIN
    if isinstance(error, UnknownPceError):
        return EXIT_UNKNOWN_PCE
    if isinstance(error, RateLimitError):
        return EXIT_RATE_LIMIT

    return EXIT_ERROR


# ------------------------------------------------------------------------------------------------------------
def fail(message: str, code: int = EXIT_ERROR, *, no_color: bool = False) -> "typer.Exit":
    """Prints an error line on stderr and returns the exception that ends the command with this exit code."""

    Console(stderr=True, no_color=no_color, highlight=False).print(
        f"[bold red]Error:[/bold red] {escape(message)}", markup=True
    )

    return typer.Exit(code)


# ------------------------------------------------------------------------------------------------------------
def handle_errors(function: Callable[..., Any]) -> Callable[..., Any]:
    """Ends a command with a one line message and an exit code, instead of a traceback.

    The traceback is printed on stderr when the log level is DEBUG (-vv).
    """

    @wraps(function)
    def wrapper(*args: Any, **kwargs: Any) -> Any:
        try:
            return function(*args, **kwargs)
        except typer.Exit:
            raise
        except (PyGazparError, OSError, ValueError) as error:
            if Logger.isEnabledFor(logging.DEBUG) or logging.getLogger().isEnabledFor(logging.DEBUG):
                print(traceback.format_exc(), file=sys.stderr)
            detail = f"{error} (HTTP {error.status_code})" if isinstance(error, ServerError) else str(error)
            raise fail(detail or type(error).__name__, exit_code_of(error)) from error

    return wrapper
