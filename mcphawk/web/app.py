"""``mcphawk up``: web UI, JSON API, live updates, HTTP proxy and the MCPHawk
MCP endpoint, all on one local port."""

import asyncio
import contextlib
import logging
from collections.abc import Callable
from pathlib import Path
from typing import Annotated, Any

from fastapi import (
    Body,
    FastAPI,
    HTTPException,
    Request,
    WebSocket,
    WebSocketDisconnect,
)
from fastapi import Query as Param
from fastapi.responses import FileResponse, JSONResponse, PlainTextResponse
from fastapi.staticfiles import StaticFiles
from starlette.routing import Route

from mcphawk import links
from mcphawk import runs as agent_runs
from mcphawk.analysis import cost, drift, lint, problems
from mcphawk.capture.http_proxy import Proxy
from mcphawk.install import installer
from mcphawk.otel import prometheus
from mcphawk.query import Query
from mcphawk.replay import ReplayError, replay
from mcphawk.store import Recorder

logger = logging.getLogger(__name__)

STATIC_DIR = Path(__file__).parent / "static"
LIVE_POLL_S = 0.5
SEVERITIES = ("error", "warning", "info")
GUARD_HEADER = "x-mcphawk"
LOCAL_HOSTS = frozenset({"127.0.0.1", "localhost", "[::1]"})


def _is_local_host(host_header: str) -> bool:
    host = host_header.rsplit(":", 1)[0] if not host_header.endswith("]") else host_header
    return host in LOCAL_HOSTS


def create_app(
    db: Path | str | None = None,
    *,
    upstreams: Callable[[], dict[str, str]] | None = None,
    with_mcp: bool = True,
    static_dir: Path | None = STATIC_DIR,
    mask: bool = True,
    telemetry: Any = None,
) -> FastAPI:
    """``telemetry`` is an optional ``mcphawk.otel.exporter.TelemetryExporter``."""
    q = Query(db)
    recorder = Recorder(db, mask=mask)
    proxy = Proxy(upstreams or installer.load_registry, recorder)
    mcp_http = None
    if with_mcp:
        from mcphawk.mcp_server import build_server

        mcp_http = build_server(db).streamable_http_app(streamable_http_path="/mcp")

    @contextlib.asynccontextmanager
    async def lifespan(app: FastAPI):
        async with contextlib.AsyncExitStack() as stack:
            if mcp_http is not None:
                await stack.enter_async_context(mcp_http.router.lifespan_context(mcp_http))
            exporting = asyncio.create_task(_export_loop()) if telemetry else None
            yield
            if exporting:
                exporting.cancel()
                with contextlib.suppress(asyncio.CancelledError):
                    await exporting
                await asyncio.to_thread(telemetry.poll)
                await asyncio.to_thread(telemetry.shutdown)
            await proxy.aclose()
            q.close()
            recorder.close()

    async def _export_loop() -> None:
        from mcphawk.otel.exporter import POLL_S

        while True:
            try:
                await asyncio.to_thread(telemetry.poll)
            except Exception:  # keep exporting even if one batch fails
                logger.exception("OpenTelemetry export failed")
            await asyncio.sleep(POLL_S)

    app = FastAPI(title="MCPHawk", lifespan=lifespan, docs_url="/api/docs",
                  openapi_url="/api/openapi.json")
    app.state.query = q
    app.state.recorder = recorder
    app.state.proxy = proxy

    @app.middleware("http")
    async def guard_mutations(request: Request, call_next):
        """State-changing API calls must come from our own UI on localhost.

        The custom header forces a CORS preflight (which we never grant), and
        the Host check stops DNS-rebinding pages from reaching the API.
        """
        mutating = request.method not in ("GET", "HEAD")
        if request.url.path.startswith("/api/") and mutating and (
                request.headers.get(GUARD_HEADER) != "1"
                or not _is_local_host(request.headers.get("host", ""))):
            return JSONResponse({"detail": "forbidden"}, status_code=403)
        return await call_next(request)

    def need(value: Any, what: str) -> Any:
        if value is None:
            raise HTTPException(404, f"{what} not found")
        return value

    # -- read API ---------------------------------------------------------

    @app.get("/metrics", include_in_schema=False)
    def metrics() -> PlainTextResponse:
        """Prometheus scrape endpoint (same names as the OTLP metrics)."""
        return PlainTextResponse(prometheus.render(q), media_type=prometheus.CONTENT_TYPE)

    @app.get("/api/stats")
    def stats() -> dict[str, Any]:
        return {**q.stats(), "proxies": proxy.upstreams(), "base_url": links.base_url()}

    @app.get("/api/runs")
    def runs(limit: int = 50) -> list[dict[str, Any]]:
        return agent_runs.list_runs(q, limit=limit)

    @app.get("/api/runs/{run_key:path}")
    def run(run_key: str) -> dict[str, Any]:
        return need(agent_runs.get_run(q, run_key), "run")

    @app.get("/api/sessions")
    def sessions(run_key: str | None = None, server: str | None = None,
                 limit: int = 100) -> list[dict[str, Any]]:
        if run_key:
            return agent_runs.resolve_scope(q, run_key=run_key).sessions
        return q.list_sessions(server=server, limit=limit)

    @app.get("/api/sessions/{session_id}")
    def session(session_id: str) -> dict[str, Any]:
        return need(q.get_session(session_id), "session")

    @app.get("/api/sessions/{session_id}/messages")
    def session_messages(session_id: str, after_id: int = 0,
                         limit: int = 500) -> list[dict[str, Any]]:
        return q.messages(session_id=session_id, after_id=after_id, limit=limit,
                          include_hidden=True)

    @app.get("/api/sessions/{session_id}/lint")
    def session_lint(session_id: str) -> list[dict[str, Any]]:
        need(q.get_session_header(session_id), "session")
        return lint.lint_session(q, session_id)

    @app.get("/api/exchanges")
    def exchanges(session_id: str | None = None, status: str | None = None,
                  method: str | None = None, target: str | None = None,
                  q_: Annotated[str | None, Param(alias="q")] = None,
                  limit: int = 500) -> list[dict[str, Any]]:
        return q.exchanges(session_id=session_id, status=status, method=method,
                           target=target, text=q_, limit=limit)

    @app.get("/api/exchanges/{exchange_id}")
    def exchange(exchange_id: int) -> dict[str, Any]:
        return need(q.get_exchange(exchange_id), "exchange")

    @app.get("/api/messages/{message_id}")
    def message(message_id: int) -> dict[str, Any]:
        return need(q.get_message(message_id), "message")

    @app.get("/api/problems")
    def problem_list(session_id: str | None = None, run_key: str | None = None,
                     server: str | None = None, min_severity: str = "warning",
                     limit: int = 200) -> dict[str, Any]:
        if min_severity not in SEVERITIES:
            raise HTTPException(422, "min_severity must be error, warning or info")
        return problems.find_problems(q, session_id=session_id, run_key=run_key,
                                      server=server, min_severity=min_severity, limit=limit)

    @app.get("/api/cost")
    def context_cost(session_id: str | None = None, run_key: str | None = None,
                     server: str | None = None) -> dict[str, Any]:
        return cost.context_cost(q, session_id=session_id, run_key=run_key, server=server)

    @app.get("/api/compare")
    def compare(before: str, after: str) -> dict[str, Any]:
        report = drift.compare_sessions(q, before, after)
        if "error" in report:
            raise HTTPException(404, report["error"])
        return report

    @app.get("/api/setup")
    def setup() -> dict[str, Any]:
        """Dry-run of ``mcphawk install``: what is and is not routed through us."""
        changes = installer.plan(include_http=True, registry=dict(installer.load_registry()))
        return {"servers": [{
            "client": c.table.client, "scope": c.table.scope, "file": str(c.table.path),
            "server": c.server,
            "status": ("would wrap" if c.action == installer.WRAP
                       else "would proxy" if c.action == installer.PROXY else c.reason),
        } for c in changes]}

    @app.post("/api/exchanges/{exchange_id}/replay")
    async def replay_exchange(
        exchange_id: int,
        params: Annotated[dict[str, Any] | None, Body(embed=True)] = None,
    ) -> dict[str, Any]:
        try:
            return await replay(q, recorder, exchange_id, params)
        except ReplayError as exc:
            raise HTTPException(409, str(exc)) from None

    @app.delete("/api/data")
    def clear(confirm: bool = False) -> dict[str, Any]:
        if not confirm:
            raise HTTPException(400, "pass confirm=true to delete all captured traffic")
        q.clear()
        return {"cleared": True}

    # -- live updates -----------------------------------------------------

    @app.websocket("/api/live")
    async def live(ws: WebSocket) -> None:
        """Pushes new message summaries; works across processes by tailing the DB."""
        await ws.accept()
        last = q.latest_message_id()
        try:
            while True:
                fresh = await asyncio.to_thread(q.messages, after_id=last, limit=500)
                if fresh:
                    last = fresh[-1]["id"]
                    await ws.send_json({"type": "messages", "items": fresh})
                with contextlib.suppress(asyncio.TimeoutError):
                    await asyncio.wait_for(ws.receive_text(), timeout=LIVE_POLL_S)
        except (WebSocketDisconnect, RuntimeError):
            return

    # -- proxy and MCP ----------------------------------------------------

    for route in proxy.routes():
        app.router.routes.append(route)
    if mcp_http is not None:
        for route in mcp_http.routes:
            if isinstance(route, Route):
                app.router.routes.append(route)

    # -- single page app --------------------------------------------------

    index = static_dir / "index.html" if static_dir else None
    if index and index.exists():
        assets = static_dir / "assets"
        if assets.exists():
            app.mount("/assets", StaticFiles(directory=assets), name="assets")

        @app.get("/{path:path}", include_in_schema=False)
        def spa(path: str) -> FileResponse:
            if path == "mcp" or path.startswith(("api/", "p/", "mcp/")):
                raise HTTPException(404)
            candidate = (static_dir / path).resolve()
            if path and candidate.is_file() and static_dir.resolve() in candidate.parents:
                return FileResponse(candidate)
            return FileResponse(index)
    else:
        @app.get("/", include_in_schema=False)
        def no_ui() -> JSONResponse:
            return JSONResponse({"message": "MCPHawk API is running; the web UI is not built.",
                                 "api": "/api/docs"})

    return app
