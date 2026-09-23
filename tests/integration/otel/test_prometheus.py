from fastapi.testclient import TestClient

from mcphawk.otel import prometheus
from mcphawk.web.app import create_app
from tests.traffic import Clock, legacy_session, modern_session


def test_render_histograms_and_gauges(recorder, query):
    legacy_session(recorder, Clock(), client_app="claude")
    text = prometheus.render(query)
    assert "# TYPE mcp_client_operation_duration_seconds histogram" in text
    ok = ('mcp_client_operation_duration_seconds_count{gen_ai_tool_name="get_weather",'
          'mcp_method_name="tools/call",mcp_protocol_version="2025-06-18",'
          'mcphawk_client_name="Claude Code",mcphawk_server_name="weather"} 1')
    assert ok in text
    assert 'error_type="tool_error"' in text
    assert 'error_type="-32602"' in text
    assert ',le="0.5"} 1' in text  # the 250 ms call lands in the 0.5 s bucket
    assert ',le="0.2"} 0' in text
    assert 'le="+Inf"' in text
    assert "mcphawk_tool_result_tokens_count{" in text
    assert ('mcphawk_tool_definition_tokens{gen_ai_tool_name="search",'
            'mcphawk_server_name="weather"}') in text


def test_render_escapes_and_empty(recorder, query):
    assert "mcp_client_operation_duration_seconds_count" not in prometheus.render(query)
    modern_session(recorder, name='we"ird\\name')
    assert 'mcphawk_server_name="we\\"ird\\\\name"' in prometheus.render(query)
    assert prometheus._escape("a\nb") == "a\\nb"
    assert prometheus._number(0.25) == "0.25"
    assert prometheus._number(2.0) == "2"


def test_metrics_route(db, recorder):
    legacy_session(recorder)
    app = create_app(db, upstreams=dict, with_mcp=False, static_dir=None)
    with TestClient(app) as client:
        response = client.get("/metrics")
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/plain; version=0.0.4")
    assert "mcp_client_operation_duration_seconds_bucket" in response.text


def test_app_runs_the_export_loop(db, monkeypatch):
    import asyncio

    from mcphawk.otel import exporter

    monkeypatch.setattr(exporter, "POLL_S", 0.01)

    class FakeTelemetry:
        def __init__(self):
            self.polls = 0
            self.closed = False

        def poll(self):
            self.polls += 1
            if self.polls == 2:
                raise RuntimeError("collector down")  # must not stop the loop

        def shutdown(self):
            self.closed = True

    fake = FakeTelemetry()
    app = create_app(db, upstreams=dict, with_mcp=False, static_dir=None, telemetry=fake)
    with TestClient(app):
        asyncio.run(asyncio.sleep(0.1))
    assert fake.polls >= 3  # kept polling after the failure, plus a final flush
    assert fake.closed


def test_grafana_dashboard_only_uses_exported_metrics_and_labels(recorder, query):
    import json
    import re
    from pathlib import Path

    legacy_session(recorder, Clock(), client_app="claude")
    exposition = prometheus.render(query)
    exported_metrics = set(re.findall(r"^([a-z_]+?)(?:\{| )", exposition, re.M))
    exported_labels = set(re.findall(r'([a-z_]+)="', exposition)) | {"le"}

    path = Path(__file__).resolve().parents[3] / "examples" / "grafana" / "mcphawk-dashboard.json"
    dashboard = json.loads(path.read_text())
    queries = [t["expr"] for p in dashboard["panels"] for t in p["targets"]]
    queries += [v["query"]["query"] for v in dashboard["templating"]["list"]
                if v["type"] == "query"]
    for expr in queries:
        for metric in re.findall(r"\b(mcp_[a-z_]+|mcphawk_[a-z_]+)\b", expr):
            if metric in exported_labels:
                continue
            assert metric in exported_metrics, f"{metric} is not exported ({expr})"
        for label in re.findall(r"\b([a-z_]+)\s*(?:=~|!=|=)", expr):
            assert label in exported_labels, f"label {label} is not exported ({expr})"
        for group in re.findall(r"by \(([^)]*)\)", expr):
            for label in (part.strip() for part in group.split(",")):
                assert label in exported_labels, f"label {label} is not exported ({expr})"
