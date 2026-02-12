"""Complete coverage tests for FolderCleanup edge cases."""
import pytest
from pathlib import Path
from media_organizer.organizer.cleanup import FolderCleanup
from media_organizer.core.logger import Logger


class TestFolderCleanupEdgeCases:
    """Test edge cases for folder cleanup."""

    def test_handles_permission_error_on_rmdir(self, tmp_path, mocker):
        """Test handles PermissionError when removing folder."""
        media_dir = tmp_path / "media"
        media_dir.mkdir()

        # Create empty folder
        empty_folder = media_dir / "empty_folder"
        empty_folder.mkdir()

        # Mock rmdir to raise PermissionError
        original_rmdir = Path.rmdir
        def mock_rmdir(self):
            if self.name == "empty_folder":
                raise PermissionError("Access denied")
            return original_rmdir(self)

        mocker.patch.object(Path, 'rmdir', mock_rmdir)

        logger = Logger(tmp_path / "test.log")
        cleaner = FolderCleanup(logger)

        # Should not crash
        cleaner.remove_empty_folders(media_dir)

        # Folder should still exist (couldn't be removed)
        assert empty_folder.exists()

    def test_handles_os_error_on_rmdir(self, tmp_path, mocker):
        """Test handles OSError when removing folder."""
        media_dir = tmp_path / "media"
        media_dir.mkdir()

        # Create empty folder
        empty_folder = media_dir / "empty_folder"
        empty_folder.mkdir()

        # Mock rmdir to raise OSError
        original_rmdir = Path.rmdir
        def mock_rmdir(self):
            if self.name == "empty_folder":
                raise OSError("Disk error")
            return original_rmdir(self)

        mocker.patch.object(Path, 'rmdir', mock_rmdir)

        logger = Logger(tmp_path / "test.log")
        cleaner = FolderCleanup(logger)

        # Should not crash
        cleaner.remove_empty_folders(media_dir)

        # Folder should still exist (couldn't be removed)
        assert empty_folder.exists()

    def test_logs_when_no_empty_folders_found(self, tmp_path):
        """Test logs message when no empty folders exist."""
        media_dir = tmp_path / "media"
        media_dir.mkdir()

        # Create folder with file (not empty)
        folder = media_dir / "not_empty"
        folder.mkdir()
        (folder / "file.txt").write_text("content")

        logger = Logger(tmp_path / "test.log")
        cleaner = FolderCleanup(logger)

        # Clean folders
        cleaner.remove_empty_folders(media_dir)

        # Check log message
        log_content = logger.log_file.read_text()
        assert "No empty folders found" in log_content

    def test_logs_count_when_folders_removed(self, tmp_path):
        """Test logs count of removed folders."""
        media_dir = tmp_path / "media"
        media_dir.mkdir()

        # Create empty folders
        (media_dir / "empty1").mkdir()
        (media_dir / "empty2").mkdir()
        (media_dir / "empty3").mkdir()

        logger = Logger(tmp_path / "test.log")
        cleaner = FolderCleanup(logger)

        # Clean folders
        cleaner.remove_empty_folders(media_dir)

        # Check log message shows count
        log_content = logger.log_file.read_text()
        assert "Removed 3 empty folders" in log_content
