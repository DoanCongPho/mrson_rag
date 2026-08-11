# Mr Son RAG — IELTS Speaking & Writing Assistant

A Retrieval-Augmented Generation chatbot built for an IELTS teacher's class materials (~55 Word documents on Speaking Part 2, Part 3, and Writing grammar). Students ask questions in a chat UI and get answers grounded in the actual lesson content, with clickable links back to the source Google Doc.

## Key Features

- **Category-aware retrieval** — course content is split into `part2` / `part3` / `writing`. Users can pin a chat session to one category via the mode switcher, or let the router pick automatically.
- **LLM router** — before every retrieval, a `gpt-4o-mini` call (structured output) decides per-query whether to retrieve at all (skips it for greetings/small talk), which category to filter to, and a dynamic `top_k` (3–10) based on how broad the question is.
- **Word-document ingestion pipeline** — parses `.docx` files in true document order (paragraphs *and* tables — most naive `python-docx` readers silently drop tables), chunks by heading boundaries with a token budget (`tiktoken`), and embeds each chunk (heading + body) with `text-embedding-3-small`.
- **Soft-deleted, versioned chunks** — re-ingesting a file deactivates its old chunks instead of deleting them, so past `RetrievalLog` references stay intact.
- **Source citations with live links** — every answer cites the chunks it used, each linking to the original Google Doc (synced from Drive metadata into Postgres).
- **Full observability** — every chat turn and every ingestion run is traced end-to-end with [Arize Phoenix](https://phoenix.arize.com/) (OpenTelemetry/OpenInference): router decision, retrieval hits + scores, LLM calls, and per-file ingestion spans, in two separate projects (Chat vs. Ingest).
- **Vector search on pgvector** — Postgres + `pgvector`, exact cosine search (no ANN index needed at current corpus scale).

## Architecture

```
Ingestion (offline, run manually when course materials change)
  Google Drive (source of truth)
    -> update_docs: sync file name/url metadata -> Postgres "documents" table
    -> local .docx copies -> loader (paragraphs + tables) -> chunker (by heading, token-bounded)
    -> embedder (text-embedding-3-small) -> Postgres "chunks" table (category, embedding, doc_url)

Serving (online, FastAPI backend)
  user query
    -> router (LLM: should_retrieve? / category? / top_k?)
    -> retrieve (pgvector cosine search, filtered by category)
    -> build grounded prompt -> chat completion (gpt-4o-mini)
    -> answer + cited sources -> saved to Postgres (conversations/messages/retrieval_logs)
```

Both pipelines share one Postgres database and are traced independently via Phoenix.

## Tech Stack

| Layer | Technology |
|---|---|
| Backend | FastAPI, SQLAlchemy 2.0 (typed ORM), Alembic migrations |
| Database | PostgreSQL 16 + `pgvector` |
| LLM / Embeddings | OpenAI (`gpt-4o-mini`, `text-embedding-3-small`) |
| Ingestion | `python-docx`, `tiktoken` |
| Observability | Arize Phoenix (OpenTelemetry / OpenInference) |
| Frontend | Vanilla HTML/CSS/JS (no build step), `marked` + `DOMPurify` for markdown |
| Packaging / infra | `uv`, Docker, Docker Compose, Nginx (frontend), Caddy-ready reverse proxy |

## Project Structure

```
app/            FastAPI backend — main.py (chat endpoint), router.py (LLM routing),
                retrieval.py (vector search), llm.py (prompting), schemas.py, tracing.py
ingestion/      loader.py, chunker.py, embedder.py, run_ingest.py, cleanup_chunks.py
db/             SQLAlchemy models + session factory
update_docs/    Google Drive metadata sync
alembic/        DB migrations
frontend/       static chat UI (mode switcher for part2/part3/writing)
docs/           architecture notes + how-to guides
word_files/     source .docx corpus (gitignored), split into heading_already_files/{part2,part3,writing}
```

## Setup

### Prerequisites

- Python 3.12+
- [`uv`](https://docs.astral.sh/uv/) for dependency management
- Docker (for Postgres + pgvector), or a Postgres 16 instance with the `pgvector` extension
- An OpenAI API key
- (Optional) A Google Cloud service account for Drive sync — see `docs/how_to_do_something/how_to_update_docs.md`
- (Optional) [Arize Phoenix](https://phoenix.arize.com/) for tracing

### 1. Clone and install dependencies

```bash
uv sync
```

### 2. Configure environment

Copy `.env.example` to `.env` and fill in the values:

```bash
cp .env.example .env
```

```env
DATABASE_URL=postgresql://raguser:ragpass@localhost:5432/ragdb
OPENAI_API_KEY=sk-...
PHOENIX_COLLECTOR_ENDPOINT=http://localhost:6006/v1/traces
PHOENIX_ENABLED=true        # set false to disable tracing entirely (no Phoenix server needed)
ROOT_FOLDER_ID=              # Google Drive folder id, only needed for update_docs sync
```

### 3. Start Postgres

```bash
docker compose up -d db
```

### 4. Run database migrations

```bash
uv run alembic upgrade head
```

### 5. (Optional) Ingest course materials

Requires `.docx` files under `word_files/heading_already_files/{part2,part3,writing}/`.

```bash
uv run python -m ingestion.run_ingest
```

See `docs/how_to_do_something/how_to_update_docs.md` for syncing source-doc links from Google Drive first.

### 6. Run the app

**Backend:**
```bash
uv run uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

**Frontend:**
```bash
cd frontend && python3 -m http.server 5500
```

Open `http://localhost:5500`.

**(Optional) Tracing UI:**
```bash
uv run phoenix serve
```
Open `http://localhost:6006` to inspect traces for every `/chat` call and ingestion run.

### Running everything with Docker Compose

```bash
docker compose up -d
```

Spins up Postgres, the FastAPI backend (migrations run automatically on start), and the Nginx-served frontend.

## Further Reading

- `docs/architecture.md` — design decisions and rationale
- `docs/how_to_do_something/how_to_update_docs.md` — Google Drive sync workflow
- `docs/how_to_do_something/how_to_run_and_code_phoenix.md` — tracing setup and how to add new spans
