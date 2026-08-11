from openai import OpenAI
from config import settings

from db.session import SessionLocal
from db.models import Chunk

from app.tracing import tracer_provider

from openinference.semconv.trace import SpanAttributes


tracer = tracer_provider.get_tracer(__name__)

client = OpenAI(api_key=settings.openai_api_key)


def embed_query(query: str) -> list[float]:
    response = client.embeddings.create(
        model="text-embedding-3-small",
        input=query,
    )
    return response.data[0].embedding

def retrieve(query: str, top_k: int = 5, category: str | None = None) -> list[tuple[Chunk, float]]:
    with tracer.start_as_current_span("retrieve") as span:
        # Phoenix log
        span.set_attribute(SpanAttributes.OPENINFERENCE_SPAN_KIND, "RETRIEVER")
        span.set_attribute(SpanAttributes.INPUT_VALUE, query)
        if category is not None:
            span.set_attribute("retrieval.category_filter", category)

        query_vector = embed_query(query)
        session = SessionLocal()
        distance = Chunk.embedding.cosine_distance(query_vector)
        # Không có ANN index (ivfflat/hnsw) trên bảng này -- exact scan là đủ nhanh
        # và chính xác hơn ở quy mô ~1k chunks, cố ý chưa thêm ANN index.
        q = session.query(Chunk, distance.label("distance")).filter(Chunk.is_active.is_(True))
        if category is not None:
            q = q.filter(Chunk.category == category)
        results = q.order_by(distance).limit(top_k).all()
        session.close()
        for i, (chunk, dist) in enumerate(results):
            span.set_attribute(f"{SpanAttributes.RETRIEVAL_DOCUMENTS}.{i}.document.id", str(chunk.id))
            span.set_attribute(f"{SpanAttributes.RETRIEVAL_DOCUMENTS}.{i}.document.content", chunk.text)
            span.set_attribute(f"{SpanAttributes.RETRIEVAL_DOCUMENTS}.{i}.document.score", 1 - dist)
        return [(chunk, float(dist)) for chunk, dist in results]


def main():
    query = "Value line là gì?"
    results = retrieve(query)
    for chunk, distance in results:
        print(f"{chunk.section_title} (distance={distance:.4f})")
    print()

if __name__ == "__main__":
    main()