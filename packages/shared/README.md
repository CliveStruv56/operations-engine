# @ops-engine/shared

**Status (14 Aug 2026): placeholder — nothing has been generated.** The web app's
shared response types live in `apps/web/lib/*.ts` today. The commands below are
the intended path if/when generation is wired up; until then this package holds
no code.

OpenAPI-generated TypeScript client for the API. Generated via:

```sh
cd apps/api && uv run python -c "import json; from app.main import app; print(json.dumps(app.openapi()))" > ../../packages/shared/openapi.json
pnpm dlx openapi-typescript packages/shared/openapi.json -o packages/shared/src/schema.d.ts
```

The OpenAPI document is the API contract (spec §6).
