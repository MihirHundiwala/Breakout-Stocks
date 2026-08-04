FROM python:3.14-slim AS base

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

COPY requirements.txt ./
RUN pip install --no-cache-dir --requirement requirements.txt

COPY alembic.ini ./
COPY migrations ./migrations
COPY app ./app

EXPOSE 8000

CMD ["python", "-m", "app.scripts.run_api"]


FROM base AS development

COPY requirements-dev.txt ./
RUN pip install --no-cache-dir --requirement requirements-dev.txt


FROM base AS production
