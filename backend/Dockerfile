FROM python:3.12-slim

COPY --from=ghcr.io/astral-sh/uv:0.12.5 /uv /uvx /bin/

# Tesseract language data for local OCR of scans and photos (PyMuPDF calls it).
RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        tesseract-ocr tesseract-ocr-deu tesseract-ocr-eng \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app/backend
ENV PATH="/app/backend/.venv/bin:$PATH" \
    PYTHONUNBUFFERED=1 \
    UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy

COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev

COPY . .

RUN python -c "from pathlib import Path; from app.config import settings; \
    Path(settings.upload_dir).mkdir(parents=True, exist_ok=True); \
    Path(settings.embedding_cache_dir).mkdir(parents=True, exist_ok=True)"

CMD ["sh", "scripts/start.sh"]
