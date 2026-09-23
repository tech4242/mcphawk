"""The real OTLP/HTTP exporters against a fake collector."""

import socket
import threading
import time

import uvicorn
from opentelemetry.proto.collector.logs.v1 import logs_service_pb2
from opentelemetry.proto.collector.metrics.v1 import metrics_service_pb2
from opentelemetry.proto.collector.trace.v1 import trace_service_pb2
from starlette.applications import Starlette
from starlette.requests import Request
from starlette.responses import Response
from starlette.routing import Route

from mcphawk.otel.exporter import TelemetryExporter
from tests.traffic import Clock, legacy_session

received: dict[str, list[bytes]] = {"traces": [], "metrics": [], "logs": []}


async def collect(request: Request) -> Response:
    received[request.path_params["signal"]].append(await request.body())
    return Response(status_code=200)


def _serve():
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        port = sock.getsockname()[1]

    class Server(uvicorn.Server):
        def install_signal_handlers(self):  # pragma: no cover
            pass

    app = Starlette(routes=[Route("/v1/{signal}", collect, methods=["POST"])])
    server = Server(uvicorn.Config(app, host="127.0.0.1", port=port, log_level="error"))
    threading.Thread(target=server.run, daemon=True).start()
    while not server.started:
        time.sleep(0.02)
    return server, port


def test_all_three_signals_reach_an_otlp_collector(recorder, query, monkeypatch):
    server, port = _serve()
    monkeypatch.setenv("OTEL_EXPORTER_OTLP_ENDPOINT", f"http://127.0.0.1:{port}")
    try:
        exporter = TelemetryExporter.from_env(query)
        legacy_session(recorder, Clock(time.time()), client_app="claude")
        exporter.poll()
        exporter.shutdown()
    finally:
        server.should_exit = True

    spans = [span for body in received["traces"]
             for rs in trace_service_pb2.ExportTraceServiceRequest.FromString(body).resource_spans
             for ss in rs.scope_spans for span in ss.spans]
    assert "tools/call get_weather" in {s.name for s in spans}
    resource = trace_service_pb2.ExportTraceServiceRequest.FromString(
        received["traces"][0]).resource_spans[0].resource
    assert {a.key: a.value.string_value for a in resource.attributes}["service.name"] == (
        "mcphawk")

    metric_names = {m.name for body in received["metrics"]
                    for rm in metrics_service_pb2.ExportMetricsServiceRequest.FromString(
                        body).resource_metrics
                    for sm in rm.scope_metrics for m in sm.metrics}
    assert {"mcp.client.operation.duration", "mcphawk.tool.result.tokens",
            "mcphawk.tool.definition.tokens"} <= metric_names

    records = [r for body in received["logs"]
               for rl in logs_service_pb2.ExportLogsServiceRequest.FromString(body).resource_logs
               for sl in rl.scope_logs for r in sl.log_records]
    assert len(records) == 11
    assert any(r.severity_text == "ERROR" and r.span_id for r in records)
