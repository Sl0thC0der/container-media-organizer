"""Tests for folder cleanup."""

from pathlib import Path
from media_organizer.organizer.cleanup import FolderCleanup
from media_organizer.core.logger import Logger


def test_remove_empty_folders(tmp_path):
    """Test removal of empty folders."""
    logger = Logger(tmp_path / "test.log")
    cleanup = FolderCleanup(logger)

    # Create test structure with empty folders
    (tmp_path / "empty1").mkdir()
    (tmp_path / "not_empty").mkdir()
    (tmp_path / "not_empty" / "file.txt").write_text("test")
    (tmp_path / "empty2").mkdir()

    removed = cleanup.remove_empty_folders(tmp_path)

    # Should remove 2 empty folders
    assert removed == 2
    assert not (tmp_path / "empty1").exists()
    assert not (tmp_path / "empty2").exists()
    assert (tmp_path / "not_empty").exists()
