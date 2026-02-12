"""Filesystem scanning and indexing."""

from pathlib import Path
from ..core.database import DatabaseManager
from ..core.logger import Logger


class FilesystemScanner:
    """Scans filesystem and indexes files into database."""

    def __init__(self, db_manager: DatabaseManager, logger: Logger) -> None:
        """Initialize filesystem scanner."""
        self.db_manager = db_manager
        self.logger = logger

    def scan(self, work_dir: Path, scan_id: int) -> int:
        """
        Scan filesystem and index files.

        Args:
            work_dir: Root directory to scan
            scan_id: Scan session ID

        Returns:
            Number of files indexed
        """
        return self.db_manager.scan_filesystem(work_dir, scan_id)
