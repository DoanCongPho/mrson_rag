# mrson_rag — Kiến trúc & cấu trúc project

RAG chatbot cho lớp học IELTS Speaking (Buổi học + BTVN, ~55 file `.docx`). LLM và embedding model: OpenAI.

## Tổng quan kiến trúc

Hai pipeline tách biệt, dùng chung 1 Postgres:

```
Ingestion (offline, chạy tay khi có tài liệu mới)
  docx files -> Loader -> Chunker -> Embedder -> Postgres (bảng chunks, có cột vector)

Serving (online, mỗi lượt chat)
  user query -> [condense query nếu multi-turn] -> embed query -> vector search top-k
  -> build grounded prompt -> gọi LLM -> trả lời -> lưu vào Postgres (conversations/messages)
```

**Vì sao tách 2 pipeline:** ingestion là job chạy 1 lần/khi cập nhật tài liệu; app là service chạy liên tục trả lời user. Nhịp sống khác nhau nên tách module, tránh phải re-embed toàn bộ tài liệu mỗi lần chạy app.

## Stack đã chốt
- Python 3.14, FastAPI, SQLAlchemy 2.0 (typed ORM) + Alembic (migration up/down)
- Postgres 16 + extension `pgvector` (chạy qua Docker, image `pgvector/pgvector:pg16`)
- OpenAI: LLM cho generation, `text-embedding-3-small` (1536 chiều) cho embedding
- Tokenizer: `tiktoken` (đếm token, không phải "encoder" — encoder thật là embedding model)

## Cấu trúc thư mục

```
mrson_rag/
├── word_files/                  # nguồn docx gốc
│   └── QUY_UOC_DANH_HEADING.md   # quy ước đánh Heading 1 cho các bạn cùng lớp sửa file
├── docs/
│   └── architecture.md           # file này
├── ingestion/                    # PIPELINE OFFLINE
│   ├── __init__.py
│   ├── loader.py                  # đọc 1 file docx -> list paragraph + feature (style/bold/color)
│   ├── chunker.py                 # (chưa code) list paragraph -> list chunk, tách theo Heading 1
│   ├── embedder.py                # (chưa code) gọi OpenAI embedding cho list chunk
│   └── run_ingest.py              # (chưa code) nhạc trưởng: loader -> chunker -> embedder -> lưu DB
├── app/                          # PIPELINE ONLINE (chatbot API)
│   ├── __init__.py
│   ├── main.py                    # (chưa code) FastAPI app + route
│   ├── retrieval.py               # (chưa code) query -> search top-k chunk trong DB
│   ├── llm.py                     # (chưa code) build prompt từ chunk + gọi Chat Completion
│   └── schemas.py                 # (chưa code) request/response models (Pydantic)
├── db/                            # dùng chung cho cả ingestion và app
│   ├── __init__.py
│   ├── models.py                  # (chưa code) SQLAlchemy models: users, conversations, messages, chunks, retrieval_logs
│   └── session.py                 # (chưa code) tạo engine/session kết nối Postgres
├── alembic/                       # migration up/down (chưa init)
├── config.py                      # (chưa code) đọc .env dùng chung
├── docker-compose.yml             # Postgres + pgvector, port 5432
├── requirements.txt
└── .env                           # OPENAI_API_KEY, DATABASE_URL (gitignored)
```

## Các quyết định thiết kế quan trọng

### 1. Chuyển đổi định dạng file
Dùng `python-docx` trực tiếp (không dùng markitdown) — vì hiện chỉ có docx, cần truy cập paragraph/run object để đọc style/bold/color, thứ markitdown không giữ lại được khi convert sang markdown.

### 2. Phát hiện cấu trúc tài liệu
File gốc không dùng Heading style của Word, chỉ có bold/màu chữ/màu nền mô phỏng header — không đáng tin để tách chunk tự động. Giải pháp: **sửa tại nguồn** — người có quyền sửa (bạn + các bạn cùng lớp) áp Heading 1 thật cho các mục lớn theo `word_files/QUY_UOC_DANH_HEADING.md`. Chỉ dùng **1 cấp Heading** (không Heading 2) để đơn giản hoá cả việc sửa file lẫn logic chunker.

Các thành phần sau **không** được coi là heading, giữ nguyên trong thân chunk:
- Nhãn/tiểu mục có màu/bold trong đoạn (vd "TRICK 1:", "Ví dụ:", "Opening")
- Ô màu nền (ví dụ đúng/sai), câu highlight vàng
- 1-2 dòng tiêu đề đầu file → xử lý như metadata `doc_title`, không tách chunk theo nó

### 3. Chunking strategy
Tách chunk theo ranh giới Heading 1 thật (`paragraph.style.name == "Heading 1"`). Trong mỗi section, gom paragraph theo kiểu paragraph-aware (không cắt giữa câu/đoạn). Chunk nhỏ hơn ngưỡng token thì giữ nguyên cả file/section làm 1 chunk, không cắt vụn.

### 4. Vector store
`pgvector` trong cùng Postgres với bảng users/conversations/messages — 1 database duy nhất, giảm hạ tầng phải quản lý, vẫn là pattern hợp lý để nói trong phỏng vấn.

### 5. Retrieval nâng cao (hybrid search, reranking, query rewriting)
Chưa làm ở MVP. Thiết kế `retrieval.py` dạng interface để dễ thêm sau. Riêng **query condensation cho multi-turn** (gộp câu hỏi follow-up + lịch sử chat thành 1 câu hỏi độc lập trước khi retrieve) cần làm sớm vì ảnh hưởng trực tiếp đến trải nghiệm chatbot nhiều lượt.

## Trạng thái hiện tại
- [x] Môi trường: venv, requirements, Docker Postgres + pgvector (đã enable extension, đã verify)
- [x] Quy ước Heading cho việc sửa file thủ công
- [x] `ingestion/loader.py`: đọc paragraph + style/bold/color (đã xong, đã test trên file mẫu)
- [ ] `ingestion/loader.py`: thêm `shading_fill` (màu nền ô) và `highlight_color` (câu tô vàng) — tạm hoãn
- [x] `config.py`: đọc `.env` bằng pydantic-settings, nguồn duy nhất cho `database_url`/`openai_api_key`
- [x] `db/models.py`: 5 bảng — users, conversations, messages, chunks (Vector 1536), retrieval_logs
- [x] `db/session.py`: engine + SessionLocal, đã verify connect Postgres
- [x] Alembic: init xong, migration đầu tiên (`180e5469a8b7_init_schema.py`) đã upgrade/downgrade thành công
- [ ] `ingestion/chunker.py`, `ingestion/embedder.py`, `ingestion/run_ingest.py`, `app/*` — chưa bắt đầu
- [ ] Eval set (~20-30 cặp Q/A) — chưa bắt đầu, nên làm trước khi tối ưu retrieval
