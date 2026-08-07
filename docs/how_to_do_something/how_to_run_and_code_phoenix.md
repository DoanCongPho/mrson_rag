# How to run và code tracing với Arize Phoenix

Phoenix là tool observability cho LLM app — theo dõi latency, input/output, retrieval documents của từng request qua OpenTelemetry (chuẩn OpenInference).

## 1. Setup 1 lần

`.env` cần biến:

```
PHOENIX_COLLECTOR_ENDPOINT=http://localhost:6006/v1/traces
```

Dependencies đã có sẵn trong `pyproject.toml`: `arize-phoenix`, `openinference-instrumentation-openai`.

## 2. Chạy local

Cần 3 process chạy song song (3 terminal riêng):

**Phoenix UI + collector:**
```bash
uv run phoenix serve
```
Mặc định lắng nghe ở `http://localhost:6006` — đây vừa là nơi nhận trace (`/v1/traces`) vừa là UI xem trace.

**Backend:**
```bash
uv run uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

**Frontend:**
```bash
cd frontend && python3 -m http.server 5500
```

Sau đó mở `http://localhost:6006` để xem trace mỗi khi gọi `/chat`.

## 3. Cấu trúc code tracing

### `app/tracing.py` — khởi tạo global tracer provider

```python
from phoenix.otel import register
from config import settings

tracer_provider = register(
    project_name="MRSON RAG",
    endpoint=settings.phoenix_collector_endpoint,
    auto_instrument=True,
)
```

- `auto_instrument=True` tự động patch các thư viện đã cài kèm openinference instrumentation (ở đây là `openinference-instrumentation-openai`) — nghĩa là **mọi lệnh gọi `client.chat.completions.create(...)` / `client.embeddings.create(...)` qua SDK OpenAI đều tự động được trace, không cần code gì thêm.**
- Phải `import app.tracing` **trước** khi bất kỳ module nào gọi OpenAI SDK, để instrumentation kịp patch. Đó là lý do `app/main.py` có `import app.tracing` ngay đầu file (dòng 5), trước cả `from app.llm import ...`.
- `register()` chỉ nên gọi **1 lần** cho cả app — import `tracer_provider` từ module này ở nơi khác, không gọi `register()` lại.

### Span thủ công — khi cần trace 1 đoạn logic không phải lệnh gọi OpenAI

Ví dụ `app/retrieval.py` (bước retrieve từ pgvector không tự động được trace vì không phải OpenAI call):

```python
from app.tracing import tracer_provider
from openinference.semconv.trace import SpanAttributes

tracer = tracer_provider.get_tracer(__name__)

def retrieve(query: str, top_k: int = 5) -> list[tuple[Chunk, float]]:
    with tracer.start_as_current_span("retrieve") as span:
        span.set_attribute(SpanAttributes.OPENINFERENCE_SPAN_KIND, "RETRIEVER")
        span.set_attribute(SpanAttributes.INPUT_VALUE, query)

        query_vector = embed_query(query)  # lệnh này tự trace riêng (auto_instrument)
        results = ...

        for i, (chunk, dist) in enumerate(results):
            span.set_attribute(f"{SpanAttributes.RETRIEVAL_DOCUMENTS}.{i}.document.id", str(chunk.id))
            span.set_attribute(f"{SpanAttributes.RETRIEVAL_DOCUMENTS}.{i}.document.content", chunk.text)
            span.set_attribute(f"{SpanAttributes.RETRIEVAL_DOCUMENTS}.{i}.document.score", 1 - dist)

        return [(chunk, float(dist)) for chunk, dist in results]
```

Pattern chung khi muốn tự thêm span cho 1 đoạn code mới:

1. `tracer = tracer_provider.get_tracer(__name__)` ở đầu module.
2. Bọc đoạn logic bằng `with tracer.start_as_current_span("<tên span>") as span:`.
3. Set `SpanAttributes.OPENINFERENCE_SPAN_KIND` — giá trị chuẩn theo OpenInference: `"RETRIEVER"`, `"LLM"`, `"CHAIN"`, `"TOOL"`, `"EMBEDDING"`... Phoenix dùng field này để hiển thị icon/màu đúng loại span trên UI.
4. Set `SpanAttributes.INPUT_VALUE` / `OUTPUT_VALUE` cho input/output chính của bước đó.
5. Nếu là bước retrieval, set thêm `RETRIEVAL_DOCUMENTS.{i}.document.id/content/score` cho từng document — Phoenix render riêng 1 tab "Retrieved Documents" khi có field này.

Span con tạo trong lúc đang ở trong `with` của span cha sẽ tự động nested đúng (dùng OpenTelemetry context, không cần truyền tay).

## 4. Lưu ý

- `register()` hiện đang dùng `SimpleSpanProcessor` mặc định (Phoenix console sẽ in warning "strongly advised to use a BatchSpanProcessor in production"). Ở local/dev không sao — `SimpleSpanProcessor` gửi trace ngay lập tức (dễ debug), nhưng production nên đổi sang `BatchSpanProcessor` để giảm overhead network mỗi request.
- Muốn gắn thêm `user_id`/`session_id` vào trace (để filter theo user trong Phoenix UI) thì dùng `using_session`/`using_user` context manager của Phoenix — **chưa làm** trong project này, để sau nếu cần.
- Muốn đánh giá tự động chất lượng answer (Relevance, Hallucination, QA Correctness) thì dùng Phoenix Evals — cũng chưa setup, đây là bước nâng cao hơn để sau.
