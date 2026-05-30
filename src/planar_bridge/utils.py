from time import sleep, strftime

from colorama import Fore
from requests import HTTPError, Response, Session


def status(msg: str, lvl: int) -> None:

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


def handle_response(session: Session, url: str) -> Response | None:

    message: tuple[str, ...]
    response: Response = session.get(url, timeout=30)

    for i in range(1, 5):

        try:
            response.raise_for_status()
            return response

        except HTTPError:
            message = (
                f"HTTP status code {response.status_code},",
                int_to_ordinal(i) + " retry...",
            )
            status((" ").join(message), 1)
            sleep(i * 30)

    message = (
        f"HTTP status code {response.status_code},",
        "too many retries, saving & exiting...",
    )
    status((" ").join(message), 6)

    return None


def progress_str(count: int, total: int, arrow: bool) -> str:

    progress: str = f"({format(count / total, ".1%").zfill(5).rjust(5)})"

    if count == total:
        progress = " (100%)"
    if arrow:
        progress += ">"

    return progress


def boolify_str(bool_str: str, default: bool | None = None) -> bool:

    if not bool_str and default is not None:
        return default

    bool_str = bool_str.strip().lower()[:1]

    if bool_str in ["y", "t", "1"]:
        return True
    if bool_str in ["n", "f", "0"]:
        return False

    raise ValueError(f"Input '{bool_str}' does not resemble a yes/no response.")


def int_to_ordinal(n: int) -> str:

    suffix: str

    if 11 <= (n % 100) <= 13:
        suffix = "th"
    else:
        suffix = ["th", "st", "nd", "rd", "th"][min(n % 10, 4)]

    return str(n) + suffix
