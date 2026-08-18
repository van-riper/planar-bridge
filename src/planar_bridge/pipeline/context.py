"""The pipeline's context objects: run-wide, per-set, and per-card state.

``PullContext`` bundles the run-wide dependencies. ``CardObject`` and
``SetObject`` hold the per-card and per-set runtime state (catalog lookups,
image paths, and progress) derived from the pure domain models. The network
work lives in ``sources/`` and the download decision in ``domain.decisions``;
these objects hold no I/O beyond reading the catalog.
"""

from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

from ..aliases import CardData, SetData
from ..catalog.repository import CardRow, CatalogRepository
from ..config.loader import AppConfig
from ..domain import layouts
from ..domain.card_model import CardFields, build_card_fields
from ..domain.set_model import SetRecord, build_set_record
from ..events import EventBus
from ..options import RunOptions
from ..paths import DataPaths
from ..sources.ports import ImageSource


@dataclass(frozen=True)
class PullContext:
    """The run-wide dependencies threaded through the set and card loops.

    Attributes:
        repository: The catalog of stored card state.
        scryfall_source: The card-image source.
        config: Resolved filtering configuration.
        bus: The event bus for set and card events.
        options: The per-run command-line switches.
    """

    repository: CatalogRepository
    scryfall_source: ImageSource
    config: AppConfig
    bus: EventBus
    options: RunOptions


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
            card_dict: One MTGJSON card entry.
            repository: The catalog, queried for the card's recorded
                resolution.
            set_directory: The set's image directory.
            config: Resolved filtering configuration.
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
            is_high_resolution: Whether the stored scan is high-res.

        Returns:
            The row to persist for this card.
        """
        return CardRow(
            filename=self.card.filename,
            set_code=self.set_code,
            uuid=self.card.uuid,
            is_high_resolution=is_high_resolution,
            relative_path=self.relative_path,
            updated_at=datetime.now(UTC).isoformat(),
        )


class SetObject:  # pylint: disable=too-few-public-methods
    """One set's derived facts, image directory, and download progress."""

    def __init__(
        self,
        set_dict: SetData,
        config: AppConfig,
        paths: DataPaths,
    ) -> None:
        """Derive a set's record, image directory, and progress counter.

        Args:
            set_dict: One MTGJSON set entry.
            config: Resolved filtering configuration.
            paths: The resolved data paths.
        """
        self.record: SetRecord = build_set_record(set_dict, config)
        self.set_directory: Path = paths.data_directory / self.record.set_code
        self.progress: tuple[int, int] = (0, len(self.record.card_entries))

    def increase_progress(self) -> None:
        """Advance the count of cards handled in this set by one."""
        self.progress = (self.progress[0] + 1, self.progress[1])
