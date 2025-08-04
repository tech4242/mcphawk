"""Tests for utility functions."""

import json

from mcphawk.utils import (
    extract_client_info,
    extract_server_info,
    get_message_type,
    get_method_name,
    parse_message,
)


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


class TestExtractServerInfo:
    """Test extract_server_info function."""

    def test_extract_server_info_from_initialize_response(self):
        """Test extracting serverInfo from initialize response."""
        message = json.dumps({
            "jsonrpc": "2.0",
            "result": {
                "protocolVersion": "2024-11-05",
                "serverInfo": {
                    "name": "test-server",
                    "version": "1.0.0"
                }
            },
            "id": "123"
        })
        result = extract_server_info(message)
        assert result == {"name": "test-server", "version": "1.0.0"}

    def test_extract_server_info_missing_version(self):
        """Test extracting serverInfo without version."""
        message = json.dumps({
            "jsonrpc": "2.0",
            "result": {
                "serverInfo": {
                    "name": "test-server"
                }
            },
            "id": "123"
        })
        result = extract_server_info(message)
        assert result == {"name": "test-server", "version": "unknown"}

    def test_extract_server_info_from_non_initialize(self):
        """Test extracting serverInfo from non-initialize response."""
        message = json.dumps({
            "jsonrpc": "2.0",
            "result": {"tools": []},
            "id": "123"
        })
        result = extract_server_info(message)
        assert result is None

    def test_extract_server_info_from_request(self):
        """Test extracting serverInfo from request (should be None)."""
        message = json.dumps({
            "jsonrpc": "2.0",
            "method": "initialize",
            "params": {},
            "id": "123"
        })
        result = extract_server_info(message)
        assert result is None

    def test_extract_server_info_invalid_json(self):
        """Test extracting serverInfo from invalid JSON."""
        message = "not json"
        result = extract_server_info(message)
        assert result is None

    def test_extract_server_info_missing_name(self):
        """Test extracting serverInfo without name field."""
        message = json.dumps({
            "jsonrpc": "2.0",
            "result": {
                "serverInfo": {
                    "version": "1.0.0"
                }
            },
            "id": "123"
        })
        result = extract_server_info(message)
        assert result is None


class TestExtractClientInfo:
    """Test extract_client_info function."""

    def test_extract_client_info_from_initialize_request(self):
        """Test extracting clientInfo from initialize request."""
        message = json.dumps({
            "jsonrpc": "2.0",
            "method": "initialize",
            "params": {
                "protocolVersion": "2024-11-05",
                "clientInfo": {
                    "name": "test-client",
                    "version": "2.0.0"
                }
            },
            "id": "123"
        })
        result = extract_client_info(message)
        assert result == {"name": "test-client", "version": "2.0.0"}

    def test_extract_client_info_missing_version(self):
        """Test extracting clientInfo without version."""
        message = json.dumps({
            "jsonrpc": "2.0",
            "method": "initialize",
            "params": {
                "clientInfo": {
                    "name": "test-client"
                }
            },
            "id": "123"
        })
        result = extract_client_info(message)
        assert result == {"name": "test-client", "version": "unknown"}

    def test_extract_client_info_from_non_initialize(self):
        """Test extracting clientInfo from non-initialize request."""
        message = json.dumps({
            "jsonrpc": "2.0",
            "method": "tools/list",
            "params": {},
            "id": "123"
        })
        result = extract_client_info(message)
        assert result is None

    def test_extract_client_info_from_response(self):
        """Test extracting clientInfo from response (should be None)."""
        message = json.dumps({
            "jsonrpc": "2.0",
            "result": {"tools": []},
            "id": "123"
        })
        result = extract_client_info(message)
        assert result is None

    def test_extract_client_info_invalid_json(self):
        """Test extracting clientInfo from invalid JSON."""
        message = "not json"
        result = extract_client_info(message)
        assert result is None

    def test_extract_client_info_missing_name(self):
        """Test extracting clientInfo without name field."""
        message = json.dumps({
            "jsonrpc": "2.0",
            "method": "initialize",
            "params": {
                "clientInfo": {
                    "version": "2.0.0"
                }
            },
            "id": "123"
        })
        result = extract_client_info(message)
        assert result is None

    def test_extract_client_info_wrong_method(self):
        """Test extracting clientInfo with wrong method."""
        message = json.dumps({
            "jsonrpc": "2.0",
            "method": "tools/list",
            "params": {
                "clientInfo": {
                    "name": "test-client",
                    "version": "2.0.0"
                }
            },
            "id": "123"
        })
        result = extract_client_info(message)
        assert result is None
