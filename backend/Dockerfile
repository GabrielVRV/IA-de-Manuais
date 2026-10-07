# syntax=docker/dockerfile:1

# ---------- Estágio 1: build do pacote ----------
FROM python:3.12-slim AS builder

ENV PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /build
COPY pyproject.toml README.md ./
COPY src ./src
RUN pip wheel --wheel-dir /wheels .

# ---------- Estágio 2: imagem final enxuta ----------
FROM python:3.12-slim AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

RUN useradd --create-home --uid 1000 app \
    # Pasta dos PDFs: criada com o dono certo para o volume herdar a permissão.
    && mkdir -p /home/app/data/manuals \
    && chown -R app:app /home/app/data

COPY --from=builder /wheels /wheels
RUN pip install /wheels/* && rm -rf /wheels

USER app
WORKDIR /home/app
EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/api/v1/health', timeout=4)"

# Aplica as migrações pendentes e só então inicia a API.
CMD ["sh", "-c", "python -m manual_assistant.infrastructure.persistence.migrate && exec uvicorn --factory manual_assistant.main:create_app --host 0.0.0.0 --port 8000"]
