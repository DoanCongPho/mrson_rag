from openai import OpenAI
from config import settings

from db.session import SessionLocal
from db.models import Chunk

from app.tracing import tracer_provider

from openinference.semconv.trace import SpanAttributes


tracer = tracer_provider.get_tracer(__name__)

client = OpenAI(api_key=settings.openai_api_key)

# Khi bật reranker, lấy 1 shortlist rộng hơn bằng cosine (rẻ) rồi để
# cross-encoder chấm lại chính xác hơn xuống còn top_k thật.
RERANK_CANDIDATE_K = 30


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

        q = session.query(Chunk, distance.label("distance")).filter(Chunk.is_active.is_(True))
        if category is not None:
            q = q.filter(Chunk.category == category)
        fetch_k = RERANK_CANDIDATE_K if settings.reranker_enabled else top_k
        rows = q.order_by(distance).limit(fetch_k).all()
        session.close()

        results = [(chunk, 1 - float(dist)) for chunk, dist in rows]

        if settings.reranker_enabled and results:
            from app.reranker import rerank  # import lazy: chỉ load model (torch) khi thật sự bật

            results = rerank(query, results, top_k)

        for i, (chunk, score) in enumerate(results):
            span.set_attribute(f"{SpanAttributes.RETRIEVAL_DOCUMENTS}.{i}.document.id", str(chunk.id))
            span.set_attribute(f"{SpanAttributes.RETRIEVAL_DOCUMENTS}.{i}.document.content", chunk.text)
            span.set_attribute(f"{SpanAttributes.RETRIEVAL_DOCUMENTS}.{i}.document.score", score)
        return results


def main():
    query = "Value line là gì?"
    results = retrieve(query)
    for chunk, score in results:
        print(f"{chunk.section_title} (score={score:.4f})")
    print()

if __name__ == "__main__":
    main()