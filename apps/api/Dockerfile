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
# EXPOSE is Railway's port-detection signal for its edge proxy. 0.0.0.0, not
# "::": Railway's public edge connects over IPv4 and its runtime forces
# v6-only sockets, so a "::" bind 502s every public request. Only the public
# domain talks to the api — nothing uses it over the IPv6 private mesh.
EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
