"""Single-container entrypoint for Hugging Face Spaces: the API under /api and the
static frontend under /, on one origin so the session cookie works without CORS."""
from pathlib import Path

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from app.main import app as api, lifespan

FRONTEND_DIR = Path(__file__).resolve().parent.parent / "frontend"

# Mounted sub-apps don't run their own lifespan, so reuse the API's (reranker warm-up, DB check).
app = FastAPI(lifespan=lifespan, docs_url=None, redoc_url=None, openapi_url=None)
app.mount("/api", api)
app.mount("/", StaticFiles(directory=FRONTEND_DIR, html=True), name="frontend")
