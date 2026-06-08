"""Small string helpers pending their branch-7/9 move.

``progress_str`` moves to the reporters and ``boolify_str`` into the CLI; what
remains here is a temporary home. The colorized ``status`` logger is gone,
replaced by the event layer and the console reporter.
"""


def progress_str(count: int, total: int, arrow: bool) -> str:
    """Format a count over a total as a padded percentage string.

    Args:
        count (int): The number done so far.
        total (int): The total to reach.
        arrow (bool): When True, append a ``>`` arrow to the string.

    Returns:
        str: The formatted progress label, such as ``(45%)>``.
    """

    progress: str = f"({format(count / total, ".1%").zfill(5).rjust(5)})"

    if count == total:
        progress = " (100%)"
    if arrow:
        progress += ">"

    return progress


def boolify_str(bool_str: str, default: bool | None = None) -> bool:
    """Interpret a yes/no string as a boolean.

    Args:
        bool_str (str): The user input to interpret.
        default (bool | None): Returned when the input is empty.

    Returns:
        bool: True for y/t/1, False for n/f/0.

    Raises:
        ValueError: When the input resembles neither yes nor no.
    """

    if not bool_str and default is not None:
        return default

    bool_str = bool_str.strip().lower()[:1]

    if bool_str in ["y", "t", "1"]:
        return True
    if bool_str in ["n", "f", "0"]:
        return False

    raise ValueError(f"Input '{bool_str}' does not resemble a yes/no response.")
