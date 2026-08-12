import torch
from transformers import AutoModelForSequenceClassification, AutoTokenizer

from db.models import Chunk
from app.tracing import tracer_provider
from openinference.semconv.trace import SpanAttributes

tracer = tracer_provider.get_tracer(__name__)

MODEL_NAME = "AITeamVN/Vietnamese_Reranker"
MAX_LENGTH = 2304

_tokenizer = AutoTokenizer.from_pretrained(MODEL_NAME)
_model = AutoModelForSequenceClassification.from_pretrained(MODEL_NAME)
_model.eval()


def rerank(query: str, candidates: list[tuple[Chunk, float]], top_k: int) -> list[tuple[Chunk, float]]:
    with tracer.start_as_current_span("rerank") as span:
        span.set_attribute(SpanAttributes.OPENINFERENCE_SPAN_KIND, "RERANKER")
        span.set_attribute(SpanAttributes.INPUT_VALUE, query)

        chunks = [chunk for chunk, _ in candidates]
        pairs = [[query, chunk.text] for chunk in chunks]

        with torch.no_grad():
            inputs = _tokenizer(
                pairs, padding=True, truncation=True, max_length=MAX_LENGTH, return_tensors="pt"
            )
            logits = _model(**inputs, return_dict=True).logits.view(-1).float()
            scores = torch.sigmoid(logits).tolist()

        reranked = sorted(zip(chunks, scores), key=lambda pair: pair[1], reverse=True)[:top_k]

        for i, (chunk, score) in enumerate(reranked):
            span.set_attribute(f"{SpanAttributes.RETRIEVAL_DOCUMENTS}.{i}.document.id", str(chunk.id))
            span.set_attribute(f"{SpanAttributes.RETRIEVAL_DOCUMENTS}.{i}.document.content", chunk.text)
            span.set_attribute(f"{SpanAttributes.RETRIEVAL_DOCUMENTS}.{i}.document.score", score)
        span.set_attribute(SpanAttributes.OUTPUT_VALUE, f"{len(reranked)} chunks reranked")

        return reranked
