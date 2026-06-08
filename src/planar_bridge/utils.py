"""Small string helper pending its branch-9 move.

``boolify_str`` moves into the CLI when it absorbs the version-mismatch
prompt; what remains here is a temporary home. The progress formatting now
lives in the console reporter, and the colorized ``status`` logger is gone,
replaced by the event layer and the console reporter.
"""


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
