# Multi-stage production Dockerfile for FastAPI Backend
FROM python:3.11-slim

WORKDIR /app

# Install system dependencies for pymupdf and compilation
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements and install
COPY backend/requirements.txt ./requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

# Copy application files and dataset
COPY backend/ ./backend/
COPY data/ ./data/

WORKDIR /app/backend

ENV PYTHONPATH=/app/backend:/app
ENV PORT=8000
ENV HOST=0.0.0.0

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
