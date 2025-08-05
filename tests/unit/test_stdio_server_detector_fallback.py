"""Unit tests for stdio server detection fallback."""


from mcphawk.stdio_server_detector_fallback import (
    detect_server_from_command,
    extract_server_name,
    merge_server_info,
)


class TestExtractServerName:
    """Test the extract_server_name function."""

    def test_mcp_server_pattern(self):
        """Test mcp-server-{name} and mcp_server_{name} patterns."""
        assert extract_server_name("mcp-server-filesystem") == "MCP Filesystem Server"
        assert extract_server_name("mcp_server_filesystem") == "MCP Filesystem Server"
        assert extract_server_name("mcp-server-git") == "MCP Git Server"
        assert extract_server_name("mcp_server_github") == "MCP Github Server"
        assert extract_server_name("MCP-SERVER-SQLITE") == "MCP Sqlite Server"
        assert extract_server_name("mcp-server-brave-search") == "MCP Brave Search Server"
        assert extract_server_name("mcp_server_multi_word_name") == "MCP Multi Word Name Server"

    def test_name_mcp_server_pattern(self):
        """Test {name}-mcp-server and {name}_mcp_server patterns."""
        assert extract_server_name("filesystem-mcp-server") == "Filesystem MCP Server"
        assert extract_server_name("my_custom_mcp_server") == "My Custom MCP Server"
        assert extract_server_name("github-actions-mcp-server") == "Github Actions MCP Server"

    def test_mcp_name_pattern(self):
        """Test mcp-{name} and mcp_{name} patterns."""
        assert extract_server_name("mcp-filesystem") == "MCP Filesystem"
        assert extract_server_name("mcp_git") == "MCP Git"
        assert extract_server_name("mcp-query") == "MCP Query"
        # Should not match mcp-server (too generic)
        assert extract_server_name("mcp-server") is None

    def test_name_mcp_pattern(self):
        """Test {name}-mcp and {name}_mcp patterns."""
        assert extract_server_name("filesystem-mcp") == "Filesystem MCP"
        assert extract_server_name("github_mcp") == "Github MCP"
        assert extract_server_name("my-custom-mcp") == "My Custom MCP"

    def test_contains_mcp(self):
        """Test names that contain 'mcp' somewhere."""
        assert extract_server_name("my-mcp-tool") == "My MCP Tool"
        assert extract_server_name("tool_with_mcp_support") == "Tool With MCP Support"
        assert extract_server_name("mcptools") == "Mcptools"

    def test_no_mcp(self):
        """Test names without 'mcp' return None."""
        assert extract_server_name("regular-server") is None
        assert extract_server_name("python-app") is None
        assert extract_server_name("node") is None

    def test_edge_cases(self):
        """Test edge cases."""
        assert extract_server_name("") is None
        assert extract_server_name(None) is None
        assert extract_server_name("mcp") == "MCP"
        assert extract_server_name("MCP") == "MCP"
        assert extract_server_name("_mcp_") == "MCP"


class TestDetectServerFromCommand:
    """Test the detect_server_from_command function."""

    def test_empty_command(self):
        """Test with empty or None command."""
        assert detect_server_from_command([]) is None
        assert detect_server_from_command(None) is None

    def test_direct_executable(self):
        """Test detection from direct executable names."""
        assert detect_server_from_command(["mcp-server-filesystem"]) == {
            "name": "MCP Filesystem Server",
            "version": "unknown"
        }
        assert detect_server_from_command(["/usr/local/bin/mcp-server-git"]) == {
            "name": "MCP Git Server",
            "version": "unknown"
        }
        assert detect_server_from_command(["./mcp_server_github"]) == {
            "name": "MCP Github Server",
            "version": "unknown"
        }

    def test_python_module(self):
        """Test detection from python -m module patterns."""
        assert detect_server_from_command(["python", "-m", "mcp_server_filesystem"]) == {
            "name": "MCP Filesystem Server",
            "version": "unknown"
        }
        assert detect_server_from_command(["python3", "-m", "mcp-server-git"]) == {
            "name": "MCP Git Server",
            "version": "unknown"
        }
        assert detect_server_from_command(["python3.exe", "-m", "my_mcp_tool"]) == {
            "name": "My MCP Tool",
            "version": "unknown"
        }

    def test_mcphawk_special_case(self):
        """Test special case for mcphawk mcp command."""
        assert detect_server_from_command(["python", "-m", "mcphawk", "mcp"]) == {
            "name": "MCPHawk Query Server",
            "version": "unknown"
        }
        assert detect_server_from_command(["python3", "-m", "mcphawk", "mcp", "--transport", "stdio"]) == {
            "name": "MCPHawk Query Server",
            "version": "unknown"
        }
        # Without 'mcp' subcommand, should use regular detection
        assert detect_server_from_command(["python", "-m", "mcphawk", "wrap"]) == {
            "name": "Mcphawk",
            "version": "unknown"
        }

    def test_python_script(self):
        """Test detection from .py script names."""
        assert detect_server_from_command(["python", "mcp-server-custom.py"]) == {
            "name": "MCP Custom Server",
            "version": "unknown"
        }
        assert detect_server_from_command(["python3", "/path/to/my_mcp_server.py", "--port", "8080"]) == {
            "name": "My MCP Server",
            "version": "unknown"
        }
        # Non-MCP scripts should return None
        assert detect_server_from_command(["python", "regular_script.py"]) is None

    def test_complex_commands(self):
        """Test more complex command patterns."""
        assert detect_server_from_command([
            "/usr/bin/python3", "-u", "-m", "mcp_server_filesystem", "--path", "/tmp"
        ]) == {
            "name": "MCP Filesystem Server",
            "version": "unknown"
        }
        assert detect_server_from_command([
            "node", "/app/mcp-server-nodejs.js"
        ]) is None  # .js files not supported

    def test_no_mcp_commands(self):
        """Test commands without MCP should return None."""
        assert detect_server_from_command(["ls", "-la"]) is None
        assert detect_server_from_command(["python", "script.py"]) is None
        assert detect_server_from_command(["node", "server.js"]) is None


class TestMergeServerInfo:
    """Test the merge_server_info function."""

    def test_protocol_takes_precedence(self):
        """Test that protocol info takes precedence over detected."""
        detected = {"name": "Detected Server", "version": "unknown"}
        from_protocol = {"name": "Protocol Server", "version": "1.0.0"}

        assert merge_server_info(detected, from_protocol) == from_protocol

    def test_fallback_to_detected(self):
        """Test fallback to detected when no protocol info."""
        detected = {"name": "Detected Server", "version": "unknown"}

        assert merge_server_info(detected, None) == detected

    def test_both_none(self):
        """Test when both are None."""
        assert merge_server_info(None, None) is None

    def test_only_protocol(self):
        """Test when only protocol info exists."""
        from_protocol = {"name": "Protocol Server", "version": "1.0.0"}

        assert merge_server_info(None, from_protocol) == from_protocol
