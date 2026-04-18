FROM python:3.12-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PIP_NO_CACHE_DIR=1 TZ=Asia/Shanghai
WORKDIR /app
RUN apt-get update && apt-get install -y --no-install-recommends nodejs npm tzdata && rm -rf /var/lib/apt/lists/*
COPY package.json /app/package.json
RUN npm install --omit=dev
COPY pyproject.toml /app/pyproject.toml
RUN pip install --no-cache-dir "fastapi>=0.116.0" "httpx>=0.28.1" "itsdangerous>=2.2.0" "jinja2>=3.1.6" "json-repair>=0.52.3" "python-multipart>=0.0.20" "uvicorn>=0.35.0"
COPY src /app/src
COPY scripts /app/scripts
COPY .env.example /app/.env.example
RUN adduser --disabled-password --gecos '' appuser && mkdir -p /app/data && chown -R appuser:appuser /app
USER appuser
EXPOSE 8080
ENV PYTHONPATH=/app/src
CMD ["uvicorn", "vid2cat.app:app", "--host", "0.0.0.0", "--port", "8080"]
