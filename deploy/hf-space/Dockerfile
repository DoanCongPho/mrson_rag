# All-in-one image for a Hugging Face Docker Space: API + frontend + reranker model.
# scripts/deploy_hf_space.py copies this file to the Space root as "Dockerfile".
FROM python:3.12-slim

COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

# Spaces run the container as user 1000.
RUN useradd -m -u 1000 user
USER user
ENV HOME=/home/user \
    HF_HOME=/home/user/.cache/huggingface \
    UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    PYTHONUNBUFFERED=1
WORKDIR /home/user/app

COPY --chown=user pyproject.toml uv.lock .python-version ./
RUN uv sync --frozen --no-install-project --no-dev

# Bake the reranker into the image so a waking Space doesn't download ~2 GB first.
RUN .venv/bin/python -c "from transformers import AutoModelForSequenceClassification as M, AutoTokenizer as T; n='AITeamVN/Vietnamese_Reranker'; T.from_pretrained(n); M.from_pretrained(n)"

COPY --chown=user . .
RUN uv sync --frozen --no-dev

EXPOSE 7860
CMD ["sh", "-c", ".venv/bin/alembic upgrade head && exec .venv/bin/uvicorn app.space:app --host 0.0.0.0 --port 7860"]
