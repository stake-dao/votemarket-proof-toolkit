"""Shared command helpers and utilities."""

import sys
from typing import Callable

from rich import print as rprint


def handle_command_error(
    error: Exception, show_usage_fn: Callable[[], None] = None
) -> None:
    """
    Standard error handling for commands.

    Args:
        error: The exception that occurred
        show_usage_fn: Optional function to display usage instructions
    """
    if isinstance(error, ValueError):
        rprint(f"[red]Error:[/red] {str(error)}")
    else:
        rprint(f"[red]Unexpected error:[/red] {str(error)}")

    if show_usage_fn:
        show_usage_fn()

    sys.exit(1)
