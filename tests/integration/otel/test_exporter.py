import pytest
from opentelemetry.sdk._logs import LoggerProvider
from opentelemetry.sdk._logs.export import (
    InMemoryLogRecordExporter,
    SimpleLogRecordProcessor,
)
from opentelemetry.sdk.metrics import MeterProvider
from opentelemetry.sdk.metrics.export import InMemoryMetricReader
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import SimpleSpanProcessor
from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter
from opentelemetry.trace import SpanKind, StatusCode

from mcphawk import runs
from mcphawk.otel import exporter as ex
from mcphawk.otel import semconv
from mcphawk.store import C2S, S2C
from tests.traffic import Clock, frame, legacy_session, modern_meta, modern_session

TRACEPARENT = "00-4bf92f3577b34da6a3ce929d0e0e4736-00f067aa0ba902b7-01"


class Telemetry:
    def __init__(self, query, now, payloads=False):
        self.spans = InMemorySpanExporter()
        self.logs = InMemoryLogRecordExporter()
        self.metrics = InMemoryMetricReader()
        ids = ex._PlannedIds()
        tracer_provider = TracerProvider(resource=ex.resource(), id_generator=ids)
        tracer_provider.add_span_processor(SimpleSpanProcessor(self.spans))
        logger_provider = LoggerProvider(resource=ex.resource())
        logger_provider.add_log_record_processor(SimpleLogRecordProcessor(self.logs))
        self.clock = now
        self.exporter = ex.TelemetryExporter(
            query, tracer_provider=tracer_provider,
            meter_provider=MeterProvider(metric_readers=[self.metrics]),
            logger_provider=logger_provider, ids=ids, include_payloads=payloads,
            now=lambda: self.clock[0])

    def span(self, name):
        return next(s for s in self.spans.get_finished_spans() if s.name == name)

    def metric_points(self, name):
        data = self.metrics.get_metrics_data()
        return [point for rm in data.resource_metrics for sm in rm.scope_metrics
                for metric in sm.metrics if metric.name == name
                for point in metric.data.data_points]


@pytest.fixture
def telemetry(query):
    return Telemetry(query, [999_000.0])


def test_live_poll_exports_spans_logs_and_metrics(recorder, query, telemetry):
    clock = Clock(1_000_000.0)
    sid = legacy_session(recorder, clock, client_key="pid:1", client_app="claude")
    telemetry.clock[0] = clock.t + 1
    sent = telemetry.exporter.poll()
    assert sent == {"spans": 5, "logs": 11, "runs": 0}
    assert telemetry.exporter.poll() == {"spans": 0, "logs": 0, "runs": 0}  # no duplicates

    run_key = runs.list_runs(query, now=clock.t)[0]["run_key"]
    weather = [s for s in telemetry.spans.get_finished_spans()
               if s.name == "tools/call get_weather"]
    ok, failed = weather
    assert ok.kind == SpanKind.CLIENT
    assert ok.context.trace_id == semconv.run_trace_id(run_key)
    assert ok.parent.span_id == semconv.run_span_id(run_key)
    assert ok.attributes["mcphawk.client.name"] == "Claude Code"
    assert ok.attributes["mcp.protocol.version"] == "2025-06-18"
    assert (ok.end_time - ok.start_time) / 1e9 == pytest.approx(0.25)
    assert failed.status.status_code == StatusCode.ERROR
    assert failed.attributes["error.type"] == "tool_error"
    search = telemetry.span("tools/call search")
    assert search.attributes["error.type"] == "-32602"
    assert search.status.description == "bad query"

    logs = [r.log_record for r in telemetry.logs.get_finished_logs()]
    assert len(logs) == 11
    error_log = next(r for r in logs if r.attributes.get("error.type") == "-32602")
    assert error_log.severity_text == "ERROR"
    assert error_log.span_id == search.context.span_id
    assert error_log.trace_id == search.context.trace_id
    notification = next(r for r in logs if r.attributes.get("mcp.method.name")
                        == "notifications/initialized")
    assert notification.span_id == 0  # not part of any call

    durations = telemetry.metric_points(semconv.OPERATION_DURATION)
    by_error = {p.attributes.get("error.type"): p.count for p in durations
                if p.attributes.get("gen_ai.tool.name") == "get_weather"}
    assert by_error == {None: 1, "tool_error": 1}
    tokens = telemetry.metric_points(semconv.RESULT_TOKENS)
    assert sum(p.count for p in tokens) == 3
    definitions = {p.attributes["gen_ai.tool.name"]: p.value
                   for p in telemetry.metric_points(semconv.DEFINITION_TOKENS)}
    assert set(definitions) == {"get_weather", "search"}
    assert definitions["search"] > definitions["get_weather"]
    assert sid


def test_root_span_is_sent_once_the_run_ends(recorder, query, telemetry):
    clock = Clock(1_000_000.0)
    legacy_session(recorder, clock, client_key="pid:1", client_app="claude")
    telemetry.clock[0] = clock.t + 1
    assert telemetry.exporter.poll()["runs"] == 0  # still going
    telemetry.clock[0] = clock.t + runs.RUN_GAP_S + 5
    assert telemetry.exporter.poll()["runs"] == 1
    assert telemetry.exporter.poll()["runs"] == 0
    root = telemetry.span("Claude Code run")
    run_key = runs.list_runs(query)[0]["run_key"]
    assert root.parent is None
    assert root.context.trace_id == semconv.run_trace_id(run_key)
    assert root.context.span_id == semconv.run_span_id(run_key)
    assert root.attributes["mcphawk.run.calls"] == 5
    assert root.status.status_code == StatusCode.ERROR


def test_traceparent_from_the_client_wins_and_retries_nest(recorder, query, telemetry):
    sid = recorder.open_session(capture="proxy", transport="streamable_http",
                                target="http://localhost:9000/mcp", ts=1_000_000)
    meta = {**modern_meta(), "traceparent": TRACEPARENT}
    recorder.record(sid, C2S, frame(id=1, method="tools/call", params={
        "name": "t", "_meta": meta}), ts=1_000_001)
    recorder.record(sid, S2C, frame(id=1, result={
        "resultType": "input_required", "requestState": "s"}), ts=1_000_002)
    recorder.record(sid, C2S, frame(id=2, method="tools/call", params={
        "name": "t", "requestState": "s", "_meta": modern_meta()}), ts=1_000_003)
    recorder.record(sid, S2C, frame(id=2, result={"resultType": "complete",
                                                  "content": []}), ts=1_000_004)
    telemetry.clock[0] = 1_000_010
    telemetry.exporter.poll()
    first, retry = sorted((s for s in telemetry.spans.get_finished_spans()),
                          key=lambda s: s.start_time)
    assert first.context.trace_id == 0x4bf92f3577b34da6a3ce929d0e0e4736
    assert first.parent.span_id == 0x00f067aa0ba902b7
    assert first.attributes["mcphawk.result.type"] == "input_required"
    assert retry.context.trace_id == first.context.trace_id
    assert retry.parent.span_id == first.context.span_id
    assert first.attributes["server.port"] == 9000
    # calls carried in the agent's trace get no run root span
    telemetry.clock[0] = 1_000_010 + runs.RUN_GAP_S + 5
    assert telemetry.exporter.poll()["runs"] == 0


def test_payloads_are_opt_in(recorder, query):
    telemetry = Telemetry(query, [999_000.0], payloads=True)
    modern_session(recorder, Clock(1_000_000.0))
    telemetry.clock[0] = 1_000_100
    telemetry.exporter.poll()
    logs = [r.log_record for r in telemetry.logs.get_finished_logs()]
    assert all("mcphawk.message.payload" in r.attributes for r in logs)


def test_export_history_selects_and_skips_pending(recorder, query, telemetry):
    clock = Clock(1_000_000.0)
    first = legacy_session(recorder, clock, client_key="pid:1")
    second = modern_session(recorder, Clock(1_100_000.0), client_key="pid:1")
    recorder.record(second, C2S, frame(id=99, method="tools/list"), ts=1_100_002)
    telemetry.clock[0] = 1_200_000
    sent = telemetry.exporter.export_history(session_id=first)
    assert sent == {"spans": 5, "logs": 11, "runs": 1}
    assert telemetry.metric_points(semconv.OPERATION_DURATION) == []  # history: no metrics

    older, newer = sorted(runs.list_runs(query), key=lambda r: r["started_at"])
    telemetry.spans.clear()
    sent = telemetry.exporter.export_history(run_key=newer["run_key"])
    assert sent["spans"] == 5  # includes the call that was never answered
    unanswered = next(s for s in telemetry.spans.get_finished_spans()
                      if s.attributes.get("jsonrpc.request.id") == "99")
    assert unanswered.attributes["error.type"] == "abandoned"
    assert telemetry.exporter.export_history()["spans"] == 10


def test_export_history_skips_calls_still_waiting(recorder, query, monkeypatch):
    telemetry = Telemetry(query, [999_000.0])
    sid = recorder.open_session(capture="wrap", transport="stdio", client_key="pid:2",
                                ts=1_000_000)
    recorder.record(sid, C2S, frame(id=1, method="tools/list"), ts=1_000_001)
    monkeypatch.setattr(query, "_is_live", lambda session: True)
    monkeypatch.setattr(query, "_now", lambda: 1_000_002)
    assert telemetry.exporter.export_history()["spans"] == 0


def test_calls_outside_any_run_get_their_own_trace(recorder, query, telemetry, monkeypatch):
    modern_session(recorder, Clock(1_000_000.0))
    monkeypatch.setattr(ex._RunIndex, "find", lambda self, session_id, ts: None)
    telemetry.clock[0] = 1_000_100
    telemetry.exporter.poll()
    spans = telemetry.spans.get_finished_spans()
    session_id = spans[0].attributes["mcphawk.session.id"]
    discover = next(s for s in spans if s.name == "server/discover")
    assert discover.parent is None
    assert discover.context.trace_id == semconv.session_trace_id(session_id)
    assert "mcphawk.run.key" not in discover.attributes


def test_planned_ids_fall_back_to_random():
    ids = ex._PlannedIds()
    ids.span_id, ids.trace_id = 5, 6
    assert (ids.generate_span_id(), ids.generate_trace_id()) == (5, 6)
    assert ids.generate_span_id() not in (0, 5)
    assert ids.generate_trace_id() not in (0, 6)


def test_from_env_builds_otlp_pipeline(query, monkeypatch):
    monkeypatch.setenv("OTEL_EXPORTER_OTLP_ENDPOINT", "http://127.0.0.1:1")
    monkeypatch.setenv("OTEL_SERVICE_NAME", "hawk-test")
    exporter = ex.TelemetryExporter.from_env(query)
    assert exporter._tracer_provider.resource.attributes["service.name"] == "hawk-test"
    exporter.shutdown()
