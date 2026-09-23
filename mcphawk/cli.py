"""MCPHawk command line."""

import asyncio
import logging
import os
import sys
import threading
import webbrowser
from pathlib import Path

import typer

from mcphawk import __version__
from mcphawk.install import clients as cl
from mcphawk.install import installer
from mcphawk.paths import db_path

app = typer.Typer(
    help="MCPHawk: DevTools for MCP. See what your MCP clients and servers really say.",
    no_args_is_help=False,
    add_completion=False,
)

DEFAULT_PORT = installer.DEFAULT_PORT


def _log_to_stderr(debug: bool) -> None:
    logging.basicConfig(
        stream=sys.stderr, level=logging.DEBUG if debug else logging.WARNING,
        format="mcphawk: %(message)s")


@app.callback(invoke_without_command=True)
def main(
    ctx: typer.Context,
    version: bool = typer.Option(False, "--version", help="Show the version and exit."),
) -> None:
    """With no command, starts the web UI (same as ``mcphawk up``)."""
    if version:
        typer.echo(f"mcphawk {__version__}")
        raise typer.Exit()
    if ctx.invoked_subcommand is None:
        _serve()


def _sniff_filter(ports: list[int] | None, custom: str | None, auto: bool) -> str | None:
    if custom:
        return custom
    if ports:
        return " or ".join(f"tcp port {p}" for p in ports)
    return "tcp" if auto else None


def _start_sniffer(filter_expr: str, interface: str | None, excluded: set[int],
                   mask: bool) -> None:  # pragma: no cover - needs capture privileges
    from mcphawk.capture.sniff import run_sniffer
    from mcphawk.store import Recorder

    def target() -> None:
        try:
            run_sniffer(filter_expr, Recorder(mask=mask), interface, excluded)
        except PermissionError:
            typer.echo("mcphawk: packet capture needs root (try sudo)", err=True)

    threading.Thread(target=target, daemon=True, name="sniffer").start()


@app.command()
def up(
    port: int = typer.Option(DEFAULT_PORT, "--port", help="Port for UI, API, proxy and /mcp."),
    host: str = typer.Option("127.0.0.1", "--host", help="Interface to bind."),
    sniff: list[int] = typer.Option(None, "--sniff", help="Also sniff this TCP port (sudo)."),
    sniff_filter: str = typer.Option(None, "--sniff-filter", help="Custom BPF filter (sudo)."),
    no_mcp: bool = typer.Option(False, "--no-mcp", help="Do not serve the MCPHawk MCP endpoint."),
    no_mask: bool = typer.Option(False, "--no-mask", help="Store secrets unmasked."),
    open_browser: bool = typer.Option(False, "--open", help="Open the UI in a browser."),
    debug: bool = typer.Option(False, "--debug", help="Verbose logging."),
) -> None:
    """Start the web UI (plus proxy and MCP endpoint) on one local port."""
    _serve(port, host, sniff, sniff_filter, no_mcp, no_mask, open_browser, debug)


@app.command(hidden=True)
def web(port: int = typer.Option(DEFAULT_PORT, "--web-port", "--port")) -> None:
    """Renamed to `mcphawk up` in 1.0."""
    typer.echo("`mcphawk web` is now `mcphawk up`; starting it for you.", err=True)
    _serve(port)


def _serve(port: int = DEFAULT_PORT, host: str = "127.0.0.1", sniff: list[int] | None = None,
           sniff_filter: str | None = None, no_mcp: bool = False, no_mask: bool = False,
           open_browser: bool = False, debug: bool = False) -> None:
    import uvicorn

    from mcphawk.web.app import create_app

    _log_to_stderr(debug)
    url = f"http://{'127.0.0.1' if host in ('0.0.0.0', '::') else host}:{port}"
    os.environ["MCPHAWK_URL"] = url
    filter_expr = _sniff_filter(sniff, sniff_filter, False)
    if filter_expr:
        _start_sniffer(filter_expr, None, {port}, not no_mask)
    typer.echo(f"MCPHawk {__version__}  ->  {url}")
    typer.echo(f"  database  {db_path()}")
    if not no_mcp:
        typer.echo(f"  MCP       {url}/mcp   (or: claude mcp add mcphawk -- mcphawk mcp)")
    proxies = installer.load_registry()
    if proxies:
        typer.echo(f"  proxying  {', '.join(sorted(proxies))}")
    if open_browser:  # pragma: no cover
        threading.Timer(1.0, webbrowser.open, (url,)).start()
    uvicorn.run(create_app(with_mcp=not no_mcp, mask=not no_mask), host=host, port=port,
                log_level="debug" if debug else "warning")


@app.command(context_settings={"allow_extra_args": True, "allow_interspersed_args": False,
                               "ignore_unknown_options": True})
def wrap(
    ctx: typer.Context,
    name: str = typer.Option(None, "--name", help="Server name shown in MCPHawk."),
    no_mask: bool = typer.Option(False, "--no-mask", help="Store secrets unmasked."),
    debug: bool = typer.Option(False, "--debug", help="Log to stderr."),
) -> None:
    """Run an stdio MCP server and record its traffic: mcphawk wrap -- <command...>"""
    from mcphawk.capture.stdio import run_wrap

    command = list(ctx.args)
    if command and command[0] == "--":
        command = command[1:]
    if not command:
        typer.echo("usage: mcphawk wrap [--name NAME] -- <server command> [args...]", err=True)
        raise typer.Exit(2)
    _log_to_stderr(debug)
    raise typer.Exit(run_wrap(command, name=name, mask=not no_mask))


@app.command()
def proxy(
    target: str = typer.Option(..., "--target", help="Upstream MCP server URL."),
    name: str = typer.Option("server", "--name", help="Name shown in MCPHawk."),
    port: int = typer.Option(8485, "--port", help="Local port to listen on."),
    no_mask: bool = typer.Option(False, "--no-mask", help="Store secrets unmasked."),
) -> None:
    """Record one HTTP MCP server without running the UI."""
    import uvicorn
    from starlette.applications import Starlette

    from mcphawk.capture.http_proxy import Proxy
    from mcphawk.store import Recorder

    recorder = Recorder(mask=not no_mask)
    proxy_ = Proxy({name: target}, recorder)
    typer.echo(f"Point your client at: http://127.0.0.1:{port}/p/{name}")
    uvicorn.run(Starlette(routes=proxy_.routes()), host="127.0.0.1", port=port,
                log_level="warning")


def _tilde(text: str) -> str:
    """Show paths under the home directory as ~/..."""
    home = str(Path.home())
    return text.replace(home + os.sep, "~" + os.sep) if home != os.sep else text


_ACTION_TEXT = {
    installer.WRAP: "recorded (stdio wrapper)",
    installer.PROXY: "recorded (HTTP proxy)",
    installer.UNWRAP: "restored",
    installer.UNPROXY: "restored",
}


def _print_plan(changes: list[installer.Change]) -> None:
    if not changes:
        typer.echo("No MCP client configurations found.")
        return
    current = None
    for change in changes:
        label = change.table.label()
        if label != current:
            typer.echo(f"\n{label}  {_tilde(str(change.table.path))}")
            current = label
        if change.after is not None:
            typer.echo(f"  + {change.server:<24} {_ACTION_TEXT[change.action]}")
        else:
            typer.echo(f"    {change.server:<24} skipped: {change.reason}")


def _run_plan(uninstall: bool, clients: list[str] | None, project: Path | None,
              include_http: bool, force_http: bool, port: int, dry_run: bool,
              yes: bool) -> None:
    chosen = tuple(clients) if clients else cl.ALL_CLIENTS
    unknown = [c for c in chosen if c not in cl.ALL_CLIENTS]
    if unknown:
        typer.echo(f"unknown client(s): {', '.join(unknown)}; "
                   f"choose from {', '.join(cl.ALL_CLIENTS)}", err=True)
        raise typer.Exit(2)
    registry = installer.load_registry()
    changes = installer.plan(uninstall=uninstall, clients=chosen, project=project,
                             include_http=include_http, force_http=force_http, port=port,
                             registry=registry)
    _print_plan(changes)
    effective = [c for c in changes if c.after is not None]
    if not effective:
        typer.echo("\nNothing to change.")
        return
    verb = "restored" if uninstall else "recorded"
    skipped = len(changes) - len(effective)
    summary = f"{len(effective)} server(s) will be {verb}" + (
        f", {skipped} skipped" if skipped else "")
    if dry_run:
        typer.echo(f"\n{summary}. Dry run: nothing was written.")
        return
    if not yes and not typer.confirm(f"\n{summary}. Continue?", default=True):
        raise typer.Exit(1)
    typer.echo("")
    for note in installer.apply(changes, registry):
        typer.echo(_tilde(note))
    typer.echo("\nRestart your MCP clients to pick up the change.")
    if not uninstall and any(c.action == installer.PROXY for c in effective):
        typer.echo("HTTP servers now go through MCPHawk: keep `mcphawk up` running.")


@app.command()
def install(
    client: list[str] = typer.Option(None, "--client", help="Only these clients."),
    project: Path = typer.Option(None, "--project", help="Also edit this project's configs."),
    include_http: bool = typer.Option(False, "--include-http",
                                      help="Route local/header-auth HTTP servers via the proxy."),
    force_http: bool = typer.Option(False, "--force-http",
                                    help="Proxy every HTTP server, even likely-OAuth ones."),
    port: int = typer.Option(DEFAULT_PORT, "--port", help="Port `mcphawk up` listens on."),
    dry_run: bool = typer.Option(False, "--dry-run", help="Show the plan only."),
    yes: bool = typer.Option(False, "--yes", "-y", help="Do not ask for confirmation."),
) -> None:
    """Route every MCP server of your clients through MCPHawk (with backups)."""
    _run_plan(False, client, project, include_http, force_http, port, dry_run, yes)


@app.command()
def uninstall(
    client: list[str] = typer.Option(None, "--client", help="Only these clients."),
    project: Path = typer.Option(None, "--project", help="Also edit this project's configs."),
    port: int = typer.Option(DEFAULT_PORT, "--port", help="Port used at install time."),
    dry_run: bool = typer.Option(False, "--dry-run", help="Show the plan only."),
    yes: bool = typer.Option(False, "--yes", "-y", help="Do not ask for confirmation."),
) -> None:
    """Undo `mcphawk install`, restoring the original server entries."""
    _run_plan(True, client, project, False, False, port, dry_run, yes)


@app.command()
def status() -> None:
    """Show where data lives, what was captured and which servers are routed."""
    from mcphawk.query import Query

    q = Query()
    stats = q.stats()
    q.close()
    typer.echo(f"database   {_tilde(str(db_path()))}")
    typer.echo(f"captured   {stats.get('sessions', 0)} sessions, "
               f"{stats.get('exchanges', 0)} calls, {stats.get('errors', 0)} errors")
    routed = [c for c in installer.plan(uninstall=True) if c.after is not None]
    typer.echo(f"routed     {len(routed)} server(s) through MCPHawk")
    for change in routed:
        typer.echo(f"  {change.table.label():<32} {change.server}")


@app.command()
def mcp(
    transport: str = typer.Option("stdio", "--transport", help="stdio or http."),
    port: int = typer.Option(8765, "--port", help="Port for --transport http."),
) -> None:
    """Serve MCPHawk's own MCP server so agents can query captured traffic."""
    from mcphawk.mcp_server import build_server

    _log_to_stderr(False)
    server = build_server()
    if transport == "stdio":
        asyncio.run(server.run_stdio_async())
    elif transport == "http":  # pragma: no cover - blocking server
        import uvicorn

        uvicorn.run(server.streamable_http_app(), host="127.0.0.1", port=port,
                    log_level="warning")
    else:
        typer.echo("transport must be stdio or http", err=True)
        raise typer.Exit(2)


@app.command()
def sniff(
    port: list[int] = typer.Option(None, "--port", "-p", help="TCP port(s) to watch."),
    filter_: str = typer.Option(None, "--filter", "-f", help="Custom BPF filter."),
    auto_detect: bool = typer.Option(False, "--auto-detect", "-a",
                                     help="Watch all TCP traffic for MCP."),
    interface: str = typer.Option(None, "--interface", "-i", help="Capture interface."),
    no_mask: bool = typer.Option(False, "--no-mask", help="Store secrets unmasked."),
) -> None:
    """Passively capture plaintext HTTP/TCP MCP traffic (needs sudo)."""
    filter_expr = _sniff_filter(port, filter_, auto_detect)
    if not filter_expr:
        typer.echo("choose --port, --filter or --auto-detect", err=True)
        raise typer.Exit(2)
    from mcphawk.capture.sniff import run_sniffer
    from mcphawk.store import Recorder

    typer.echo(f"sniffing '{filter_expr}' -> {db_path()}  (Ctrl+C to stop)")
    try:  # pragma: no cover - needs capture privileges
        run_sniffer(filter_expr, Recorder(mask=not no_mask), interface)
    except PermissionError:
        typer.echo("packet capture needs root: try `sudo mcphawk sniff ...`", err=True)
        raise typer.Exit(1) from None
    except KeyboardInterrupt:  # pragma: no cover
        pass


@app.command()
def clear(yes: bool = typer.Option(False, "--yes", "-y", help="Do not ask.")) -> None:
    """Delete all captured traffic."""
    from mcphawk.query import Query

    if not yes and not typer.confirm(f"Delete everything in {db_path()}?", default=False):
        raise typer.Exit(1)
    q = Query()
    q.clear()
    q.close()
    typer.echo("cleared")

