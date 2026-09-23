# AGENTS.md

MCPHawk is DevTools for MCP: it records real traffic between MCP clients and servers
(stdio wrapper, HTTP proxy, passive sniffer), stores it in SQLite, and serves a web UI plus
its own MCP server over the same data. Targets MCP spec 2026-07-28 and still supports the
older `initialize` handshake era.

## Rules

- Use the local venv (`.venv/bin/python`) and Makefile targets when they exist.
- Add dependencies to `requirements.txt` / `requirements-dev.txt` and `pyproject.toml`;
  never `pip install` ad hoc.
- Before finishing: `make lint` and `make test`. Coverage must stay above 85%
  (`make coverage` fails below it).
- New tests: `tests/unit/` for isolated functions, `tests/integration/<area>/` for anything
  touching the DB, processes, network or HTTP. Build traffic with `tests/traffic.py`.
- Follow the MCP spec and the official SDK instead of inventing custom protocol behaviour.
- Write PEP 8 from the start (ruff, line length 88, Python 3.10+).

## Layout

```
capture/  -> store/recorder.py -> SQLite -> query.py + analysis/ -> web/app.py, mcp_server.py
```

- `protocol/`: JSON-RPC framing, MCP semantics for both eras, secret masking, token estimates
- `store/recorder.py`: request/response pairing, multi round-trip chains, client/server identity
- `query.py`: the one read layer; the web API and the MCP server must not query SQL themselves
- `runs.py`: agent runs, computed at read time (client group, split at 5 min idle gaps).
  `sessions.client_key` stores only which client process a session belongs to
- `install/`: client config locations and install/uninstall
- `frontend/`: Vue 3 app, built into `mcphawk/web/static` (committed)

## Commands

```bash
make install        # deps + editable install + frontend deps
make test           # or test-unit / test-integration / test-e2e ...
make dev            # mcphawk up on :8484 + Vite on :5173
make build-frontend # then commit mcphawk/web/static; CI fails if it is stale
make demo           # demo traffic from three SDK servers
```

## Gotchas

- MCP SDK 2.x: `FastMCP` is now `mcp.server.mcpserver.MCPServer`; the client is
  `mcp.client.client.Client`.
- The SDK's stdio client gives child processes a filtered environment. Pass `env=` when
  spawning `mcphawk wrap` in tests or examples, or data lands in `~/.mcphawk` instead of
  `MCPHAWK_DB`.
- Tests isolate `MCPHAWK_HOME` / `MCPHAWK_DB` in `tests/conftest.py`; never point anything
  at the real `~/.mcphawk`.
- Async fixtures must not hold an SDK `Client` open across yield (anyio cancel scopes);
  open the client inside the test.
- The stdio shim forwards bytes before recording them, and its two pump threads race: a
  response can be recorded before its request. The recorder pairs these; keep it that way.
- Mutating API routes need the `X-MCPHawk: 1` header and a localhost `Host` (CSRF and DNS
  rebinding guard). The SDK's `/mcp` endpoint also rejects non-localhost hosts, so use
  `base_url="http://127.0.0.1:8484"` with `TestClient`.
- Secrets are masked before storage. Replay refuses requests or commands that still contain
  the mask.
- Remote HTTP servers without static headers are assumed to use OAuth and are not proxied by
  default: their tokens are bound to the server URL.
- Claude Code retitles its process with its version number; `capture/process.py` falls back
  to `argv[0]` for client names.
