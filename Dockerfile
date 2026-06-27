FROM python:3.12-slim

WORKDIR /app

ENV APP_ENV=development
ENV SQLITE_DB_PATH=/data/travel_products.db
ENV SQLITE_BACKUP_DIR=/app/backups
ENV PORT=8000

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY apps ./apps
COPY scripts ./scripts
COPY alembic ./alembic
COPY alembic.ini .
COPY README.md .

RUN mkdir -p /data /app/backups

EXPOSE 8000

CMD uvicorn apps.backend.main:app --host 0.0.0.0 --port ${PORT}
