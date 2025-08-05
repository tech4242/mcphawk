"""MCP server wrapper for transparent stdio monitoring."""

import asyncio
import contextlib
import json
import logging
import os
import signal
import subprocess
import sys
import threading
import time
import uuid
from datetime import datetime, timezone
from typing import Optional

from mcphawk.logger import log_message
from mcphawk.stdio_server_detector_fallback import (
    detect_server_from_command,
    merge_server_info,
)
from mcphawk.web.broadcaster import broadcast_new_log

logger = logging.getLogger(__name__)


class MCPWrapper:
    """Transparently wrap an MCP server to capture stdio traffic."""

    def __init__(self, command: list[str], debug: bool = False):
        self.command = command
        self.debug = debug
        self.proc: Optional[subprocess.Popen] = None
        self.running = False
        self.server_info = None  # Track server info from initialize response
        self.client_info = None  # Track client info from initialize request
        self.server_info_fallback = detect_server_from_command(command)  # Fallback detection
        self.stdin_thread: Optional[threading.Thread] = None
        self.stdout_thread: Optional[threading.Thread] = None
        self.stderr_thread: Optional[threading.Thread] = None

    def start(self) -> int:
        """Start the wrapper and return exit code."""
        try:
            # Start the actual MCP server
            logger.info(f"Starting MCP server: {' '.join(self.command)}")

            self.proc = subprocess.Popen(
                self.command,
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                bufsize=0  # Unbuffered for real-time
            )

            self.running = True

            # Start forwarding threads
            self.stdin_thread = threading.Thread(
                target=self._forward_stdin,
                daemon=True
            )
            self.stdout_thread = threading.Thread(
                target=self._forward_stdout,
                daemon=True
            )
            self.stderr_thread = threading.Thread(
                target=self._forward_stderr,
                daemon=True
            )

            self.stdin_thread.start()
            self.stdout_thread.start()
            self.stderr_thread.start()

            # Wait for process to complete
            return_code = self.proc.wait()
            self.running = False

            # Give threads time to finish
            time.sleep(0.1)

            return return_code

        except KeyboardInterrupt:
            logger.info("Wrapper interrupted")
            self.stop()
            return 130  # Standard exit code for SIGINT
        except Exception as e:
            logger.error(f"Wrapper error: {e}")
            self.stop()
            return 1

    def stop(self):
        """Stop the wrapper and subprocess."""
        self.running = False
        if self.proc:
            self.proc.terminate()
            try:
                self.proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                self.proc.kill()

    def _forward_stdin(self):
        """Forward stdin from parent to subprocess, capturing JSON-RPC."""
        try:
            buffer = ""
            while self.running and self.proc and self.proc.stdin:
                # Read from our stdin
                char = sys.stdin.read(1)
                if not char:
                    break

                # Forward to subprocess
                self.proc.stdin.write(char)
                self.proc.stdin.flush()

                # Build buffer for JSON detection
                buffer += char

                # Check for complete JSON messages
                if char == '\n':
                    line = buffer.strip()
                    if line:
                        self._try_parse_json(line, "client->server")
                    buffer = ""

        except Exception as e:
            if self.debug:
                logger.debug(f"stdin forward error: {e}")

    def _forward_stdout(self):
        """Forward stdout from subprocess to parent, capturing JSON-RPC."""
        try:
            buffer = ""
            while self.running and self.proc and self.proc.stdout:
                # Read from subprocess
                char = self.proc.stdout.read(1)
                if not char:
                    break

                # Forward to our stdout
                sys.stdout.write(char)
                sys.stdout.flush()

                # Build buffer for JSON detection
                buffer += char

                # Check for complete JSON messages
                if char == '\n':
                    line = buffer.strip()
                    if line:
                        self._try_parse_json(line, "server->client")
                    buffer = ""

        except Exception as e:
            if self.debug:
                logger.debug(f"stdout forward error: {e}")

    def _forward_stderr(self):
        """Forward stderr from subprocess to parent."""
        try:
            while self.running and self.proc and self.proc.stderr:
                # Read from subprocess
                char = self.proc.stderr.read(1)
                if not char:
                    break

                # Forward to our stderr
                sys.stderr.write(char)
                sys.stderr.flush()

        except Exception as e:
            if self.debug:
                logger.debug(f"stderr forward error: {e}")

    def _try_parse_json(self, line: str, direction: str):
        """Try to parse a line as JSON-RPC and log if successful."""
        try:
            # Skip empty lines
            if not line.strip():
                return

            # Try to parse as JSON
            msg = json.loads(line)

            # Check if it's JSON-RPC
            if msg.get("jsonrpc") == "2.0":
                # Extract server/client info if this is an initialize message
                if direction == "client->server":
                    # Check for client info in initialize request
                    from .utils import extract_client_info
                    client_info = extract_client_info(json.dumps(msg))
                    if client_info:
                        self.client_info = client_info
                        if self.debug:
                            logger.debug(f"Captured client info: {client_info}")

                elif direction == "server->client":
                    # Check for server info in initialize response
                    from .utils import extract_server_info
                    server_info = extract_server_info(json.dumps(msg))
                    if server_info:
                        self.server_info = server_info
                        if self.debug:
                            logger.debug(f"Captured server info: {server_info}")

                self._log_jsonrpc_message(msg, direction)

        except json.JSONDecodeError:
            # Not JSON, ignore
            pass
        except Exception as e:
            if self.debug:
                logger.debug(f"Error parsing JSON: {e}")

    def _log_jsonrpc_message(self, message: dict, direction: str):
        """Log a JSON-RPC message to the database."""
        try:
            # Create log entry
            ts = datetime.now(tz=timezone.utc)
            log_id = str(uuid.uuid4())

            # Parse direction
            if direction == "client->server":
                src_ip = "mcp-client"
                dst_ip = "mcp-server"
                flow_direction = "outgoing"
            else:
                src_ip = "mcp-server"
                dst_ip = "mcp-client"
                flow_direction = "incoming"

            # Get process info
            pid = self.proc.pid if self.proc else os.getpid()

            # Build metadata with server info
            metadata = {
                "wrapper": True,
                "command": self.command,
                "direction": direction
            }

            # Merge server info (protocol takes precedence over fallback)
            merged_server_info = merge_server_info(self.server_info_fallback, self.server_info)
            if merged_server_info:
                metadata["server_name"] = merged_server_info["name"]
                metadata["server_version"] = merged_server_info["version"]

            # Add client info if we have it
            if self.client_info:
                metadata["client_name"] = self.client_info["name"]
                metadata["client_version"] = self.client_info["version"]

            entry = {
                "log_id": log_id,
                "timestamp": ts,
                "src_ip": src_ip,
                "src_port": None,  # No port for stdio
                "dst_ip": dst_ip,
                "dst_port": None,  # No port for stdio
                "direction": flow_direction,
                "message": json.dumps(message),
                "transport_type": "stdio",
                "metadata": json.dumps(metadata),
                "pid": pid  # Add PID field
            }

            # Log to database
            log_message(entry)

            # Broadcast to web UI
            broadcast_entry = dict(entry)
            broadcast_entry["timestamp"] = ts.isoformat()

            # Try to broadcast
            try:
                loop = asyncio.get_running_loop()
                _ = loop.create_task(broadcast_new_log(broadcast_entry))  # noqa: RUF006
            except RuntimeError:
                # No event loop in this thread, try to create one
                with contextlib.suppress(Exception):
                    asyncio.run(broadcast_new_log(broadcast_entry))

            # Log info
            method = message.get("method", "response")
            logger.info(f"Captured {direction} JSON-RPC: {method}")

        except Exception as e:
            logger.error(f"Error logging JSON-RPC message: {e}")


def run_wrapper(command: list[str], debug: bool = False) -> int:
    """Run the MCP wrapper with the given command."""
    # Set up signal handling
    def signal_handler(signum, frame):
        logger.info("Received signal, shutting down wrapper")
        sys.exit(130)

    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    # Create and run wrapper
    wrapper = MCPWrapper(command, debug=debug)
    return wrapper.start()
