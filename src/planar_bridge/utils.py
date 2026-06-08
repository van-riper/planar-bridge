"""Console logging and small string helpers used by the pull pipeline.

These are the remaining utilities pending their branch-7 move: ``status`` and
``boolify_str`` go to the CLI and prompt layer, ``progress_str`` to the
reporters.
"""

from time import strftime

from colorama import Fore


def status(msg: str, lvl: int) -> None:
    """Print a timestamped, color-coded status line for each message line.

    Args:
        msg (str): The message; each line is printed with the same prefix.
        lvl (int): The severity level 0-6 selecting the colored label.

    Raises:
        ValueError: When ``lvl`` is outside the 0-6 range.
    """

    prefix: str

    match lvl:
        case 0:
            prefix = Fore.CYAN + "INFO"
        case 1:
            prefix = Fore.RED + "WARNING"
        case 2:
            prefix = Fore.GREEN + "LOAD SET"
        case 3:
            prefix = Fore.YELLOW + "SKIP SET"
        case 4:
            prefix = Fore.MAGENTA + "NEW CARD"
        case 5:
            prefix = Fore.BLUE + "ENHANCED"
        case 6:
            prefix = Fore.RED + "ERROR"
        case _:
            raise ValueError(lvl)

    prefix += Fore.RESET + ":"
    timestamp: str = "[" + Fore.CYAN + strftime("%H:%M:%S") + Fore.RESET + "]"

    for line in msg.splitlines():
        print(timestamp, prefix, line)


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
