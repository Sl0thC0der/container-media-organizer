"""Tests for filesystem scanner."""

import pytest
from pathlib import Path
from media_organizer.scanner.filesystem import FilesystemScanner
from media_organizer.core.database import DatabaseManager
from media_organizer.core.logger import Logger


def test_scanner_creation(test_db, tmp_path):
    """Test scanner can be created."""
    logger = Logger(tmp_path / "test.log")
    db_manager = DatabaseManager.__new__(DatabaseManager)
    db_manager.logger = logger
    db_manager.db = test_db

    scanner = FilesystemScanner(db_manager, logger)
    assert scanner is not None
    assert scanner.db_manager == db_manager
    assert scanner.logger == logger
