"""Tests for configuration module."""

import pytest
import sys
from pathlib import Path
from media_organizer.config import validate_work_dir


def test_validate_work_dir_success(temp_work_dir):
    """Test validation of valid work directory."""
    result = validate_work_dir(temp_work_dir)
    assert result == temp_work_dir.resolve()


def test_validate_work_dir_invalid(monkeypatch):
    """Test validation fails for non-existent directory."""
    # Temporarily remove pytest from sys.modules to test validation
    if "pytest" in sys.modules:
        monkeypatch.delitem(sys.modules, "pytest")
    monkeypatch.delenv("PYTEST_CURRENT_TEST", raising=False)

    with pytest.raises(SystemExit):
        validate_work_dir(Path("/nonexistent/directory/path"))


def test_validate_work_dir_not_a_directory(tmp_path, monkeypatch):
    """Test validation fails for file instead of directory."""
    # Temporarily remove pytest from sys.modules to test validation
    if "pytest" in sys.modules:
        monkeypatch.delitem(sys.modules, "pytest")
    monkeypatch.delenv("PYTEST_CURRENT_TEST", raising=False)

    file_path = tmp_path / "test.txt"
    file_path.write_text("test")

    with pytest.raises(SystemExit):
        validate_work_dir(file_path)
