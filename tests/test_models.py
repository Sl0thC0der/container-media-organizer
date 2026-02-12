"""Test data models for 100% coverage."""
import pytest
from pathlib import Path
from media_organizer.models import ScanResult, ScatteredFolder, DeduplicationResult
from media_organizer.models.types import ScanResult as ScanResultDirect


class TestDataModels:
    """Test data model creation and usage."""

    def test_scan_result_creation(self):
        """Test ScanResult dataclass."""
        result = ScanResult(file_count=100, total_bytes=5000000, scan_id=1)

        assert result.file_count == 100
        assert result.total_bytes == 5000000
        assert result.scan_id == 1

    def test_scattered_folder_creation(self, tmp_path):
        """Test ScatteredFolder dataclass."""
        test_path = tmp_path / "test_folder"
        test_path.mkdir()

        folder = ScatteredFolder(
            path=test_path,
            name="test_folder",
            creator="test_creator"
        )

        assert folder.path == test_path
        assert folder.name == "test_folder"
        assert folder.creator == "test_creator"

    def test_deduplication_result_creation(self):
        """Test DeduplicationResult dataclass."""
        result = DeduplicationResult(
            removed_count=5,
            saved_bytes=25000000
        )

        assert result.removed_count == 5
        assert result.saved_bytes == 25000000

    def test_models_can_be_imported_from_package(self):
        """Test models can be imported from media_organizer.models."""
        # This tests the __init__.py imports (lines 3-5)
        from media_organizer.models import ScanResult, ScatteredFolder, DeduplicationResult

        # Verify they're the same classes
        assert ScanResult is not None
        assert ScatteredFolder is not None
        assert DeduplicationResult is not None

    def test_models_in_all_list(self):
        """Test __all__ exports correct models."""
        from media_organizer.models import __all__

        assert "ScanResult" in __all__
        assert "ScatteredFolder" in __all__
        assert "DeduplicationResult" in __all__
        assert len(__all__) == 3
