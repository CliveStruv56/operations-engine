# Ingestion worker — Docling parse + embed. Torch (CPU) makes this image
# large; models download on first use into /home/worker/.cache (mount a
# volume to persist across container recreates).
FROM python:3.12-slim

RUN apt-get update \
    && apt-get install -y --no-install-recommends libgl1 libglib2.0-0 \
    && rm -rf /var/lib/apt/lists/*

RUN useradd --create-home worker
# Pre-create the model cache so a named volume mounted here inherits worker's
# ownership instead of root's (the container runs unprivileged).
RUN mkdir -p /home/worker/.cache && chown worker:worker /home/worker/.cache
WORKDIR /app

COPY pyproject.toml ./
COPY worker/ worker/
RUN pip install --no-cache-dir ".[parse]"

USER worker
CMD ["arq", "worker.main.WorkerSettings"]
