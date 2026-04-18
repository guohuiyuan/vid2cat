FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    TZ=Asia/Shanghai \
    PYTHONPATH=/app/src

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    ca-certificates \
    curl \
    gnupg \
    nodejs \
    npm \
    tzdata \
    fonts-wqy-zenhei \
    && rm -rf /var/lib/apt/lists/*

RUN pip install --no-cache-dir uv

COPY pyproject.toml uv.lock /app/
COPY package.json package-lock.json /app/
COPY src /app/src
COPY scripts /app/scripts

RUN uv export --format requirements-txt --output-file requirements.txt --frozen \
    && uv pip install --system --no-cache-dir -r requirements.txt \
    && npm ci --omit=dev

RUN adduser --disabled-password --gecos '' appuser \
    && mkdir -p /app/data \
    && chown -R appuser:appuser /app

USER appuser

EXPOSE 8080

CMD ["uvicorn", "vid2cat.app:app", "--host", "0.0.0.0", "--port", "8080"]
