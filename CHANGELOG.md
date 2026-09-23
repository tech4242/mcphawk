# Changelog

## 1.0.0

A rewrite around the 2026-07-28 MCP specification: MCPHawk is now DevTools for MCP,
for people and for agents.

### Added
- `mcphawk install` / `uninstall` for Claude Desktop, Claude Code, Cursor and VS Code,
  with backups and structural undo; `--include-http` routes local and header-authenticated
  HTTP servers through the proxy.
- Recording reverse proxy for Streamable HTTP and legacy HTTP+SSE, including HTTPS and
  remote servers, served by `mcphawk up`.
- New web UI: run timeline across servers, call inspector with rendered results, context
  cost, problems, session comparison, replay and a setup page.
- Context cost analysis: tokens per tool definition and result, unused tools, heaviest
  results.
- Problem detection: errors, tool errors, unanswered and slow calls, repeated identical
  calls, and spec lint per negotiated protocol version.
- Replay of client requests (optionally edited) over stdio and Streamable HTTP.
- MCPHawk MCP server with six read-only tools (`list_sessions`, `get_session`,
  `get_exchange`, `find_problems`, `context_cost`, `compare_sessions`) returning capped
  summaries with deep links into the UI.
- Full support for both protocol eras: stateless 2026-07-28 (`_meta` identity,
  `server/discover`, multi round-trip requests, `Mcp-Method`/`Mcp-Name`) and the
  2024-11-05 to 2025-11-25 handshake era.
- Secret masking before anything is stored (`--no-mask` to opt out).
- Sessions are grouped into runs by the client process that launched them.

### Changed
- The capture database lives in `~/.mcphawk/mcphawk.db` (override with `MCPHAWK_DB`)
  with a new schema of sessions, exchanges and messages. Captures from 0.x are not migrated.
- `mcphawk web` is now `mcphawk up` (the old name still works) and runs the UI, API,
  proxy and `/mcp` on one port, 8484 by default.
- `mcphawk wrap` forwards raw bytes before recording and preserves the server's exit code;
  use `mcphawk wrap --name NAME -- <command>`. The 0.x form `mcphawk wrap <command>` still works.
- Rewritten passive sniffer with TCP sequence ordering and an incremental HTTP/1.x and SSE
  parser.
- Requires MCP Python SDK 2.2+.

### Removed
- The terminal UI and the 0.x MCP tools (`query_traffic`, `search_traffic`, `get_stats`,
  `list_methods`).
