FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

RUN addgroup --system mercury && adduser --system --ingroup mercury mercury

COPY pyproject.toml README.md ./
COPY --chown=mercury:mercury alembic.ini ./
COPY --chown=mercury:mercury alembic ./alembic
COPY --chown=mercury:mercury app ./app
COPY --chown=mercury:mercury scripts ./scripts

RUN pip install --no-cache-dir ".[dev]"

RUN mkdir -p /app/.mercury-data && chown -R mercury:mercury /app

USER mercury

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]

