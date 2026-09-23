"""Prometheus text exposition of MCPHawk's metrics at ``/metrics``.

Names and labels are what Prometheus produces when it ingests the OTLP
metrics (dots become underscores, seconds get a ``_seconds`` suffix), so one
dashboard works whether metrics arrive by scrape or by OTLP. No dependency on
the OpenTelemetry SDK. Values are computed from the capture database, so
they are cumulative until the data is cleared.
"""

from collections import defaultdict
from typing import Any

from mcphawk.analysis.cost import context_cost
from mcphawk.otel import semconv
from mcphawk.query import Query

CONTENT_TYPE = "text/plain; version=0.0.4; charset=utf-8"

_DURATION = "mcp_client_operation_duration_seconds"
_RESULT_TOKENS = "mcphawk_tool_result_tokens"
_DEFINITION_TOKENS = "mcphawk_tool_definition_tokens"


def _label_name(attribute: str) -> str:
    return attribute.replace(".", "_")


def _escape(value: Any) -> str:
    return str(value).replace("\\", "\\\\").replace("\n", "\\n").replace('"', '\\"')


def _labels(attributes: dict[str, Any], extra: tuple[tuple[str, str], ...] = ()) -> str:
    pairs = [(_label_name(k), v) for k, v in sorted(attributes.items())] + list(extra)
    return "{" + ",".join(f'{k}="{_escape(v)}"' for k, v in pairs) + "}"


def _number(value: float) -> str:
    return repr(float(value)) if value != int(value) else str(int(value))


def render(q: Query) -> str:
    durations: dict[tuple, list[float]] = defaultdict(list)
    tokens: dict[tuple, list[int]] = defaultdict(list)
    for row in q.finished_calls():
        session = {**row, "display_name": row["name"] or row["server_name"]
                   or row["session_target"]}
        attributes = semconv.metric_attributes(row, session)
        key = tuple(sorted(attributes.items()))
        durations[key].append((row["duration_ms"] or 0) / 1000)
        if row["method"] == "tools/call":
            tokens[key].append(row["response_tokens"] or 0)

    lines = [
        f"# HELP {_DURATION} Duration of MCP requests as observed on the wire.",
        f"# TYPE {_DURATION} histogram",
    ]
    for key, values in sorted(durations.items()):
        attributes = dict(key)
        for bound in semconv.DURATION_BUCKETS:
            count = sum(v <= bound for v in values)
            lines.append(f"{_DURATION}_bucket{_labels(attributes, (('le', _number(bound)),))}"
                         f" {count}")
        lines.append(f"{_DURATION}_bucket{_labels(attributes, (('le', '+Inf'),))} "
                     f"{len(values)}")
        lines.append(f"{_DURATION}_sum{_labels(attributes)} {_number(round(sum(values), 6))}")
        lines.append(f"{_DURATION}_count{_labels(attributes)} {len(values)}")

    lines += [
        f"# HELP {_RESULT_TOKENS} Estimated tokens tool results added to the context.",
        f"# TYPE {_RESULT_TOKENS} histogram",
    ]
    for key, values in sorted(tokens.items()):
        attributes = dict(key)
        lines.append(f"{_RESULT_TOKENS}_bucket{_labels(attributes, (('le', '+Inf'),))} "
                     f"{len(values)}")
        lines.append(f"{_RESULT_TOKENS}_sum{_labels(attributes)} {sum(values)}")
        lines.append(f"{_RESULT_TOKENS}_count{_labels(attributes)} {len(values)}")

    lines += [
        f"# HELP {_DEFINITION_TOKENS} Estimated tokens each tool definition adds to every"
        " model turn.",
        f"# TYPE {_DEFINITION_TOKENS} gauge",
    ]
    for server in context_cost(q)["servers"]:
        for definition in server["definitions"]:
            attributes = {"mcphawk.server.name": server["server"],
                          "gen_ai.tool.name": definition["name"]}
            lines.append(f"{_DEFINITION_TOKENS}{_labels(attributes)} {definition['total']}")
    return "\n".join(lines) + "\n"
