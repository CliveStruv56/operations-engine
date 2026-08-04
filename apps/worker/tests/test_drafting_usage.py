"""DRAFT-001: the engine meters every terminal outcome, not just success.

`CLAUDE.md` hard constraint 5 is "cost telemetry on every LLM call". Usage
rows used to be written by each module's `register_draft()`, which runs only
on success — so a job that died on its ninth model call billed the tenant
nothing. Observed live on 4 Aug 2026: a provider 429 after real calls
recorded `llm_calls 0, tokens_out 0, cost_usd 0`.

This drives `run_draft` against a fake pool, so it asserts the *control flow*:
which outcomes write usage and how much. That the INSERT itself lands under
RLS is asserted from the API suite against the migrated database
(`tests/test_worker_drafting_usage.py`, ASSUMPTIONS #13).
"""

import asyncio
import contextlib
import json

import httpx
import pytest

from tests.test_drafts_context import _pack
from tests.test_drafts_pipeline import _completion, _FakeClient
from worker.drafting.engine import DraftModule, run_draft
from worker.drafting.llm import DraftBudgetExceeded
from worker.drafting.sections import Section

TENANT = "8f6b2e2a-0f6a-4b28-9a3f-3c2a1d5e6b70"
SUBJECT = "1a2b3c4d-5e6f-4a7b-8c9d-0e1f2a3b4c5d"
JOB = "9e8d7c6b-5a4f-4e3d-2c1b-0a9f8e7d6c5b"
USER = "3f2e1d0c-9b8a-4756-8342-1f0e9d8c7b6a"

SECTIONS = [Section("intro", "Introduction"), Section("next", "Next steps")]


class _FakeConn:
    """Records every statement the engine runs, so a test can assert on them."""

    def __init__(self, log: list[tuple[str, tuple]]):
        self.log = log

    @contextlib.asynccontextmanager
    async def transaction(self):
        yield self

    async def execute(self, sql, *args):
        self.log.append((sql, args))

    async def executemany(self, sql, args):
        self.log.append((sql, tuple(args)))

    async def fetchrow(self, sql, *args):
        self.log.append((sql, args))
        if "draft_jobs" in sql:
            return {"kind": "monthly_report", "params": json.dumps({})}
        return None

    async def fetchval(self, sql, *args):
        self.log.append((sql, args))
        return "encrypted-key"


class _FakePool:
    def __init__(self):
        self.log: list[tuple[str, tuple]] = []

    @contextlib.asynccontextmanager
    async def acquire(self):
        yield _FakeConn(self.log)

    def usage_rows(self) -> list[tuple]:
        rows: list[tuple] = []
        for sql, args in self.log:
            if "insert into usage_events" not in sql:
                continue
            rows.extend(args if isinstance(args[0], tuple) else [args])
        return rows

    def statuses(self) -> list[str]:
        return [
            status
            for sql, _ in self.log
            for status in ("running", "failed", "succeeded")
            if f"status = '{status}'" in sql
        ]


def _module(register=None, gather=None) -> DraftModule:
    async def _gather(conn, subject_id, kind, params, today):
        return _pack(kind=kind)

    async def _register(conn, **kw):
        # Registration no longer writes usage — the engine does.
        await conn.execute("update proj_draft_jobs set status = 'succeeded' where id = $1", JOB)
        return SUBJECT

    return DraftModule(
        storage_segment="projects",
        job_table="proj_draft_jobs",
        system_prompt="system",
        skeletons={"monthly_report": SECTIONS},
        tables={},
        gather=gather or _gather,
        queries_for=lambda kind, pack: [],  # no embedding call to fake
        scope_weights=lambda conn, subject_id: asyncio.sleep(0, {}),
        register=register or _register,
    )


def _gateway(monkeypatch, replies):
    """Serve `replies` in order; a callable reply is raised or called."""
    pending = iter(replies)

    def _client(**_kw):
        reply = next(pending)
        if callable(reply):
            reply()
        return _FakeClient(reply)

    monkeypatch.setattr("worker.drafting.llm.httpx.AsyncClient", _client)
    monkeypatch.setattr(
        "worker.drafting.llm.get_settings",
        lambda: type("S", (), {"litellm_base_url": "http://gateway"})(),
    )
    monkeypatch.setattr("worker.drafting.engine.decrypt_llm_key", lambda _: "virtual-key")
    monkeypatch.setattr("worker.drafting.engine.upload_bytes", lambda *a, **kw: None)


def _boom():
    raise httpx.ReadTimeout("gateway timed out")


async def test_a_failed_draft_bills_the_calls_it_already_made(monkeypatch):
    pool = _FakePool()
    # Outline + one section, then the gateway dies on the second section.
    _gateway(monkeypatch, [_completion("{}"), _completion("Prose."), _boom])

    with pytest.raises(httpx.ReadTimeout):
        await run_draft(_module(), {"pool": pool}, TENANT, SUBJECT, JOB, USER)

    rows = pool.usage_rows()
    assert len(rows) == 2, "two calls were made and paid for, so two rows"
    # (tenant_id, user_id, alias, tokens_in, tokens_out, cost_usd)
    assert [r[3] for r in rows] == [100, 100]
    assert [r[4] for r in rows] == [200, 200]
    assert all(r[5] > 0 for r in rows)
    assert pool.statuses() == ["running", "failed"]


async def test_the_failure_status_is_written_before_the_usage_rows(monkeypatch):
    """Separate transactions, in that order: a usage write that fails must not
    roll back the failure status the UI polls for."""
    pool = _FakePool()
    _gateway(monkeypatch, [_completion("{}"), _boom])

    with pytest.raises(httpx.ReadTimeout):
        await run_draft(_module(), {"pool": pool}, TENANT, SUBJECT, JOB, USER)

    order = [sql for sql, _ in pool.log if "status = 'failed'" in sql or "usage_events" in sql]
    assert "status = 'failed'" in order[0]
    assert "usage_events" in order[1]


async def test_a_failure_before_the_first_call_bills_nothing(monkeypatch):
    """No zero rows: a gather-level failure must not invent an empty charge —
    and `_mark_failed` must not crash reaching for a ledger that never
    existed, which would leave the job stuck at 'running'."""

    async def _explode(conn, subject_id, kind, params, today):
        raise ValueError("Project not found")

    pool = _FakePool()
    _gateway(monkeypatch, [])
    with pytest.raises(ValueError, match="Project not found"):
        await run_draft(_module(gather=_explode), {"pool": pool}, TENANT, SUBJECT, JOB, USER)

    assert pool.usage_rows() == []
    assert pool.statuses() == ["running", "failed"]


async def test_a_cancelled_job_still_bills_what_it_spent(monkeypatch):
    """arq's job_timeout cancels mid-draft — the calls already made are real
    money and must not vanish with the job."""

    def _cancel():
        raise asyncio.CancelledError()

    pool = _FakePool()
    _gateway(monkeypatch, [_completion("{}"), _completion("Prose."), _cancel])

    with pytest.raises(asyncio.CancelledError):
        await run_draft(_module(), {"pool": pool}, TENANT, SUBJECT, JOB, USER)

    assert len(pool.usage_rows()) == 2
    assert pool.statuses() == ["running", "failed"]


async def test_the_cost_guard_is_metered_too(monkeypatch):
    """`DraftBudgetExceeded` aborts a job that has already spent — the guard
    exists because those calls cost money, so they must be billed."""
    pool = _FakePool()
    monkeypatch.setattr("worker.drafting.llm.MAX_LLM_CALLS", 2)
    _gateway(monkeypatch, [_completion("{}"), _completion("Prose."), _completion("More.")])

    with pytest.raises(DraftBudgetExceeded):
        await run_draft(_module(), {"pool": pool}, TENANT, SUBJECT, JOB, USER)

    assert len(pool.usage_rows()) == 2
    assert pool.statuses() == ["running", "failed"]


async def test_a_successful_draft_is_metered_exactly_once(monkeypatch):
    """Metering moved out of `register_draft()`; success must be unchanged —
    one row per call, and no duplicate from the module."""
    pool = _FakePool()
    _gateway(monkeypatch, [_completion("{}"), _completion("One."), _completion("Two.")])

    result = await run_draft(_module(), {"pool": pool}, TENANT, SUBJECT, JOB, USER)

    assert result == f"succeeded:{SUBJECT}"
    assert len(pool.usage_rows()) == len(SECTIONS) + 1  # every section plus the outline
    assert pool.statuses() == ["running", "succeeded"]


async def test_the_embedding_call_is_billed_on_a_failure_too(monkeypatch):
    """Retrieval spends real tokens before the first section is drafted."""
    from worker.drafting import engine

    class _Embedded:
        vectors: list = []
        tokens = 4_000
        cost_usd = 0.0004

    async def _embed(key, queries):
        return _Embedded()

    async def _weights(conn, subject_id):
        return {}

    async def _retrieve(conn, queries, vectors, weights):
        return []

    monkeypatch.setattr(engine, "embed_texts", _embed)
    monkeypatch.setattr(engine, "retrieve_excerpts", _retrieve)
    module = _module()
    module = DraftModule(**{**module.__dict__, "queries_for": lambda k, p: ["need evidence"]})
    pool = _FakePool()
    _gateway(monkeypatch, [_boom])

    with pytest.raises(httpx.ReadTimeout):
        await run_draft(module, {"pool": pool}, TENANT, SUBJECT, JOB, USER)

    embed_rows = [args for sql, args in pool.log if "usage_events" in sql and "'embed'" in sql]
    assert embed_rows and embed_rows[0][2] == 4_000
