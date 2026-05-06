FROM --platform=$BUILDPLATFORM python:3.12-slim AS base

ARG TARGETPLATFORM
WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    ffmpeg libsndfile1 \
    # build deps pour les wheels qui manquent en arm64
    build-essential libffi-dev \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt /app/requirements.txt
# Sur arm64, certaines dépendances scientifiques bénéficient de --prefer-binary
RUN pip install --no-cache-dir --prefer-binary -r /app/requirements.txt

ENV PYTHONUNBUFFERED=1 PYTHONPATH=/app

CMD ["python", "-m", "app.main"]
