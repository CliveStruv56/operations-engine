# @ops-engine/shared

OpenAPI-generated TypeScript client for the API. Generated in Slice 2 once the
chat endpoints land, via:

```sh
cd apps/api && uv run python -c "import json; from app.main import app; print(json.dumps(app.openapi()))" > ../../packages/shared/openapi.json
pnpm dlx openapi-typescript packages/shared/openapi.json -o packages/shared/src/schema.d.ts
```

The OpenAPI document is the API contract (spec §6).
