# Ingestion worker — Docling parse + embed. Torch (CPU) makes this image
# large; models download on first use into /home/worker/.cache (mount a
# volume to persist across container recreates). Torch is pinned to the CPU
# build deliberately — see the install step below.
FROM python:3.12-slim

# libpango/cairo/gdk-pixbuf + fonts are WeasyPrint's runtime (health card).
RUN apt-get update \
    && apt-get install -y --no-install-recommends libgl1 libglib2.0-0 \
        libpango-1.0-0 libpangocairo-1.0-0 libcairo2 libgdk-pixbuf-2.0-0 \
        fonts-dejavu-core \
    && rm -rf /var/lib/apt/lists/*

RUN useradd --create-home worker
# Pre-create the model cache so a named volume mounted here inherits worker's
# ownership instead of root's (the container runs unprivileged).
RUN mkdir -p /home/worker/.cache && chown worker:worker /home/worker/.cache
WORKDIR /app

COPY pyproject.toml ./
COPY worker/ worker/
# Torch's PyPI wheels bundle the CUDA runtime — roughly 4 GB of nvidia-*,
# triton and cuda-toolkit packages that this CPU-only worker never loads.
# Across two architectures on one runner that overflowed the build disk
# ("No space left on device"), which is why the image had not built since
# 31 Jul. Installing torch and torchvision from PyTorch's CPU index first
# leaves docling's torch requirement (>=2.2.2,<3) already satisfied, so the
# install below never reaches for the CUDA build. The CPU index mirrors
# torch's own dependencies, so resolving without PyPI here is fine.
RUN pip install --no-cache-dir --index-url https://download.pytorch.org/whl/cpu \
        torch torchvision \
    && pip install --no-cache-dir ".[parse]"

USER worker
CMD ["arq", "worker.main.WorkerSettings"]
