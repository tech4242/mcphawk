"""Fallback server detection for stdio transport when initialize message is not available."""

import re
from pathlib import Path
from typing import Optional


def detect_server_from_command(command: list[str]) -> Optional[dict[str, str]]:
    """
    Try to detect MCP server info from the command being executed.

    This is a fallback when we don't have initialize message info.

    Args:
        command: Command and arguments list

    Returns:
        Dict with 'name' and 'version' if detected, None otherwise
    """
    if not command:
        return None

    # Get the executable name
    exe = command[0]
    exe_name = Path(exe).name
    exe_path = Path(exe).stem  # without extension

    # Check if running Python module with -m
    if exe_name in ['python', 'python3', 'python3.exe', 'python.exe']:
        # Look for -m module_name pattern
        for i, arg in enumerate(command[1:], 1):
            if arg == '-m' and i < len(command) - 1:
                module = command[i + 1]

                # Special case for mcphawk
                if module == 'mcphawk' and i + 2 < len(command) and command[i + 2] == 'mcp':
                    return {'name': 'MCPHawk Query Server', 'version': 'unknown'}

                # Extract name from module
                name = extract_server_name(module)
                if name:
                    return {'name': name, 'version': 'unknown'}

    # Check executable name
    name = extract_server_name(exe_path)
    if name:
        return {'name': name, 'version': 'unknown'}

    # Check for .py files in arguments
    for arg in command[1:]:
        if arg.endswith('.py'):
            script_name = Path(arg).stem
            name = extract_server_name(script_name)
            if name:
                return {'name': name, 'version': 'unknown'}

    return None


def extract_server_name(text: str) -> Optional[str]:
    """
    Extract a human-readable server name from various text patterns.

    Args:
        text: Text to extract server name from (module name, exe name, etc)

    Returns:
        Human-readable server name or None
    """
    if not text or not isinstance(text, str):
        return None

    # Pattern 1: mcp-server-{name} or mcp_server_{name}
    match = re.match(r'^mcp[-_]server[-_](.+)$', text, re.IGNORECASE)
    if match:
        name_part = match.group(1)
        # Convert to title case, handling both - and _
        words = re.split(r'[-_]', name_part)
        return f"MCP {' '.join(word.capitalize() for word in words)} Server"

    # Pattern 2: {name}-mcp-server or {name}_mcp_server
    match = re.match(r'^(.+?)[-_]mcp[-_]server$', text, re.IGNORECASE)
    if match:
        name_part = match.group(1)
        words = re.split(r'[-_]', name_part)
        return f"{' '.join(word.capitalize() for word in words)} MCP Server"

    # Pattern 3: mcp-{name} or mcp_{name} (but not mcp-server)
    match = re.match(r'^mcp[-_](.+)$', text, re.IGNORECASE)
    if match:
        name_part = match.group(1)
        # Skip if it's just "server" without additional parts
        if name_part.lower() == 'server':
            return None
        words = re.split(r'[-_]', name_part)
        return f"MCP {' '.join(word.capitalize() for word in words)}"

    # Pattern 4: {name}-mcp or {name}_mcp
    match = re.match(r'^(.+?)[-_]mcp$', text, re.IGNORECASE)
    if match:
        name_part = match.group(1)
        words = re.split(r'[-_]', name_part)
        return f"{' '.join(word.capitalize() for word in words)} MCP"

    # Pattern 5: contains 'mcp' somewhere
    if 'mcp' in text.lower():
        # Clean up and format
        words = re.split(r'[-_]', text)
        # Filter out empty strings from split
        words = [w for w in words if w]
        formatted_words = []
        for word in words:
            if word.lower() == 'mcp':
                formatted_words.append('MCP')
            else:
                formatted_words.append(word.capitalize())
        return ' '.join(formatted_words)

    return None


def merge_server_info(
    detected: Optional[dict[str, str]],
    from_protocol: Optional[dict[str, str]]
) -> Optional[dict[str, str]]:
    """
    Merge server info from command detection and protocol messages.

    Protocol info takes precedence as it's more accurate.

    Args:
        detected: Server info detected from command
        from_protocol: Server info from initialize response

    Returns:
        Merged server info or None
    """
    if from_protocol:
        return from_protocol
    return detected
