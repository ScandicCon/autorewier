# Stage 1: Build Vue frontend
FROM node:20-alpine AS frontend-builder
WORKDIR /frontend
COPY frontend/package*.json ./
RUN npm ci
COPY frontend/ ./
ENV VITE_BASE_PATH=/
RUN npm run build

# Stage 2: Python backend
FROM python:3.12-slim AS runtime
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

RUN apt-get update \
    && apt-get install -y --no-install-recommends ca-certificates curl \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt ./
RUN pip install --upgrade pip \
    && pip install -r requirements.txt \
    && playwright install --with-deps chromium

COPY app ./app
COPY web ./web
COPY alembic ./alembic
COPY alembic.ini ./alembic.ini
COPY run_api.py ./
COPY run_bot.py ./
COPY .env.example ./.env.example
COPY --from=frontend-builder /frontend/dist ./frontend/dist

RUN mkdir -p /app/data

EXPOSE 8000

# Run alembic migrations then start server
CMD ["sh", "-c", "alembic upgrade head && python run_api.py"]
