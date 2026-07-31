# LiteLLM proxy with the alias config baked in — for hosts that can't mount
# files (Railway). Compose deploys mount config.yaml instead and don't use
# this. "--host ::" for Railway's IPv6 private networking.
FROM ghcr.io/berriai/litellm-database:main-stable

COPY config.yaml /app/config.yaml

CMD ["--config", "/app/config.yaml", "--port", "4000", "--host", "::"]
