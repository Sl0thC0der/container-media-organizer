"""Complete coverage tests for DMRClient edge cases."""
import pytest
import requests
from media_organizer.ai.dmr_client import DMRClient
from media_organizer.core.logger import Logger
from tests.fixtures.mock_dmr import MockDMRResponse


class TestDMRClientRequestExceptions:
    """Test handling of various request exceptions."""

    def test_handles_general_request_exception(self, tmp_path, mocker):
        """Test handles generic RequestException."""
        logger = Logger(tmp_path / "test.log")
        client = DMRClient(logger)

        # Mock to raise general RequestException
        mocker.patch('requests.post', side_effect=[
            requests.exceptions.RequestException("Network error"),
            requests.exceptions.RequestException("Network error"),
            MockDMRResponse.success("Success on 3rd try")
        ])

        result = client.call_api("test prompt", max_retries=3)

        # Should retry and eventually succeed
        assert result == "Success on 3rd try"

        # Check error was logged
        log_content = logger.log_file.read_text()
        assert "request failed" in log_content.lower()

    def test_exhausts_retries_on_request_exception(self, tmp_path, mocker):
        """Test exhausts all retries on persistent RequestException."""
        logger = Logger(tmp_path / "test.log")
        client = DMRClient(logger)

        # Mock to always fail
        mocker.patch('requests.post', side_effect=requests.exceptions.RequestException("Network error"))

        result = client.call_api("test prompt", max_retries=2)

        # Should return None after exhausting retries
        assert result is None

        # Check failure was logged
        log_content = logger.log_file.read_text()
        assert "failed after" in log_content.lower()

    def test_handles_connection_error_variant(self, tmp_path, mocker):
        """Test handles ConnectionError (subclass of RequestException)."""
        logger = Logger(tmp_path / "test.log")
        client = DMRClient(logger)

        # Mock to raise ConnectionError
        mocker.patch('requests.post', side_effect=[
            requests.exceptions.ConnectionError("Cannot connect"),
            MockDMRResponse.success("Success after reconnect")
        ])

        result = client.call_api("test prompt", max_retries=2)

        # Should retry and succeed
        assert result == "Success after reconnect"

    def test_handles_http_error_variant(self, tmp_path, mocker):
        """Test handles HTTPError (subclass of RequestException)."""
        logger = Logger(tmp_path / "test.log")
        client = DMRClient(logger)

        # Mock to raise HTTPError
        mocker.patch('requests.post', side_effect=[
            requests.exceptions.HTTPError("Bad Gateway"),
            MockDMRResponse.success("Success after retry")
        ])

        result = client.call_api("test prompt", max_retries=2)

        # Should retry and succeed
        assert result == "Success after retry"
