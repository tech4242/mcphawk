"""Transparent stdio shim: ``mcphawk wrap -- <server command>``.

Bytes are forwarded first and recorded second, so a slow disk or a bug in
recording can never stall or corrupt the traffic between client and server.
"""

import contextlib
import logging
import os
import shlex
import signal
import subprocess
import sys
import threading
from collections.abc import Callable
from typing import BinaryIO

from mcphawk.capture.process import find_client
from mcphawk.protocol.masking import mask_argv
from mcphawk.store import C2S, S2C, Recorder

logger = logging.getLogger(__name__)

CHUNK = 64 * 1024
MAX_LINE = 64 * 1024 * 1024


class LineFramer:
    """Splits a byte stream into newline-delimited frames."""

    def __init__(self, on_line: Callable[[bytes], None]):
        self._buffer = bytearray()
        self._on_line = on_line

    def feed(self, chunk: bytes) -> None:
        self._buffer.extend(chunk)
        while True:
            index = self._buffer.find(b"\n")
            if index < 0:
                break
            line = bytes(self._buffer[:index])
            del self._buffer[:index + 1]
            self._emit(line)
        if len(self._buffer) > MAX_LINE:
            self._emit(bytes(self._buffer))
            self._buffer.clear()

    def flush(self) -> None:
        if self._buffer:
            self._emit(bytes(self._buffer))
            self._buffer.clear()

    def _emit(self, line: bytes) -> None:
        if line.strip():
            try:
                self._on_line(line)
            except Exception:  # recording must never break forwarding
                logger.exception("failed to record frame")


def _read_chunk(stream: BinaryIO) -> bytes:
    reader = getattr(stream, "read1", None)
    return reader(CHUNK) if reader else stream.read(CHUNK)


def _pump(source: BinaryIO, sink: BinaryIO | None, framer: LineFramer,
          close_sink: bool) -> None:
    try:
        while True:
            chunk = _read_chunk(source)
            if not chunk:
                break
            if sink is not None:
                try:
                    sink.write(chunk)
                    sink.flush()
                except (BrokenPipeError, OSError, ValueError):
                    sink = None  # peer is gone; keep draining for the record
            framer.feed(chunk)
    except (OSError, ValueError):
        pass
    finally:
        framer.flush()
        if close_sink and sink is not None:
            with contextlib.suppress(OSError):
                sink.close()


class StdioShim:
    def __init__(
        self,
        command: list[str],
        *,
        name: str | None = None,
        recorder: Recorder | None = None,
        stdin: BinaryIO | None = None,
        stdout: BinaryIO | None = None,
        stderr: BinaryIO | None = None,
        mask: bool = True,
    ):
        if not command:
            raise ValueError("no server command given")
        self.command = command
        self.name = name
        self._mask = mask
        self.recorder = recorder
        self._stdin = stdin or sys.stdin.buffer
        self._stdout = stdout or sys.stdout.buffer
        self._stderr = stderr or sys.stderr.buffer
        self.proc: subprocess.Popen | None = None
        self.session_id: str | None = None

    def run(self) -> int:
        try:
            self.proc = subprocess.Popen(
                self.command, stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                stderr=subprocess.PIPE, bufsize=0)
        except OSError as exc:
            self._stderr.write(f"mcphawk: cannot start {self.command[0]!r}: {exc}\n".encode())
            self._stderr.flush()
            return 127

        sid = self._open_session()
        if sid is None:  # recording is unavailable: forward only
            to_server = LineFramer(lambda _: None)
            to_client = LineFramer(lambda _: None)
        else:
            to_server = LineFramer(lambda line: self.recorder.record(sid, C2S, line))
            to_client = LineFramer(lambda line: self.recorder.record(sid, S2C, line))

        threads = [
            threading.Thread(target=_pump, args=(self._stdin, self.proc.stdin, to_server, True),
                             daemon=True),
            threading.Thread(target=_pump, args=(self.proc.stdout, self._stdout, to_client,
                                                 False), daemon=True),
            threading.Thread(target=_pump, args=(self.proc.stderr, self._stderr,
                                                 LineFramer(lambda _: None), False),
                             daemon=True),
        ]
        for thread in threads:
            thread.start()
        try:
            code = self.proc.wait()
        except KeyboardInterrupt:
            self.terminate()
            code = self.proc.wait()
        # stdout/stderr hit EOF once the server exits; the stdin pump may
        # block on the client forever, so it is not joined.
        for thread in threads[1:]:
            thread.join(timeout=2)
        if sid is not None:
            with contextlib.suppress(Exception):
                self.recorder.end_session(sid)
        return code

    def _open_session(self) -> str | None:
        """Start recording; on any failure keep the server usable and say why once."""
        try:
            if self.recorder is None:
                self.recorder = Recorder(mask=self._mask)
            client = find_client()
            argv = mask_argv(self.command) if self._mask else self.command
            self.session_id = self.recorder.open_session(
                capture="wrap", transport="stdio",
                name=self.name or os.path.basename(self.command[0]),
                target=shlex.join(argv), pid=os.getpid(),
                client_pid=client.pid if client else None,
                client_app=client.name if client else None,
                client_key=client.client_key if client else None,
            )
            return self.session_id
        except Exception as exc:
            self._stderr.write(
                f"mcphawk: not recording this server ({exc}); traffic is forwarded "
                "unchanged\n".encode())
            self._stderr.flush()
            return None

    def terminate(self, *_: object) -> None:
        if self.proc and self.proc.poll() is None:
            self.proc.terminate()
            try:
                self.proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                self.proc.kill()


def run_wrap(command: list[str], name: str | None = None, mask: bool = True) -> int:
    shim = StdioShim(command, name=name, mask=mask)
    signal.signal(signal.SIGTERM, shim.terminate)
    if hasattr(signal, "SIGHUP"):
        signal.signal(signal.SIGHUP, shim.terminate)
    code = shim.run()
    # a server killed by a signal reports -N; shells expect 128 + N
    return 128 - code if code < 0 else code
