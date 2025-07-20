import typer
from mcp_shark.sniffer import start_sniffer

app = typer.Typer(
    help=(
        "MCP-Shark: Passive MCP traffic sniffer "
        "(WebSocket/TCP)"
    )
)


@app.command()
def sniff(
    filter: str = typer.Option(
        "tcp and host 127.0.0.1",
        help="BPF filter for scapy."
    )
):
    """
    Start sniffing MCP traffic passively on localhost.
    """
    typer.echo("[MCP-Shark] Starting passive listener...")
    start_sniffer(filter)


def main():
    app()


if __name__ == "__main__":
    main()
