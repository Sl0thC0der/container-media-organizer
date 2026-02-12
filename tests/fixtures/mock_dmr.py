"""Mock Docker Model Runner responses for testing."""
import json


class MockDMRResponse:
    """Mock DMR API response builder."""

    @staticmethod
    def success(content: str, status_code: int = 200):
        """Create successful DMR response."""
        class Response:
            def __init__(self):
                self.status_code = status_code

            def json(self):
                return {
                    'choices': [{
                        'message': {
                            'content': content
                        }
                    }]
                }
        return Response()

    @staticmethod
    def models_list(models: list):
        """Create models list response."""
        class Response:
            def __init__(self):
                self.status_code = 200

            def json(self):
                return {
                    'data': [{'id': model} for model in models]
                }
        return Response()

    @staticmethod
    def error(status_code: int, message: str = "Error"):
        """Create error response."""
        class Response:
            def __init__(self):
                self.status_code = status_code
                self.text = message
        return Response()

    @staticmethod
    def timeout():
        """Raise timeout exception."""
        import requests
        raise requests.exceptions.Timeout("Connection timeout")

    @staticmethod
    def connection_error():
        """Raise connection exception."""
        import requests
        raise requests.exceptions.ConnectionError("Cannot connect")


def mock_creator_identification_response(mappings: dict) -> str:
    """Generate mock AI response for creator identification."""
    return f"Here's the JSON:\n{json.dumps(mappings)}\nThat's my analysis."


def mock_malformed_json_response() -> str:
    """Generate AI response with incomplete/malformed JSON."""
    return '{"folder1": "creator1", "folder2":'  # Incomplete JSON
