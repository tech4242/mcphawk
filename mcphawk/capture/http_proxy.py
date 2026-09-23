"""Recording reverse proxy for HTTP MCP servers.

Routes:

* ``/p/<name>``            -> the upstream URL registered as ``<name>``
* ``/p/<name>/~/<path>``   -> ``<path>`` on the upstream's origin (used when a
  legacy HTTP+SSE server announces an absolute endpoint such as
  ``/messages?session_id=...``, which we rewrite to stay on the proxy)

Unlike passive sniffing this works for HTTPS upstreams and remote servers.
"""

import json
import logging
from collections.abc import AsyncIterator, Callable
from typing import Any
from urllib.parse import urljoin, urlsplit, urlunsplit

import httpx
from starlette.requests import Request
from starlette.responses import JSONResponse, Response, StreamingResponse
from starlette.routing import Route

from mcphawk.capture.http_sessions import SESSION_HEADER, HttpSessions, header
from mcphawk.capture.sse import SSEEvent, SSEParser
from mcphawk.protocol import jsonrpc
from mcphawk.store import C2S, S2C, Recorder

logger = logging.getLogger(__name__)

PROXY_PREFIX = "/p"
ROOT_MARKER = "~"

_HOP_BY_HOP = frozenset({
    "connection", "keep-alive", "proxy-authenticate", "proxy-authorization", "te",
    "trailers", "transfer-encoding", "upgrade", "host", "content-length",
    "accept-encoding", "content-encoding",
})


def _forward_headers(headers: Any) -> dict[str, str]:
    return {k: v for k, v in headers.items() if k.lower() not in _HOP_BY_HOP}


def _origin(url: str) -> str:
    parts = urlsplit(url)
    return urlunsplit((parts.scheme, parts.netloc, "", "", ""))


def _is_event_stream(headers: Any) -> bool:
    return "text/event-stream" in (header(dict(headers), "content-type") or "")


class Proxy:
    def __init__(
        self,
        upstreams: dict[str, str] | Callable[[], dict[str, str]],
        recorder: Recorder,
        transport: httpx.AsyncBaseTransport | None = None,
    ):
        self._upstreams = upstreams
        self.recorder = recorder
        self.sessions = HttpSessions(recorder, capture="proxy")
        self._client = httpx.AsyncClient(
            transport=transport, timeout=httpx.Timeout(30.0, read=None),
            follow_redirects=False)

    def upstreams(self) -> dict[str, str]:
        return self._upstreams() if callable(self._upstreams) else self._upstreams

    def routes(self) -> list[Route]:
        methods = ["GET", "POST", "DELETE", "PUT", "PATCH", "OPTIONS"]
        return [
            Route(PROXY_PREFIX + "/{name}", self.handle, methods=methods),
            Route(PROXY_PREFIX + "/{name}/{rest:path}", self.handle, methods=methods),
        ]

    async def aclose(self) -> None:
        await self._client.aclose()

    def _upstream_url(self, name: str, rest: str, query: str) -> str | None:
        base = self.upstreams().get(name)
        if base is None:
            return None
        if rest.startswith(ROOT_MARKER + "/") or rest == ROOT_MARKER:
            url = _origin(base) + "/" + rest[len(ROOT_MARKER):].lstrip("/")
        elif rest:
            url = base.rstrip("/") + "/" + rest
        else:
            url = base
        return url + ("?" + query if query else "")

    async def handle(self, request: Request) -> Response:
        name = request.path_params["name"]
        rest = request.path_params.get("rest", "")
        query = request.url.query
        url = self._upstream_url(name, rest, query)
        if url is None:
            return JSONResponse({"error": f"no upstream named {name!r}"}, status_code=404)
        upstream = self.upstreams()[name]

        body = await request.body()
        req_headers = dict(request.headers)
        session_id = None
        messages = jsonrpc.parse_frame(body.decode("utf-8", "replace")) if body else None
        if request.method == "POST" and body:
            session_id = self.sessions.for_request(
                upstream, req_headers, messages or [], name=name, query=query)
            self.recorder.record(session_id, C2S, body, headers=req_headers)

        forward = _forward_headers(request.headers)
        forward["accept-encoding"] = "identity"
        upstream_request = self._client.build_request(
            request.method, url, headers=forward, content=body)
        try:
            response = await self._client.send(upstream_request, stream=True)
        except httpx.HTTPError as exc:
            logger.warning("upstream %s failed: %s", url, exc)
            if session_id and messages:
                self._record_gateway_error(session_id, messages, str(exc))
            return JSONResponse({"error": f"upstream unreachable: {exc}"}, status_code=502)

        resp_headers = _forward_headers(response.headers)
        if session_id:
            self.sessions.bind_session_header(
                session_id, upstream, header(dict(response.headers), SESSION_HEADER))

        if _is_event_stream(response.headers):
            if session_id is None:
                session_id = self.sessions.for_sse_stream(upstream, req_headers, name)
            return StreamingResponse(
                self._stream(response, upstream, name, session_id),
                status_code=response.status_code, headers=resp_headers)

        content = await response.aread()
        await response.aclose()
        if session_id and content and response.status_code != 202:
            self.recorder.record(session_id, S2C, content)
        return Response(content, status_code=response.status_code, headers=resp_headers)

    def _record_gateway_error(self, session_id: str, messages: list[dict[str, Any]],
                              reason: str) -> None:
        for msg in messages:
            if jsonrpc.classify(msg) == jsonrpc.REQUEST:
                self.recorder.record(session_id, S2C, json.dumps({
                    "jsonrpc": "2.0", "id": msg["id"],
                    "error": {"code": -32000,
                              "message": f"mcphawk proxy: upstream unreachable: {reason}"}}))

    async def _stream(self, response: httpx.Response, upstream: str, name: str,
                      session_id: str | None) -> AsyncIterator[bytes]:
        parser = SSEParser()
        # A stream of a known session is passed through byte for byte. An
        # unknown GET stream may be legacy HTTP+SSE, whose endpoint event must
        # be rewritten, so its events are re-serialized instead.
        passthrough = session_id is not None
        try:
            async for chunk in response.aiter_raw():
                events = parser.feed(chunk)
                for event in events:
                    if event.event == "endpoint" and session_id is None:
                        endpoint = urljoin(upstream, event.data)
                        session_id = self.sessions.open_legacy_sse(upstream, endpoint, name)
                    elif session_id and event.data.strip():
                        self.recorder.record(session_id, S2C, event.data)
                if passthrough:
                    yield chunk
                else:
                    for event in events:
                        yield self._serialize(event, name, upstream)
        finally:
            await response.aclose()

    @staticmethod
    def _serialize(event: SSEEvent, name: str, upstream: str) -> bytes:
        data = event.data
        if event.event == "endpoint":
            endpoint = urlsplit(urljoin(upstream, data))
            if _origin(urlunsplit(endpoint)) == _origin(upstream):
                path = endpoint.path + ("?" + endpoint.query if endpoint.query else "")
                data = f"{PROXY_PREFIX}/{name}/{ROOT_MARKER}{path}"
        lines = [f"event: {event.event}"]
        if event.id is not None:
            lines.append(f"id: {event.id}")
        lines.extend(f"data: {line}" for line in data.split("\n"))
        return ("\n".join(lines) + "\n\n").encode()
