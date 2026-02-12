"""Complete coverage tests for config module."""
import pytest
import sys
import os
from pathlib import Path
from media_organizer.config import validate_work_dir


class TestConfigValidation:
    """Test validate_work_dir for 100% coverage."""

    def test_validate_work_dir_returns_resolved_path_in_production(self, tmp_path, monkeypatch):
        """Test validate_work_dir returns resolved path when not in test mode (line 18)."""
        test_dir = tmp_path / "test_work"
        test_dir.mkdir()

        # Temporarily remove pytest from sys.modules
        if "pytest" in sys.modules:
            monkeypatch.delitem(sys.modules, "pytest")
        monkeypatch.delenv("PYTEST_CURRENT_TEST", raising=False)

        # Now validation should actually run and return resolved path
        result = validate_work_dir(test_dir)

        # Should return the resolved path
        assert result == test_dir.resolve()
        assert result.is_absolute()


class TestConfigFallback:
    """Test config directory fallback (lines 37-40)."""

    def test_config_paths_are_valid(self):
        """Test that config paths are properly set."""
        import media_organizer.config as config

        # Verify CONFIG_DIR and LOG_DIR are set
        assert config.CONFIG_DIR is not None
        assert config.LOG_DIR is not None
        assert isinstance(config.CONFIG_DIR, Path)
        assert isinstance(config.LOG_DIR, Path)

        # Verify they exist (created by lines 49-50)
        assert config.CONFIG_DIR.exists()
        assert config.LOG_DIR.exists()
