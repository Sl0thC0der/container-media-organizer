"""Type definitions and data classes."""

from dataclasses import dataclass
from pathlib import Path
from typing import Optional


@dataclass
class ScanResult:
    """Result of filesystem scan operation."""

    file_count: int
    total_bytes: int
    scan_id: int


@dataclass
class ScatteredFolder:
    """Folder containing scattered media files that need organization."""

    path: Path
    name: str
    creator: str


@dataclass
class DeduplicationResult:
    """Result of deduplication operation."""

    removed_count: int
    saved_bytes: int
