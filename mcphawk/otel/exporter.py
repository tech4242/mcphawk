"""Stream captured MCP traffic to any OpenTelemetry backend.

Runs inside ``mcphawk up`` and reads the capture database, so it sees every
wrapper, proxy and sniffer process and knows agent-run boundaries.

* **Traces:** one span per call. A ``traceparent`` sent by the client in
  ``_meta`` wins, so spans join the agent's own trace; otherwise each agent
  run is one trace with a root span, emitted once the run has ended.
* **Metrics:** ``mcp.client.operation.duration`` plus token metrics.
* **Logs:** one record per captured message, linked to its call's span.

Configured with the standard ``OTEL_*`` environment variables.
"""

import logging
import os
import time
from collections.abc import Iterable
from typing import Any

from opentelemetry import trace
from opentelemetry._logs import SeverityNumber
from opentelemetry.metrics import CallbackOptions, Observation
from opentelemetry.sdk._logs import LoggerProvider
from opentelemetry.sdk.metrics import MeterProvider
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.id_generator import IdGenerator, RandomIdGenerator
from opentelemetry.trace import (
    NonRecordingSpan,
    SpanContext,
    SpanKind,
    Status,
    StatusCode,
)

from mcphawk import __version__
from mcphawk.otel import semconv
from mcphawk.protocol import mcp as proto
from mcphawk.protocol.tokens import estimate_json, estimate_text
from mcphawk.query import Query
from mcphawk.runs import RUN_GAP_S, Run, client_label, compute_runs

logger = logging.getLogger(__name__)

POLL_S = 2.0
_SEVERITY = {"INFO": SeverityNumber.INFO, "WARN": SeverityNumber.WARN,
             "ERROR": SeverityNumber.ERROR}
_SAMPLED = trace.TraceFlags(trace.TraceFlags.SAMPLED)


class _PlannedIds(IdGenerator):
    """Lets the exporter choose span and trace ids; random when nothing is planned.

    Deterministic ids make exports stable and let a retry name the span of
    the call it retries before or after that span is exported.
    """

    def __init__(self) -> None:
        self._random = RandomIdGenerator()
        self.span_id: int | None = None
        self.trace_id: int | None = None

    def generate_span_id(self) -> int:
        value, self.span_id = self.span_id, None
        return value or self._random.generate_span_id()

    def generate_trace_id(self) -> int:
        value, self.trace_id = self.trace_id, None
        return value or self._random.generate_trace_id()


def _ns(seconds: float) -> int:
    return int(seconds * 1_000_000_000)


def _context(trace_id: int, span_id: int, flags: int = _SAMPLED):
    return trace.set_span_in_context(NonRecordingSpan(SpanContext(
        trace_id=trace_id, span_id=span_id, is_remote=True,
        trace_flags=trace.TraceFlags(flags))))


def resource() -> Resource:
    return Resource.create({
        "service.name": os.environ.get("OTEL_SERVICE_NAME", "mcphawk"),
        "service.version": __version__,
    })


class TelemetryExporter:
    def __init__(
        self,
        q: Query,
        *,
        tracer_provider: TracerProvider,
        meter_provider: MeterProvider,
        logger_provider: LoggerProvider,
        ids: _PlannedIds,
        include_payloads: bool = False,
        now=time.time,
    ):
        self.q = q
        self._ids = ids
        self._include_payloads = include_payloads
        self._now = now
        self._tracer_provider = tracer_provider
        self._meter_provider = meter_provider
        self._logger_provider = logger_provider
        self._tracer = tracer_provider.get_tracer("mcphawk", __version__)
        self._logger = logger_provider.get_logger("mcphawk", __version__)
        meter = meter_provider.get_meter("mcphawk", __version__)
        self._duration = meter.create_histogram(
            semconv.OPERATION_DURATION, unit="s",
            description="Duration of MCP requests as observed on the wire.",
            explicit_bucket_boundaries_advisory=list(semconv.DURATION_BUCKETS))
        self._result_tokens = meter.create_histogram(
            semconv.RESULT_TOKENS, unit="{token}",
            description="Estimated tokens a tool result adds to the model's context.")
        self._definitions: dict[tuple[str, str], int] = {}
        meter.create_observable_gauge(
            semconv.DEFINITION_TOKENS, callbacks=[self._observe_definitions], unit="{token}",
            description="Estimated tokens each tool definition adds to every model turn.")
        self._message_cursor = q.latest_message_id()
        self._ended_cursor = now()
        self._exported: set[int] = set()
        self._roots_done: set[str] = set()
        self._roots_pending: dict[str, tuple[Run, list[dict[str, Any]]]] = {}

    # -- construction -------------------------------------------------------

    @classmethod
    def from_env(cls, q: Query, include_payloads: bool = False) -> "TelemetryExporter":
        """OTLP over HTTP, configured by the standard OTEL_* variables."""
        from opentelemetry.exporter.otlp.proto.http._log_exporter import OTLPLogExporter
        from opentelemetry.exporter.otlp.proto.http.metric_exporter import (
            OTLPMetricExporter,
        )
        from opentelemetry.exporter.otlp.proto.http.trace_exporter import (
            OTLPSpanExporter,
        )
        from opentelemetry.sdk._logs.export import BatchLogRecordProcessor
        from opentelemetry.sdk.metrics.export import PeriodicExportingMetricReader
        from opentelemetry.sdk.trace.export import BatchSpanProcessor

        ids = _PlannedIds()
        res = resource()
        tracer_provider = TracerProvider(resource=res, id_generator=ids)
        tracer_provider.add_span_processor(BatchSpanProcessor(OTLPSpanExporter()))
        meter_provider = MeterProvider(resource=res, metric_readers=[
            PeriodicExportingMetricReader(OTLPMetricExporter())])
        logger_provider = LoggerProvider(resource=res)
        logger_provider.add_log_record_processor(BatchLogRecordProcessor(OTLPLogExporter()))
        return cls(q, tracer_provider=tracer_provider, meter_provider=meter_provider,
                   logger_provider=logger_provider, ids=ids,
                   include_payloads=include_payloads)

    def shutdown(self) -> None:
        for provider in (self._tracer_provider, self._meter_provider, self._logger_provider):
            try:
                provider.shutdown()
            except Exception:  # pragma: no cover - exporter shutdown is best effort
                logger.exception("OpenTelemetry shutdown failed")

    def flush(self) -> None:
        self._tracer_provider.force_flush()
        self._meter_provider.force_flush()
        self._logger_provider.force_flush()

    # -- live streaming -----------------------------------------------------

    def poll(self) -> dict[str, int]:
        """Export everything that happened since the last poll."""
        runs = compute_runs(self.q)
        index = _RunIndex(runs)
        started = self._now()

        messages = self.q.messages(after_id=self._message_cursor, limit=5000, with_body=True)
        if messages:
            self._message_cursor = messages[-1]["id"]
        sessions = self._sessions({m["session_id"] for m in messages})

        finished = self.q.exchanges(ended_since=self._ended_cursor - 1, limit=5000)
        finished = [e for e in finished if e["id"] not in self._exported]
        self._ended_cursor = started
        sessions.update(self._sessions({e["session_id"] for e in finished} - set(sessions)))

        for exchange in finished:
            self._export_exchange(exchange, sessions[exchange["session_id"]], index,
                                  record_metrics=True)
        for message in messages:
            self._export_log(message, sessions[message["session_id"]], index)
        roots = self._export_roots(runs, closed_before=started - RUN_GAP_S)
        if len(self._exported) > 100_000:
            self._exported = set(sorted(self._exported)[-50_000:])
        return {"spans": len(finished), "logs": len(messages), "runs": roots}

    # -- backfill -----------------------------------------------------------

    def export_history(self, *, run_key: str | None = None,
                       session_id: str | None = None) -> dict[str, int]:
        """Send past traffic (traces and logs; metrics only describe the present)."""
        runs = compute_runs(self.q)
        index = _RunIndex(runs)
        if run_key:
            selected = [(r, s) for r, s in runs if r.key == run_key]
        elif session_id:
            selected = [(r, s) for r, s in runs if session_id in r.session_ids]
        else:
            selected = runs
        spans = logs = 0
        for run, members in selected:
            sessions = {s["id"]: s for s in members}
            ids = [s["id"] for s in members if not session_id or s["id"] == session_id]
            for exchange in self.q.exchanges(session_ids=ids, since=run.start - 1,
                                             until=run.end + 1, limit=100_000):
                if exchange["status"] in ("pending", "hung"):
                    continue
                self._export_exchange(exchange, sessions[exchange["session_id"]], index,
                                      record_metrics=False)
                spans += 1
            for message in self.q.messages_between(ids, run.start - 1, run.end + 1):
                self._export_log(message, sessions[message["session_id"]], index)
                logs += 1
        roots = self._export_roots(selected, closed_before=self._now() - RUN_GAP_S)
        self.flush()
        return {"spans": spans, "logs": logs, "runs": roots}

    # -- signals ------------------------------------------------------------

    def _sessions(self, ids: Iterable[str]) -> dict[str, dict[str, Any]]:
        ids = list(ids)
        if not ids:
            return {}
        return {s["id"]: s for s in self.q.list_sessions(session_ids=ids, limit=len(ids),
                                                         include_hidden=True)}

    def _parent(self, exchange: dict[str, Any], index: "_RunIndex"
                ) -> tuple[Any, str | None]:
        """Parent context for a call's span, and the run it belongs to."""
        run = index.find(exchange["session_id"], exchange["started_at"])
        run_key = run.key if run else None
        request = self.q.get_message(exchange["request_msg_id"]) if exchange.get(
            "request_msg_id") else None
        propagated = semconv.request_traceparent((request or {}).get("body"))
        if exchange.get("parent_id"):
            trace_id = self._trace_id(exchange["chain_root_id"] or exchange["parent_id"],
                                      index, run_key)
            return _context(trace_id, semconv.exchange_span_id(exchange["parent_id"])), run_key
        if propagated:
            trace_id, span_id, flags = propagated
            return _context(trace_id, span_id, flags), run_key
        if run_key:
            if run.key not in self._roots_done:
                self._roots_pending.setdefault(run.key, (run, []))
            return _context(semconv.run_trace_id(run_key), semconv.run_span_id(run_key)), run_key
        # no run (should not happen): a trace of its own for the session
        self._ids.trace_id = semconv.session_trace_id(exchange["session_id"])
        return trace.set_span_in_context(trace.INVALID_SPAN), None

    def _trace_id(self, exchange_id: int, index: "_RunIndex", run_key: str | None) -> int:
        root = self.q.get_exchange(exchange_id)
        if root:
            request = (root.get("request") or {}).get("body")
            propagated = semconv.request_traceparent(request)
            if propagated:
                return propagated[0]
        return semconv.run_trace_id(run_key) if run_key else semconv.session_trace_id(
            root["session_id"] if root else "")

    def _export_exchange(self, exchange: dict[str, Any], session: dict[str, Any],
                         index: "_RunIndex", record_metrics: bool) -> None:
        parent, run_key = self._parent(exchange, index)
        end = exchange.get("ended_at") or (
            exchange["started_at"] + (exchange.get("duration_ms") or 0) / 1000)
        self._ids.span_id = semconv.exchange_span_id(exchange["id"])
        span = self._tracer.start_span(
            semconv.span_name(exchange), context=parent, kind=SpanKind.CLIENT,
            attributes=semconv.span_attributes(exchange, session, run_key),
            start_time=_ns(exchange["started_at"]))
        failure = semconv.error_type(exchange)
        if failure:
            span.set_status(Status(StatusCode.ERROR, exchange.get("error_message") or failure))
        span.end(end_time=_ns(end))
        self._exported.add(exchange["id"])

        if exchange["method"] == "tools/list" and exchange["status"] == "ok":
            self._remember_definitions(exchange, session)
        if record_metrics:
            attributes = semconv.metric_attributes(exchange, session)
            self._duration.record(max(end - exchange["started_at"], 0), attributes)
            if exchange["method"] == "tools/call":
                self._result_tokens.record(exchange.get("response_tokens") or 0, attributes)

    def _export_log(self, message: dict[str, Any], session: dict[str, Any],
                    index: "_RunIndex") -> None:
        severity, body, attributes = semconv.log_fields(message, session,
                                                        self._include_payloads)
        context = None
        if message.get("exchange_id"):
            exchange = self.q.get_exchange(message["exchange_id"])
            if exchange:
                run = index.find(exchange["session_id"], exchange["started_at"])
                trace_id = self._trace_id(exchange["chain_root_id"] or exchange["id"], index,
                                          run.key if run else None)
                context = _context(trace_id, semconv.exchange_span_id(exchange["id"]))
        self._logger.emit(
            timestamp=_ns(message["ts"]), context=context, severity_text=severity,
            severity_number=_SEVERITY[severity], body=body, attributes=attributes)

    def _export_roots(self, runs: list[tuple[Run, list[dict[str, Any]]]],
                      closed_before: float) -> int:
        """One root span per finished run whose calls were exported."""
        done = 0
        wanted = {run.key: (run, members) for run, members in runs}
        for key in list(self._roots_pending):
            if key not in wanted:
                continue
            run, members = wanted[key]
            if run.end > closed_before:
                continue
            self._ids.trace_id = semconv.run_trace_id(run.key)
            self._ids.span_id = semconv.run_span_id(run.key)
            span = self._tracer.start_span(
                f"{client_label(members, run.group)} run", kind=SpanKind.INTERNAL,
                context=trace.set_span_in_context(trace.INVALID_SPAN),
                start_time=_ns(run.start),
                attributes={
                    "mcphawk.run.key": run.key,
                    "mcphawk.client.name": client_label(members, run.group),
                    "mcphawk.run.servers": sorted({m["display_name"] for m in members}),
                    "mcphawk.run.calls": run.exchanges,
                    "mcphawk.run.errors": run.errors,
                })
            if run.errors:
                span.set_status(Status(StatusCode.ERROR, f"{run.errors} failed calls"))
            span.end(end_time=_ns(run.end))
            del self._roots_pending[key]
            self._roots_done.add(key)
            done += 1
        return done

    # -- context cost gauge -------------------------------------------------

    def _remember_definitions(self, exchange: dict[str, Any], session: dict[str, Any]) -> None:
        response = self.q.get_message(exchange["response_msg_id"]) if exchange.get(
            "response_msg_id") else None
        server = session.get("display_name") or "unknown"
        for tool in proto.tools_from_list((response or {}).get("body") or {}):
            name = str(tool.get("name"))
            tokens = (estimate_text(name) + estimate_text(str(tool.get("description") or ""))
                      + estimate_json(tool.get("inputSchema"))
                      + estimate_json(tool.get("outputSchema")))
            self._definitions[(server, name)] = tokens

    def _observe_definitions(self, options: CallbackOptions) -> Iterable[Observation]:
        return [Observation(tokens, {"mcphawk.server.name": server, "gen_ai.tool.name": tool})
                for (server, tool), tokens in sorted(self._definitions.items())]


class _RunIndex:
    """Which run a call belongs to, from a session id and a timestamp."""

    def __init__(self, runs: list[tuple[Run, list[dict[str, Any]]]]):
        self._by_session: dict[str, list[Run]] = {}
        for run, _ in runs:
            for session_id in run.session_ids:
                self._by_session.setdefault(session_id, []).append(run)

    def find(self, session_id: str, ts: float) -> Run | None:
        for run in self._by_session.get(session_id, []):
            if run.start - 1 <= ts <= run.end + 1:
                return run
        return None
