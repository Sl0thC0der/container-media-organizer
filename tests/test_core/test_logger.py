"""Tests for logger module."""

from media_organizer.core.logger import Logger


def test_logger_writes_to_file(tmp_path):
    """Test logger writes messages to file."""
    log_file = tmp_path / "test.log"
    logger = Logger(log_file)
    logger.log("Test message")

    assert log_file.exists()
    content = log_file.read_text()
    assert "Test message" in content


def test_logger_creates_parent_directory(tmp_path):
    """Test logger creates parent directories if needed."""
    log_file = tmp_path / "subdir" / "test.log"
    logger = Logger(log_file)
    logger.log("Test message")

    assert log_file.exists()
    assert log_file.parent.exists()


def test_logger_appends_to_existing_file(tmp_path):
    """Test logger appends to existing log file."""
    log_file = tmp_path / "test.log"
    logger = Logger(log_file)

    logger.log("First message")
    logger.log("Second message")

    content = log_file.read_text()
    assert "First message" in content
    assert "Second message" in content
    assert content.count("\n") == 2
