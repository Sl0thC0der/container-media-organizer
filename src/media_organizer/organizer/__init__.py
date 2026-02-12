"""File organization: merging, deduplication, cleanup."""

from .merger import FileMerger
from .deduplicator import FileDeduplicator
from .cleanup import FolderCleanup

__all__ = ["FileMerger", "FileDeduplicator", "FolderCleanup"]
