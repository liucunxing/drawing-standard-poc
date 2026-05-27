"""Base interface for table recognition engines."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Protocol


@dataclass
class RecognitionResult:
    status: str
    raw_output: str = ""
    html: str = ""
    markdown: str = ""
    csv_text: str = ""
    json_data: dict[str, Any] = field(default_factory=dict)
    error_message: str = ""
    engine_message: str = ""


class TableRecognitionEngine(Protocol):
    name: str

    def recognize(self, image_path: Path, candidate_metadata: dict[str, Any]) -> RecognitionResult:
        """Recognize a table-like crop image."""
