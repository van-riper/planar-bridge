"""Console reporter: renders engine events as colorized status lines.

This reproduces the output of the old ``status()`` logger (the integer
levels 0 to 6) exactly, now driven by typed events instead of
``(message, level)`` calls. It is the only place that knows about color and
the timestamp: the engine emits plain facts and this reporter decides how
they look. Events with no console output (RunStarted, CardSkipped) are
received and ignored.
"""

from time import strftime

from colorama import Fore

from .. import constants
from ..events import (
    BulkDataLoaded,
    BulkDownloadStarted,
    CardDownloaded,
    CardEvent,
    CardFailed,
    CardUpgraded,
    Event,
    Interrupted,
    MetadataCheckStarted,
    RunFinished,
    SetSkipped,
    SetStarted,
    VersionMismatch,
)

# Each category is the (color, label) pair from the old status() levels.
_INFO = (str(Fore.CYAN), "INFO")
_WARNING = (str(Fore.RED), "WARNING")
_LOAD_SET = (str(Fore.GREEN), "LOAD SET")
_SKIP_SET = (str(Fore.YELLOW), "SKIP SET")
_NEW_CARD = (str(Fore.MAGENTA), "NEW CARD")
_ENHANCED = (str(Fore.BLUE), "ENHANCED")
_ERROR = (str(Fore.RED), "ERROR")


class ConsoleReporter:  # pylint: disable=too-few-public-methods
    """Subscribes to the event bus and prints the legacy colorized lines."""

    def handle(self, event: Event) -> None:  # pylint: disable=too-many-branches
        """Render one event to stdout, or ignore it if it has no output.

        Args:
            event (Event): The event to render.
        """
        if isinstance(event, MetadataCheckStarted):
            self.__render(_INFO, "Comparing local & source files...")
        elif isinstance(event, VersionMismatch):
            self.__render(_WARNING, self.__version_message(event))
        elif isinstance(event, BulkDownloadStarted):
            self.__render(_INFO, "Downloading bulk files...")
        elif isinstance(event, BulkDataLoaded):
            self.__render(_INFO, f"Loading bulk data ({event.date})...")
        elif isinstance(event, SetStarted):
            self.__render(_LOAD_SET, self.__set_message(event))
        elif isinstance(event, SetSkipped):
            self.__render(_SKIP_SET, event.set_code)
        elif isinstance(event, CardDownloaded):
            self.__render(_NEW_CARD, self.__card_message(event))
        elif isinstance(event, CardUpgraded):
            self.__render(_ENHANCED, self.__card_message(event))
        elif isinstance(event, CardFailed):
            message = f"Failed to download a card in {event.set_code}"
            self.__render(_ERROR, message)
        elif isinstance(event, RunFinished):
            self.__render(_INFO, "Finished successfully.")
            self.__render(_INFO, self.__remaining_message(event))
        elif isinstance(event, Interrupted):
            message = "Interrupted (Ctrl-C), exiting. Progress is saved."
            self.__render(_ERROR, message)

    def __version_message(self, event: VersionMismatch) -> str:

        return (
            "MTGJSON has been updated to v"
            + event.source_version
            + "\n"
            + constants.VERS_WARNING
        )

    def __set_message(self, event: SetStarted) -> str:

        run = self.__progress(event.run_count, event.run_total, False)

        return (
            f"{run} {event.set_code.ljust(6)} "
            f"AllHighRes: {event.is_all_high_resolution}"
        )

    def __card_message(self, event: CardEvent) -> str:

        run = self.__progress(event.run_count, event.run_total, False)
        within = self.__progress(event.set_count, event.set_total, True)

        return (
            f"{run} {event.set_code.ljust(6)} "
            f"{within} {event.display_label}"
        )

    def __progress(self, count: int, total: int, arrow: bool) -> str:
        """Format a count over a total as a padded percentage label.

        Args:
            count (int): The number done so far.
            total (int): The total to reach.
            arrow (bool): When True, append a ``>`` arrow (set-level lines).

        Returns:
            str: The formatted label, such as ``(45.0%)`` or ``(45.0%)>``.
        """
        label = f"({format(count / total, '.1%').zfill(5).rjust(5)})"

        if count == total:
            label = " (100%)"
        if arrow:
            label += ">"

        return label

    def __remaining_message(self, event: RunFinished) -> str:

        return "Remaining sets with low res scans: " + (", ").join(
            event.low_resolution_set_codes
        )

    def __render(self, category: tuple[str, str], message: str) -> None:

        color, label = category
        prefix = f"{color}{label}{Fore.RESET}:"
        timestamp = f"[{Fore.CYAN}{strftime('%H:%M:%S')}{Fore.RESET}]"

        for line in message.splitlines():
            print(timestamp, prefix, line)
