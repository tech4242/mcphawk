"""OpenTelemetry export (optional: ``pip install 'mcphawk[otel]'``)."""


def available() -> bool:
    try:
        import opentelemetry.exporter.otlp.proto.http
        import opentelemetry.sdk
    except ImportError:
        return False
    return True
