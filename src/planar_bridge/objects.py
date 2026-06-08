"""Per-card and per-set context objects used by the pull pipeline.

These bundle the pure domain facts with the runtime state the pipeline needs:
a card's stored resolution and image path, and a set's directory and progress.
The network work lives in ``sources/`` and the download decision in
``domain.decisions``; these objects hold no I/O beyond reading the catalog.
"""

from datetime import datetime, timezone
from pathlib import Path

from . import utils
from .aliases import CardData, SetData
from .catalog.repository import CardRow, CatalogRepository
from .config.loader import AppConfig
from .domain import layouts
from .domain.card_model import CardFields, build_card_fields
from .domain.set_model import SetRecord, build_set_record
from .events import EventBus
from .paths import DataPaths


class CardObject:  # pylint: disable=too-few-public-methods
    """One card's derived facts, image path, and stored resolution."""

    def __init__(
        self,
        card_dict: CardData,
        repository: CatalogRepository,
        set_directory: Path,
        config: AppConfig,
    ) -> None:
        """Derive a card's facts, paths, and catalog state.

        Args:
            card_dict (CardData): One MTGJSON card entry.
            repository (CatalogRepository): The catalog, queried for the card's
                recorded resolution.
            set_directory (Path): The set's image directory.
            config (AppConfig): Resolved filtering configuration.
        """

        self.card: CardFields = build_card_fields(card_dict, config)

        row: CardRow | None = repository.get_card(self.card.filename)
        self.local_state: bool | None = (
            row.is_high_resolution if row is not None else None
        )

        self.set_code: str = set_directory.name
        data_directory: Path = set_directory.parent

        image_directory: Path = set_directory
        if self.card.layout in layouts.LAYOUT_TOKEN:
            image_directory = set_directory / "tokens"

        self.img_path: Path = image_directory / (self.card.filename + ".jpg")
        self.path_exists: bool = self.img_path.exists()
        self.relative_path: str = self.img_path.relative_to(
            data_directory
        ).as_posix()

    def to_row(self, is_high_resolution: bool) -> CardRow:
        """Build the catalog row recording this card's stored resolution.

        Args:
            is_high_resolution (bool): Whether the stored scan is high-res.

        Returns:
            CardRow: The row to persist for this card.
        """

        return CardRow(
            filename=self.card.filename,
            set_code=self.set_code,
            uuid=self.card.uuid,
            is_high_resolution=is_high_resolution,
            relative_path=self.relative_path,
            updated_at=datetime.now(timezone.utc).isoformat(),
        )


class SetObject:
    """One set's derived facts, image directory, and download progress."""

    def __init__(
        self,
        set_dict: SetData,
        config: AppConfig,
        paths: DataPaths,
        bus: EventBus,
    ) -> None:
        """Derive a set's record, image directory, and progress counter.

        Args:
            set_dict (SetData): One MTGJSON set entry.
            config (AppConfig): Resolved filtering configuration.
            paths (DataPaths): The resolved data paths.
            bus (EventBus): The event bus for progress events.
        """

        self.record: SetRecord = build_set_record(set_dict, config)
        self.set_directory: Path = paths.data_directory / self.record.set_code
        self.progress: tuple[int, int] = (0, len(self.record.card_entries))
        self.bus: EventBus = bus

    def increase_progress(self) -> None:
        """Advance the count of cards handled in this set by one."""

        self.progress = (self.progress[0] + 1, self.progress[1])

    def inner_progress(self) -> str:
        """Return the set's progress as a formatted percentage string."""

        return utils.progress_str(*self.progress, True)
