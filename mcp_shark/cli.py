import asyncio
import webbrowser
import typer
from .sniffer import start_sniffer
from .web.server import app
import uvicorn

app_cli = typer.Typer(
    help="MCP-Shark: Passive MCP traffic sniffer (WebSocket/TCP)."
)


@app_cli.command()
def sniff(
    filter: str = typer.Option(
        "tcp and host 127.0.0.1",
        help="BPF filter for Scapy."
    ),
):
    """
    Start sniffing MCP traffic passively on localhost.
    """
    typer.echo("[MCP-Shark] Starting passive listener...")
    start_sniffer(filter)


@app_cli.command()
def web(
    filter: str = typer.Option(
        "tcp and host 127.0.0.1",
        help="BPF filter for Scapy."
    ),
    host: str = typer.Option(
        "127.0.0.1",
        help="Web dashboard host."
    ),
    port: int = typer.Option(
        8000,
        help="Web dashboard port."
    ),
    open_browser: bool = typer.Option(
        True,
        help="Open the web dashboard in the browser automatically."
    ),
):
    """
    Start MCP-Shark sniffer and web dashboard.
    """
    typer.echo(
        f"[MCP-Shark] Starting sniffer and dashboard on "
        f"http://{host}:{port}"
    )

    async def run_all() -> None:
        if open_browser:
            # Open the browser slightly after server startup
            loop = asyncio.get_event_loop()
            loop.call_later(
                1.5, lambda: webbrowser.open(f"http://{host}:{port}")
            )

        loop = asyncio.get_event_loop()
        loop.run_in_executor(None, start_sniffer, filter)
        config = uvicorn.Config(
            app, host=host, port=port, log_level="info"
        )
        server = uvicorn.Server(config)
        await server.serve()

    asyncio.run(run_all())


def main() -> None:
    """Entry point for the MCP-Shark CLI."""
    app_cli()


if __name__ == "__main__":
    main()
