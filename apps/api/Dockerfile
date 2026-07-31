# API image — CI builds this (.github/workflows/app-images.yml); staging pulls
# from GHCR. The project is not a package ([tool.uv] package = false), so deps
# install from the lockfile and the source is copied in. migrations/ ships in
# the image so the deploy migrate step can run from it:
#   docker run --rm -e DATABASE_URL=<owner-url> <image> alembic upgrade head
FROM python:3.12-slim

COPY --from=ghcr.io/astral-sh/uv:0.8 /uv /usr/local/bin/uv

RUN useradd --create-home api
WORKDIR /app

ENV UV_PROJECT_ENVIRONMENT=/app/.venv \
    PATH="/app/.venv/bin:$PATH"

COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev

COPY alembic.ini ./
COPY migrations/ migrations/
COPY app/ app/

USER api
# EXPOSE is Railway's port-detection signal for its edge proxy; "::" binds
# dual-stack — Railway's private/edge networking is IPv6-only, and IPv4-mapped
# addresses keep plain-Docker hosts working too.
EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "::", "--port", "8000"]
