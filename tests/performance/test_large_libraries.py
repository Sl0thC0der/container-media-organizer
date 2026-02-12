"""Performance tests for large media libraries."""
import pytest
import time
from tests.fixtures.filesystem_fixtures import create_large_media_library


@pytest.mark.performance
class TestLargeLibraries:
    """Test performance with large file counts."""

    def test_scans_large_library_efficiently(self, tmp_path, test_db):
        """Test scanning 1000 files completes in reasonable time."""
        from media_organizer.core.database import DatabaseManager
        from media_organizer.core.logger import Logger

        # Create test library in subdirectory to avoid log file
        media_dir = tmp_path / "media"
        media_dir.mkdir()
        create_large_media_library(media_dir, creators=10, files_per_creator=100)

        logger = Logger(tmp_path / "test.log")
        db_manager = DatabaseManager.__new__(DatabaseManager)
        db_manager.db = test_db
        db_manager.logger = logger

        start_time = time.time()
        count = db_manager.scan_filesystem(media_dir, scan_id=1)
        duration = time.time() - start_time

        assert count == 1000
        # Should complete in under 30 seconds
        assert duration < 30, f"Scan took {duration:.2f}s, expected <30s"

    def test_parallel_hashing_performance(self, tmp_path, test_db):
        """Test parallel hashing is efficient."""
        from media_organizer.organizer.deduplicator import FileDeduplicator
        from media_organizer.core.logger import Logger

        # Create test files
        for i in range(100):
            f = tmp_path / f"file{i}.jpg"
            f.write_bytes(b"x" * 10000)  # 10KB each
            test_db.execute(
                "INSERT INTO files(path, hash, mtime, size, creator, filetype, scan_id) VALUES(?,?,?,?,?,?,?)",
                (str(f), None, 1000.0, 10000, 'creator', 'pic', 1)
            )
        test_db.commit()

        logger = Logger(tmp_path / "test.log")
        deduplicator = FileDeduplicator(test_db, logger)

        start_time = time.time()
        removed, saved = deduplicator.deduplicate_files(tmp_path / "dedup.log")
        duration = time.time() - start_time

        # Should complete in under 10 seconds
        assert duration < 10, f"Hashing took {duration:.2f}s, expected <10s"

        # All files should be hashed
        unhashed = test_db.execute("SELECT COUNT(*) FROM files WHERE hash IS NULL").fetchone()[0]
        assert unhashed == 0

    @pytest.mark.slow
    def test_very_large_library(self, tmp_path, test_db):
        """Test with 5000+ files (marked slow, skip in CI)."""
        from media_organizer.core.database import DatabaseManager
        from media_organizer.core.logger import Logger

        # Create test library in subdirectory to avoid log file
        media_dir = tmp_path / "media"
        media_dir.mkdir()
        create_large_media_library(media_dir, creators=50, files_per_creator=100)

        logger = Logger(tmp_path / "test.log")
        db_manager = DatabaseManager.__new__(DatabaseManager)
        db_manager.db = test_db
        db_manager.logger = logger

        start_time = time.time()
        count = db_manager.scan_filesystem(media_dir, scan_id=1)
        duration = time.time() - start_time

        assert count == 5000
        # Should complete in under 2 minutes
        assert duration < 120


@pytest.mark.performance
class TestBatchProcessing:
    """Test batch processing efficiency."""

    def test_batch_upsert_performance(self, tmp_path, test_db):
        """Test batch UPSERT is efficient."""
        from media_organizer.core.database import DatabaseManager
        from media_organizer.core.logger import Logger

        # Create many small files in subdirectory to avoid log file
        media_dir = tmp_path / "media"
        media_dir.mkdir()
        for i in range(1000):
            (media_dir / f"file{i}.jpg").write_bytes(b"x")

        logger = Logger(tmp_path / "test.log")
        db_manager = DatabaseManager.__new__(DatabaseManager)
        db_manager.db = test_db
        db_manager.logger = logger

        start_time = time.time()
        count = db_manager.scan_filesystem(media_dir, scan_id=1)
        duration = time.time() - start_time

        assert count == 1000
        # Batching should make this fast
        assert duration < 10
