"""Tests for utility functions."""

import json

from mcphawk.utils import get_message_type, get_method_name, parse_message


class TestParseMessage:
    """Test parse_message function."""

    def test_parse_valid_json_string(self):
        """Test parsing valid JSON string."""
        message = '{"jsonrpc": "2.0", "method": "test"}'
        result = parse_message(message)
        assert result == {"jsonrpc": "2.0", "method": "test"}

    def test_parse_invalid_json_string(self):
        """Test parsing invalid JSON string."""
        message = '{"invalid": json}'
        result = parse_message(message)
        assert result is None

    def test_parse_non_string(self):
        """Test parsing non-string input."""
        message = {"already": "parsed"}
        result = parse_message(message)
        assert result == {"already": "parsed"}

    def test_parse_empty_string(self):
        """Test parsing empty string."""
        result = parse_message("")
        assert result is None


class TestGetMessageType:
    """Test get_message_type function."""

    def test_request_message(self):
        """Test identifying request messages."""
        message = json.dumps({
            "jsonrpc": "2.0",
            "method": "tools/list",
            "id": "123"
        })
        assert get_message_type(message) == "request"

    def test_response_message(self):
        """Test identifying response messages."""
        message = json.dumps({
            "jsonrpc": "2.0",
            "result": {"tools": []},
            "id": "123"
        })
        assert get_message_type(message) == "response"

    def test_notification_message(self):
        """Test identifying notification messages."""
        message = json.dumps({
            "jsonrpc": "2.0",
            "method": "progress/update"
        })
        assert get_message_type(message) == "notification"

    def test_error_message(self):
        """Test identifying error messages."""
        message = json.dumps({
            "jsonrpc": "2.0",
            "error": {
                "code": -32600,
                "message": "Invalid Request"
            },
            "id": "123"
        })
        assert get_message_type(message) == "error"

    def test_unknown_message_no_jsonrpc(self):
        """Test message without jsonrpc field."""
        message = json.dumps({
            "method": "test",
            "id": "123"
        })
        assert get_message_type(message) == "unknown"

    def test_unknown_message_wrong_version(self):
        """Test message with wrong JSON-RPC version."""
        message = json.dumps({
            "jsonrpc": "1.0",
            "method": "test",
            "id": "123"
        })
        assert get_message_type(message) == "unknown"

    def test_unknown_message_invalid_json(self):
        """Test invalid JSON."""
        message = "not json"
        assert get_message_type(message) == "unknown"

    def test_edge_case_null_id(self):
        """Test request with null id (valid in JSON-RPC 2.0)."""
        message = json.dumps({
            "jsonrpc": "2.0",
            "method": "test",
            "id": None
        })
        assert get_message_type(message) == "request"

    def test_edge_case_error_without_id(self):
        """Test error without id (should be unknown)."""
        message = json.dumps({
            "jsonrpc": "2.0",
            "error": {"code": -32600, "message": "Error"}
        })
        assert get_message_type(message) == "unknown"

    def test_edge_case_result_without_id(self):
        """Test result without id (should be unknown)."""
        message = json.dumps({
            "jsonrpc": "2.0",
            "result": "test"
        })
        assert get_message_type(message) == "unknown"


class TestGetMethodName:
    """Test get_method_name function."""

    def test_get_method_from_request(self):
        """Test extracting method from request."""
        message = json.dumps({
            "jsonrpc": "2.0",
            "method": "tools/list",
            "id": "123"
        })
        assert get_method_name(message) == "tools/list"

    def test_get_method_from_notification(self):
        """Test extracting method from notification."""
        message = json.dumps({
            "jsonrpc": "2.0",
            "method": "progress/update"
        })
        assert get_method_name(message) == "progress/update"

    def test_get_method_from_response(self):
        """Test extracting method from response (should be None)."""
        message = json.dumps({
            "jsonrpc": "2.0",
            "result": {"tools": []},
            "id": "123"
        })
        assert get_method_name(message) is None

    def test_get_method_from_error(self):
        """Test extracting method from error (should be None)."""
        message = json.dumps({
            "jsonrpc": "2.0",
            "error": {"code": -32600, "message": "Error"},
            "id": "123"
        })
        assert get_method_name(message) is None

    def test_get_method_from_invalid_json(self):
        """Test extracting method from invalid JSON."""
        message = "not json"
        assert get_method_name(message) is None
