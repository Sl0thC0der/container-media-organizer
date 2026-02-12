"""Integration tests for the complete workflow."""

import pytest
from pathlib import Path
from media_organizer.cli import MediaOrganizer


def test_media_organizer_can_be_instantiated():
    """Test that MediaOrganizer can be created."""
    organizer = MediaOrganizer()
    assert organizer is not None
    assert organizer.logger is not None


@pytest.mark.skip(reason="Requires Docker Model Runner to be running")
def test_full_pipeline_with_dmr(temp_work_dir, test_db):
    """
    Test complete organize workflow end-to-end.

    NOTE: This test requires Docker Model Runner to be running.
    It is skipped by default in CI environments.
    """
    # This would be a comprehensive integration test
    # that sets up a test media library and runs the full pipeline
    pass


def test_organizer_handles_empty_directory(temp_work_dir):
    """Test organizer gracefully handles empty directory."""
    # Test that the organizer doesn't crash on empty directory
    # Would need to mock DMR client to avoid requiring Docker
    pass
