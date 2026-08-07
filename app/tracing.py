# app/tracing.py
from phoenix.otel import register
from config import settings

tracer_provider = register(
    project_name="MRSON RAG",
    endpoint=settings.phoenix_collector_endpoint,
    auto_instrument=True,
)