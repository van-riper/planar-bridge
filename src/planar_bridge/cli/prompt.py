"""Interactive CLI prompts and the version-drift approval they build.

The pipeline emits a ``VersionMismatch`` event but does not know how to ask
the user about it; it takes an approval callback instead. This module is where
that callback is built, so the only ``input()`` in the program lives here.
"""

from collections.abc import Callable


def _ask_yes_no(question: str) -> bool:
    """Prompt for a yes/no answer, re-prompting until it is y or n.

    Args:
        question (str): The question to show; a ``[y/n]`` hint is appended.

    Returns:
        bool: True for y, False for n. A closed input stream (EOF) declines.
    """

    while True:
        try:
            answer = input(f"{question} [y/n]: ").strip().lower()
        except EOFError:
            return False

        if answer == "y":
            return True
        if answer == "n":
            return False


def confirm_version_drift() -> bool:
    """Ask the user whether to proceed past an MTGJSON version drift.

    Returns:
        bool: True to proceed, False to abort.
    """

    return _ask_yes_no("Do you want to proceed?")


def approval_for(*, assume_yes: bool) -> Callable[[], bool]:
    """Choose the version-drift approval for a run.

    Args:
        assume_yes (bool): True when ``--assume-yes`` was given.

    Returns:
        Callable[[], bool]: An auto-approval that proceeds without prompting
        under ``--assume-yes``, otherwise the interactive prompt.
    """

    if assume_yes:
        return lambda: True

    return confirm_version_drift
