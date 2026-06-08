"""Console reporter: renders engine events as colorized status lines.

This reproduces the historical ``utils.status`` output (the old integer
levels 0 to 6) exactly, now driven by typed events instead of
``(message, level)`` calls. It is the only place that knows about color and
the timestamp: the engine emits plain facts and this reporter decides how
they look. Events with no legacy output (RunStarted, SetSkipped, CardSkipped,
CardFailed) are received and ignored, so the console output is unchanged.
"""

from time import strftime

from colorama import Fore

from .. import constants
from ..events import (
    BulkDataLoaded,
    BulkDownloadStarted,
    CardDownloaded,
    CardEvent,
    CardUpgraded,
    Event,
    Interrupted,
    MetadataChecked,
    MetadataCheckStarted,
    RunFinished,
    SetStarted,
    VersionMismatch,
)

# Each category is the (color, label) pair from the old status() levels.
_INFO = (Fore.CYAN, "INFO")
_WARNING = (Fore.RED, "WARNING")
_LOAD_SET = (Fore.GREEN, "LOAD SET")
_NEW_CARD = (Fore.MAGENTA, "NEW CARD")
_ENHANCED = (Fore.BLUE, "ENHANCED")
_ERROR = (Fore.RED, "ERROR")


class ConsoleReporter:  # pylint: disable=too-few-public-methods
    """Subscribes to the event bus and prints the legacy colorized lines."""

    def handle(self, event: Event) -> None:
        """Render one event to stdout, or ignore it if it has no output.

        Args:
            event (Event): The event to render.
        """

        if isinstance(event, MetadataCheckStarted):
            self.__render(_INFO, "Comparing local & source files...")
        elif isinstance(event, MetadataChecked):
            if not event.is_outdated:
                self.__render(_INFO, "Local data is up to date.")
        elif isinstance(event, VersionMismatch):
            self.__render(_WARNING, self.__version_message(event))
        elif isinstance(event, BulkDownloadStarted):
            self.__render(_INFO, "Downloading bulk files...")
        elif isinstance(event, BulkDataLoaded):
            self.__render(_INFO, f"Loading bulk data ({event.date})...")
        elif isinstance(event, SetStarted):
            self.__render(_LOAD_SET, self.__set_message(event))
        elif isinstance(event, CardDownloaded):
            self.__render(_NEW_CARD, self.__card_message(event))
        elif isinstance(event, CardUpgraded):
            self.__render(_ENHANCED, self.__card_message(event))
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

        return (
            f"{event.progress} {event.set_code.ljust(6)} "
            f"AllHighRes: {event.is_all_high_resolution}"
        )

    def __card_message(self, event: CardEvent) -> str:

        return (
            f"{event.run_progress} {event.set_code.ljust(6)} "
            f"{event.set_progress} {event.display_label}"
        )

    def __remaining_message(self, event: RunFinished) -> str:

        return "Remaining sets with low res scans: " + (", ").join(
            event.low_resolution_set_codes
        )

    def __render(self, category: tuple[str, str], message: str) -> None:

        color, label = category
        prefix = color + label + Fore.RESET + ":"
        timestamp = "[" + Fore.CYAN + strftime("%H:%M:%S") + Fore.RESET + "]"

        for line in message.splitlines():
            print(timestamp, prefix, line)
