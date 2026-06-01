FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

COPY pyproject.toml manage.py /app/
COPY backend /app/backend

RUN pip install --no-cache-dir -e ".[dev]"

EXPOSE 8000
