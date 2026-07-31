from uuid import UUID, uuid4

import pytest
from cryptography.fernet import Fernet

from app.config import get_settings
from app.db import db
from app.errors import ApiError
from app.litellm import litellm_client
from app.secrets import decrypt_llm_key, encrypt_llm_key
from tests.conftest import auth


@pytest.fixture
def crypto_key(monkeypatch):
    key = Fernet.generate_key().decode()
    monkeypatch.setenv("LITELLM_KEY_ENCRYPTION_KEY", key)
    get_settings.cache_clear()
    yield key
    get_settings.cache_clear()


def test_round_trip(crypto_key):
    stored = encrypt_llm_key("sk-secret")
    assert stored != "sk-secret"
    assert stored.startswith("gAAAA")
    assert decrypt_llm_key(stored) == "sk-secret"


def test_pass_through_when_disabled():
    assert encrypt_llm_key("sk-secret") == "sk-secret"
    assert decrypt_llm_key("sk-secret") == "sk-secret"
    assert encrypt_llm_key(None) is None
    assert decrypt_llm_key(None) is None


def test_undecryptable_value_raises_503(crypto_key):
    with pytest.raises(ApiError) as exc:
        decrypt_llm_key("sk-cleartext-left-behind")
    assert exc.value.status_code == 503


async def test_bootstrap_stores_ciphertext(client, monkeypatch, crypto_key):
    async def fake_create(tenant_id, soft_budget_usd):
        return "sk-live-secret"

    monkeypatch.setattr(litellm_client, "create_tenant_key", fake_create)
    owner_id = uuid4()
    resp = await client.post("/api/v1/tenants", json={"name": "enc-test"}, headers=auth(owner_id))
    assert resp.status_code == 201, resp.text
    tenant_id = UUID(resp.json()["id"])

    async with db.tenant_tx(owner_id, tenant_id) as conn:
        stored = await conn.fetchval(
            "select litellm_key_encrypted from tenants where id = $1", tenant_id
        )
    assert stored != "sk-live-secret"
    assert stored.startswith("gAAAA")
    assert decrypt_llm_key(stored) == "sk-live-secret"
