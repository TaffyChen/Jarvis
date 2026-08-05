# Jarvis 应用镜像：前端静态资源 + FastAPI
# 构建：docker build -f deploy/Dockerfile -t jarvis:local .
# 不要把 .env 打进镜像。

FROM node:22-alpine AS frontend
WORKDIR /web
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci
COPY frontend/ ./
RUN npm run build

FROM python:3.12-slim AS runtime
WORKDIR /srv
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH=/srv/backend \
    PIP_DISABLE_PIP_VERSION_CHECK=1

RUN apt-get update \
  && apt-get install -y --no-install-recommends curl \
  && rm -rf /var/lib/apt/lists/*

COPY backend/requirements.txt /srv/backend/requirements.txt
RUN pip install --no-cache-dir -r /srv/backend/requirements.txt

COPY backend /srv/backend
COPY knowledge /srv/knowledge
COPY --from=frontend /web/dist /srv/frontend/dist

RUN mkdir -p /srv/data/vectordb \
  && useradd --create-home --uid 10001 jarvis \
  && chown -R jarvis:jarvis /srv

USER jarvis
EXPOSE 1690
WORKDIR /srv/backend
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "1690"]
