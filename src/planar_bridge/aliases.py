"""Shared type aliases for MTGJSON data shapes and domain value types."""

from typing import Any, Literal

type CardData = dict[str, Any]
type SetData = dict[str, Any]
type SetEntries = dict[str, SetData]
type Face = Literal["front", "back"]
type ImageStatus = Literal[
    "missing",
    "placeholder",
    "lowres",
    "highres_scan",
]
