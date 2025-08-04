"""Stdio capture implementation that works within macOS SIP limitations."""

import json
import logging
import os
import subprocess
import sys
import threading
import uuid
from datetime import datetime, timezone
from typing import Optional, TextIO

from mcphawk.logger import log_message
from mcphawk.web.broadcaster import broadcast_new_log

logger = logging.getLogger(__name__)


class StdioCapture:
    """Capture stdio for specific processes we control."""

    def __init__(self, debug: bool = False):
        self.debug = debug
        self.running = False

    def capture_subprocess(self, cmd: list[str], env: Optional[dict] = None) -> subprocess.Popen:
        """
        Run a subprocess with captured stdio.

        This is the most reliable way to capture stdio on macOS with SIP.
        """
        logger.info(f"Starting subprocess with stdio capture: {' '.join(cmd)}")

        proc = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            stdin=subprocess.PIPE,
            text=True,
            bufsize=1,
            env=env
        )

        # Start monitoring threads
        self._start_monitor_thread(proc.stdout, proc.pid, "stdout")
        self._start_monitor_thread(proc.stderr, proc.pid, "stderr")

        return proc

    def _start_monitor_thread(self, stream: Optional[TextIO], pid: int, stream_name: str):
        """Start a thread to monitor a stream."""
        if not stream:
            return

        def monitor():
            buffer = ""
            for line in stream:
                if self.debug:
                    logger.debug(f"PID {pid} {stream_name}: {line.rstrip()}")

                # Add to buffer
                buffer += line

                # Try to extract JSON-RPC messages
                while True:
                    # Look for complete JSON objects
                    start = buffer.find('{')
                    if start == -1:
                        break

                    # Try to find the end of the JSON
                    brace_count = 0
                    in_string = False
                    escape_next = False
                    end = start

                    for i in range(start, len(buffer)):
                        char = buffer[i]

                        if escape_next:
                            escape_next = False
                            continue

                        if char == '\\':
                            escape_next = True
                            continue

                        if char == '"' and not escape_next:
                            in_string = not in_string
                            continue

                        if not in_string:
                            if char == '{':
                                brace_count += 1
                            elif char == '}':
                                brace_count -= 1
                                if brace_count == 0:
                                    end = i + 1
                                    break

                    if brace_count != 0:
                        # Incomplete JSON, wait for more data
                        break

                    # Extract the JSON
                    json_str = buffer[start:end]
                    buffer = buffer[end:]

                    try:
                        msg = json.loads(json_str)
                        if msg.get("jsonrpc") == "2.0":
                            self._process_jsonrpc_message(msg, pid, stream_name)
                    except json.JSONDecodeError:
                        if self.debug:
                            logger.debug(f"Failed to parse JSON: {json_str[:50]}...")

        thread = threading.Thread(target=monitor, daemon=True)
        thread.start()

    def _process_jsonrpc_message(self, message: dict, pid: int, source: str) -> None:
        """Process a captured JSON-RPC message."""
        try:
            # Create log entry
            ts = datetime.now(tz=timezone.utc)
            log_id = str(uuid.uuid4())

            # Determine direction based on message type
            if "method" in message and "id" not in message:
                direction = "outgoing"  # Notification
            elif "method" in message:
                direction = "outgoing"  # Request
            else:
                direction = "incoming"  # Response

            entry = {
                "log_id": log_id,
                "timestamp": ts,
                "src_ip": "stdio",
                "src_port": None,  # No port for stdio
                "dst_ip": "stdio",
                "dst_port": None,  # No port for stdio
                "direction": direction,
                "message": json.dumps(message),
                "transport_type": "stdio",
                "metadata": json.dumps({"process_id": pid, "source": source}),
                "pid": pid  # Add PID field
            }

            # Log to database
            log_message(entry)

            # Broadcast to web UI
            broadcast_entry = dict(entry)
            broadcast_entry["timestamp"] = ts.isoformat()

            # Try to broadcast
            try:
                import asyncio
                try:
                    loop = asyncio.get_running_loop()
                    _ = loop.create_task(broadcast_new_log(broadcast_entry))  # noqa: RUF006
                except RuntimeError:
                    # No event loop in this thread
                    asyncio.run(broadcast_new_log(broadcast_entry))
            except Exception as e:
                if self.debug:
                    logger.debug(f"Broadcast failed: {e}")

            logger.info(f"Captured stdio JSON-RPC from PID {pid} ({source}): {message.get('method', 'response')}")

        except Exception as e:
            logger.error(f"Error processing JSON-RPC message: {e}")


class StdioWrapper:
    """
    Wrapper to intercept stdio for the current process.

    Usage:
        wrapper = StdioWrapper()
        wrapper.install()
        # Now all stdout/stderr is monitored
        wrapper.uninstall()
    """

    def __init__(self, debug: bool = False):
        self.debug = debug
        self.original_stdout = None
        self.original_stderr = None
        self.capture = StdioCapture(debug=debug)

    def install(self):
        """Replace stdout/stderr with monitoring versions."""
        self.original_stdout = sys.stdout
        self.original_stderr = sys.stderr

        sys.stdout = MonitoredFile(sys.stdout, os.getpid(), "stdout", self.capture)
        sys.stderr = MonitoredFile(sys.stderr, os.getpid(), "stderr", self.capture)

        logger.info("Stdio wrapper installed")

    def uninstall(self):
        """Restore original stdout/stderr."""
        if self.original_stdout:
            sys.stdout = self.original_stdout
        if self.original_stderr:
            sys.stderr = self.original_stderr

        logger.info("Stdio wrapper uninstalled")


class MonitoredFile:
    """A file-like object that monitors writes for JSON-RPC."""

    def __init__(self, original, pid: int, name: str, capture: StdioCapture):
        self.original = original
        self.pid = pid
        self.name = name
        self.capture = capture
        self.buffer = ""

    def write(self, data: str) -> int:
        """Write data and check for JSON-RPC."""
        # Write to original
        result = self.original.write(data)

        # Add to buffer and check for JSON-RPC
        self.buffer += data

        # Check for complete JSON objects (simplified check)
        if '{"jsonrpc"' in self.buffer and '}' in self.buffer:
            lines = self.buffer.split('\n')
            self.buffer = lines[-1]  # Keep incomplete last line

            for line in lines[:-1]:
                if '{"jsonrpc"' in line:
                    try:
                        # Try to extract JSON from the line
                        start = line.find('{')
                        end = line.rfind('}') + 1
                        if start >= 0 and end > start:
                            json_str = line[start:end]
                            msg = json.loads(json_str)
                            if msg.get("jsonrpc") == "2.0":
                                self.capture._process_jsonrpc_message(msg, self.pid, self.name)
                    except Exception:
                        pass

        return result

    def __getattr__(self, name):
        """Delegate all other attributes to the original file."""
        return getattr(self.original, name)


# Example usage function
def run_with_stdio_capture(cmd: list[str], debug: bool = False) -> int:
    """
    Run a command with stdio capture.

    This is the recommended way to capture stdio on macOS with SIP.
    """
    capture = StdioCapture(debug=debug)
    proc = capture.capture_subprocess(cmd)

    # Wait for process to complete
    return proc.wait()
