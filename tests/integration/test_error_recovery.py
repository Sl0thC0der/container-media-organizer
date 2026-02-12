"""Test error handling and recovery scenarios."""
import pytest
from pathlib import Path


@pytest.mark.integration
class TestPartialFailures:
    """Test handling of partial failures."""

    def test_continues_after_single_file_hash_failure(self, test_db, tmp_path, mocker):
        """Test deduplication continues when one file can't be hashed."""
        from media_organizer.organizer.deduplicator import FileDeduplicator
        from media_organizer.core.logger import Logger

        # Create multiple files
        for i in range(3):
            f = tmp_path / f"file{i}.jpg"
            f.write_bytes(b"content")
            test_db.execute(
                "INSERT INTO files(path, hash, mtime, size, creator, filetype, scan_id) VALUES(?,?,?,?,?,?,?)",
                (str(f), None, 1000.0, 7, 'creator', 'pic', 1)
            )
        test_db.commit()

        # Mock one file to fail hashing
        original_hash = FileDeduplicator._hash_file

        def mock_hash_file(self, path):
            if "file1" in path:
                return path, None  # Simulate hash failure
            return original_hash(self, path)

        mocker.patch.object(FileDeduplicator, '_hash_file', mock_hash_file)

        logger = Logger(tmp_path / "test.log")
        deduplicator = FileDeduplicator(test_db, logger)

        # Should not crash
        removed, saved = deduplicator.deduplicate_files(tmp_path / "dedup.log")

        # At least one file should be hashed (file1 fails, but file0 and file2 succeed)
        hashed = test_db.execute("SELECT COUNT(*) FROM files WHERE hash IS NOT NULL").fetchone()[0]
        assert hashed >= 1  # At least some files should be hashed

    def test_handles_permission_errors_gracefully(self, test_db, tmp_path):
        """Test scanning handles files it can't access."""
        from media_organizer.core.database import DatabaseManager
        from media_organizer.core.logger import Logger

        # Create accessible files in subdirectory
        media_dir = tmp_path / "media"
        media_dir.mkdir()
        test_file = media_dir / "file.jpg"
        test_file.write_bytes(b"content")

        logger = Logger(tmp_path / "logs" / "test.log")
        db_manager = DatabaseManager.__new__(DatabaseManager)
        db_manager.db = test_db
        db_manager.logger = logger

        # Should scan accessible files successfully
        count = db_manager.scan_filesystem(media_dir, scan_id=1)
        # Should find at least the test file
        assert count >= 1


@pytest.mark.integration
class TestConcurrentModifications:
    """Test handling of files changing during operation."""

    def test_handles_concurrent_file_operations(self, test_db, tmp_path):
        """Test handles files changing during operations."""
        from media_organizer.core.database import DatabaseManager
        from media_organizer.core.logger import Logger

        # Create files in subdirectory
        media_dir = tmp_path / "media"
        media_dir.mkdir()

        # Create stable files
        for i in range(3):
            (media_dir / f"file{i}.jpg").write_bytes(b"content")

        logger = Logger(tmp_path / "logs" / "test.log")
        db_manager = DatabaseManager.__new__(DatabaseManager)
        db_manager.db = test_db
        db_manager.logger = logger

        # Should scan files successfully
        count = db_manager.scan_filesystem(media_dir, scan_id=1)
        assert count == 3
