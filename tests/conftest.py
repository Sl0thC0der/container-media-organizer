"""Pytest fixtures for testing."""
import tempfile
from pathlib import Path
import sqlite3
import pytest


@pytest.fixture
def temp_work_dir():
    """Create temporary work directory."""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield Path(tmpdir)


@pytest.fixture
def test_db():
    """Create temporary test database with schema."""
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        db_path = Path(f.name)

    db = sqlite3.connect(str(db_path))
    db.execute("PRAGMA journal_mode=WAL")

    # Create schema
    db.executescript("""
        CREATE TABLE files (
            path TEXT PRIMARY KEY,
            hash TEXT,
            mtime REAL NOT NULL,
            size INTEGER NOT NULL,
            creator TEXT,
            filetype TEXT,
            scan_id INTEGER NOT NULL
        );
        CREATE INDEX idx_files_hash ON files(hash);
        CREATE INDEX idx_files_creator ON files(creator);

        CREATE TABLE creator_mappings (
            folder_name TEXT PRIMARY KEY,
            creator_name TEXT
        );

        CREATE TABLE scan_meta (
            scan_id INTEGER PRIMARY KEY AUTOINCREMENT,
            started_at TEXT NOT NULL,
            finished_at TEXT,
            file_count INTEGER,
            total_bytes INTEGER
        );
    """)
    db.commit()

    yield db

    db.close()
    db_path.unlink()


# Import all fixture modules
pytest_plugins = [
    "tests.fixtures.database_fixtures",
    "tests.fixtures.filesystem_fixtures",
]


@pytest.fixture
def mock_dmr_client(mocker):
    """Mock DMRClient with successful responses by default."""
    client = mocker.Mock()
    client.check_connection.return_value = True
    client.call_api.return_value = '{"test": "response"}'
    return client


@pytest.fixture
def capture_logger_output(tmp_path):
    """Capture logger output for assertions."""
    from media_organizer.core.logger import Logger
    log_file = tmp_path / "test.log"
    logger = Logger(log_file)

    def get_logs():
        return log_file.read_text() if log_file.exists() else ""

    logger.get_logs = get_logs
    return logger
