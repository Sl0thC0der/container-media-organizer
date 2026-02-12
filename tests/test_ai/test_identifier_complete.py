"""Complete coverage tests for CreatorIdentifier."""
import pytest
import json
from pathlib import Path
from media_organizer.ai.identifier import CreatorIdentifier
from media_organizer.core.logger import Logger


class TestIdentifierJSONParsing:
    """Test JSON parsing edge cases to achieve 100% coverage."""

    def test_handles_json_decode_error_with_debug_log(self, test_db, tmp_path, mocker):
        """Test logs debug info when JSON parsing fails (lines 88-91)."""
        logger = Logger(tmp_path / "test.log")

        # Mock DMR to return invalid JSON that will cause JSONDecodeError
        dmr_client = mocker.Mock()
        dmr_client.call_api.return_value = '{"invalid": json, "syntax": error}'

        identifier = CreatorIdentifier(test_db, dmr_client, logger)

        # Create a test folder
        test_folder = tmp_path / "Test Folder"
        test_folder.mkdir()

        # Call identify_creators - should catch JSONDecodeError
        result = identifier.identify_creators([test_folder], {})

        # Should return empty dict
        assert result == {}

        # Verify error and debug were logged
        log_content = logger.log_file.read_text()
        assert "Failed to parse AI response" in log_content
        assert "DEBUG" in log_content
        assert "Response was:" in log_content

    def test_handles_response_with_no_json_object(self, test_db, tmp_path, mocker):
        """Test handles response that has no JSON object at all (line 86)."""
        logger = Logger(tmp_path / "test.log")

        # Mock DMR to return text with no JSON
        dmr_client = mocker.Mock()
        dmr_client.call_api.return_value = 'This is just plain text without any JSON braces or brackets'

        identifier = CreatorIdentifier(test_db, dmr_client, logger)

        # Create a test folder
        test_folder = tmp_path / "Test Folder"
        test_folder.mkdir()

        # Call identify_creators
        result = identifier.identify_creators([test_folder], {})

        # Should return empty dict
        assert result == {}

        # Verify error was logged about no JSON found
        log_content = logger.log_file.read_text()
        assert "No JSON found in response" in log_content
