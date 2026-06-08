"""Interactive CLI prompts and the version-drift approval they build.

The pipeline emits a ``VersionMismatch`` event but does not know how to ask
the user about it; it takes an approval callback instead. This module is where
that callback is built, so the only ``input()`` in the program lives here.
"""

from collections.abc import Callable

from .. import utils


def confirm_version_drift() -> bool:
    """Ask the user whether to proceed past an MTGJSON version drift.

    Returns:
        bool: True to proceed, False to abort. An empty answer defaults to
        False (do not proceed).
    """

    return utils.boolify_str(input("Do you want to proceed? [y/N]: "), False)


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
