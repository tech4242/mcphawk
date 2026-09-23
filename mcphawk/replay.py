"""Re-send a captured request (optionally edited) to the same server.

The replay runs in a fresh connection and is recorded as its own session
(capture ``replay``), so it can be compared with the original. Replays can
have side effects - it is a real tool call - so the UI asks first and the
MCP server does not expose this at all.
"""

import asyncio
import copy
import json
import shlex
from typing import Any

import httpx

from mcphawk.capture.sse import SSEParser
from mcphawk.protocol import mcp as proto
from mcphawk.protocol.masking import MASK
from mcphawk.query import Query
from mcphawk.store import C2S, S2C, Recorder

REPLAY_ID = "mcphawk-replay"
LEGACY_FALLBACK_VERSION = "2025-06-18"
TIMEOUT_S = 30.0


class ReplayError(Exception):
    pass


def _initialize_request(q: Query, session: dict[str, Any]) -> dict[str, Any]:
    """The session's own initialize request, or a minimal one."""
    for message in q.messages_for(session["id"]):
        body = message["body"]
        if isinstance(body, dict) and body.get("method") == "initialize":
            return {**body, "id": f"{REPLAY_ID}-init"}
    return {
        "jsonrpc": "2.0", "id": f"{REPLAY_ID}-init", "method": "initialize",
        "params": {
            "protocolVersion": session.get("protocol_version") or LEGACY_FALLBACK_VERSION,
            "capabilities": {}, "clientInfo": {"name": "mcphawk-replay", "version": "1"},
        },
    }


def _prepare(q: Query, exchange_id: int, params: dict[str, Any] | None
             ) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
    exchange = q.get_exchange(exchange_id)
    if not exchange:
        raise ReplayError(f"exchange {exchange_id} not found")
    if exchange["initiator"] != "client":
        raise ReplayError("only client requests can be replayed")
    request = copy.deepcopy(exchange["request"]["body"])
    if params is not None:
        request["params"] = params
    request["id"] = REPLAY_ID
    if MASK in json.dumps(request, ensure_ascii=False):
        raise ReplayError("the request contains masked secrets; edit them before replaying")
    return exchange, exchange["session"], request


async def replay(q: Query, recorder: Recorder, exchange_id: int,
                 params: dict[str, Any] | None = None,
                 timeout: float = TIMEOUT_S) -> dict[str, Any]:
    exchange, session, request = _prepare(q, exchange_id, params)
    legacy = session.get("era") != proto.MODERN
    handshake = [_initialize_request(q, session)] if legacy else []
    if session["transport"] == "stdio" and session["capture"] in ("wrap", "replay"):
        runner = _replay_stdio
    elif session["transport"] == "streamable_http":
        runner = _replay_http
    else:
        raise ReplayError(f"replay is not supported for {session['transport']} sessions")

    new_session = recorder.open_session(
        capture="replay", transport=session["transport"],
        name=f"{session['display_name']} (replay)", target=session["target"],
        run_key=f"replay:{exchange_id}")
    try:
        response = await asyncio.wait_for(
            runner(session, handshake, request, lambda d, m: recorder.record(
                new_session, d, json.dumps(m) if isinstance(m, dict) else m)),
            timeout)
    except asyncio.TimeoutError:
        raise ReplayError(f"no response within {timeout:.0f}s") from None
    finally:
        recorder.end_session(new_session)
    replayed = q.get_session(new_session)
    new_exchange = next((e for e in reversed(replayed["exchanges"])
                         if e["method"] == exchange["method"]), None)
    return {
        "session_id": new_session,
        "exchange_id": new_exchange["id"] if new_exchange else None,
        "status": new_exchange["status"] if new_exchange else None,
        "response": response,
    }


async def _replay_stdio(session, handshake, request, record) -> dict[str, Any]:
    command = shlex.split(session["target"] or "")
    if not command:
        raise ReplayError("session has no command to run")
    if any(MASK in part for part in command):
        raise ReplayError("the server command contains masked secrets; "
                          "wrap it with --no-mask to replay")
    proc = await asyncio.create_subprocess_exec(
        *command, stdin=asyncio.subprocess.PIPE, stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.DEVNULL)

    async def send(message: dict[str, Any]) -> None:
        record(C2S, message)
        proc.stdin.write(json.dumps(message).encode() + b"\n")
        await proc.stdin.drain()

    async def wait_for(rpc_id: str) -> dict[str, Any]:
        while True:
            line = await proc.stdout.readline()
            if not line:
                raise ReplayError("server exited before answering")
            if not line.strip():
                continue
            record(S2C, line.decode("utf-8", "replace"))
            try:
                message = json.loads(line)
            except json.JSONDecodeError:
                continue
            if isinstance(message, dict) and message.get("id") == rpc_id:
                return message

    try:
        for init in handshake:
            await send(init)
            await wait_for(init["id"])
            await send({"jsonrpc": "2.0", "method": "notifications/initialized"})
        await send(request)
        return await wait_for(request["id"])
    finally:
        if proc.returncode is None:
            proc.terminate()
            await proc.wait()


def _http_headers(message: dict[str, Any], session_id: str | None) -> dict[str, str]:
    headers = {"Accept": "application/json, text/event-stream",
               "Content-Type": "application/json"}
    version = proto.protocol_version(message)
    if version and proto.era_of_version(version) == proto.MODERN:
        headers["MCP-Protocol-Version"] = version
        headers["Mcp-Method"] = message["method"]
        target = proto.target_of(message)
        if target is not None:
            headers["Mcp-Name"] = target
    if session_id:
        headers["Mcp-Session-Id"] = session_id
    return headers


async def _post(client: httpx.AsyncClient, url: str, message: dict[str, Any],
                session_id: str | None, record) -> tuple[dict[str, Any] | None, str | None]:
    record(C2S, message)
    async with client.stream("POST", url, json=message,
                             headers=_http_headers(message, session_id)) as response:
        new_session_id = response.headers.get("mcp-session-id") or session_id
        if response.status_code >= 400 and response.status_code != 202:
            body = await response.aread()
            raise ReplayError(f"server answered HTTP {response.status_code}: "
                              f"{body[:200].decode('utf-8', 'replace')}")
        if "text/event-stream" in response.headers.get("content-type", ""):
            parser = SSEParser()
            async for chunk in response.aiter_bytes():
                for event in parser.feed(chunk):
                    if not event.data.strip():
                        continue
                    record(S2C, event.data)
                    try:
                        data = json.loads(event.data)
                    except json.JSONDecodeError:
                        continue
                    if isinstance(data, dict) and data.get("id") == message.get("id"):
                        return data, new_session_id
            return None, new_session_id
        content = await response.aread()
        if not content:
            return None, new_session_id
        record(S2C, content.decode("utf-8", "replace"))
        return json.loads(content), new_session_id


async def _replay_http(session, handshake, request, record,
                       transport: httpx.AsyncBaseTransport | None = None) -> dict[str, Any]:
    url = session["target"]
    async with httpx.AsyncClient(transport=transport, timeout=TIMEOUT_S) as client:
        session_id = None
        for init in handshake:
            _, session_id = await _post(client, url, init, None, record)
            await _post(client, url, {"jsonrpc": "2.0", "method": "notifications/initialized"},
                        session_id, record)
        response, _ = await _post(client, url, request, session_id, record)
    if response is None:
        raise ReplayError("server did not answer the request")
    return response
