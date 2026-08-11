# app/tracing.py
from opentelemetry.trace import NoOpTracerProvider
from phoenix.otel import register
from config import settings

if settings.phoenix_enabled:
    tracer_provider = register(
        project_name="MRSON RAG - Chat",
        endpoint=settings.phoenix_collector_endpoint,
        auto_instrument=True,
    )
else:
    tracer_provider = NoOpTracerProvider()
