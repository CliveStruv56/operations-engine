"""Is a database role still using a password this repository publishes?

Two literals reach real databases. Migration 0001 creates `ops_app` with one
when the role is missing, and `infra/docker-compose.dev.yml` sets the owner's.
The step meant to replace them — `infra/staging-roles.sql` — is documented for
the compose path, while Railway runs `alembic upgrade head` automatically as a
pre-deploy hook, so on any database first migrated there nothing guarantees a
default was ever replaced. Nothing visible from outside distinguishes the two
cases either, which is exactly why it went unnoticed.

Postgres stores a SCRAM verifier rather than the password, but a verifier can
be *tested* against a candidate: re-derive StoredKey from the candidate using
the salt and iteration count embedded in the stored string, and compare. That
turns "did anyone rotate this?" into a question a migration can answer, which
is what `0029_role_password_guard` does with it.

Deliberately migrations-local, matching `rls.py`: schema history must not shift
under us when application code is refactored.
"""

import base64
import binascii
import hashlib
import hmac

#: Role -> the password this repo would have given it. `ops_app` from
#: migration 0001, `ops` from the dev compose file.
PUBLISHED_PASSWORDS = {"ops": "ops", "ops_app": "ops_app"}

_SCRAM_PREFIX = "SCRAM-SHA-256$"


def password_matches(stored: str | None, candidate: str, rolname: str) -> bool:
    """True when `stored` (a `pg_authid.rolpassword` value) is `candidate`.

    Unknown or absent verifier formats return False: this feeds a guard that
    blocks deploys, so it must only fire on a positive identification, never
    on "I could not tell".
    """
    if not stored:
        return False
    if stored.startswith(_SCRAM_PREFIX):
        return _scram_matches(stored, candidate)
    if stored.startswith("md5"):
        # Pre-PG14 default: md5(password || rolname), hex, prefixed "md5".
        digest = hashlib.md5(  # noqa: S324 - verifying an existing hash, not creating one
            (candidate + rolname).encode(), usedforsecurity=False
        ).hexdigest()
        return hmac.compare_digest(stored, "md5" + digest)
    return False


def _scram_matches(stored: str, candidate: str) -> bool:
    """SCRAM-SHA-256$<iterations>:<salt>$<StoredKey>:<ServerKey>, all base64.

    StoredKey = SHA256(HMAC(PBKDF2(password, salt, iterations), "Client Key")),
    so the candidate can be checked without ever recovering the password.
    """
    try:
        params, keys = stored[len(_SCRAM_PREFIX) :].split("$", 1)
        iterations, salt_b64 = params.split(":", 1)
        stored_key = base64.b64decode(keys.split(":", 1)[0], validate=True)
        salted = hashlib.pbkdf2_hmac(
            "sha256", candidate.encode(), base64.b64decode(salt_b64, validate=True), int(iterations)
        )
    except (ValueError, binascii.Error):
        return False  # malformed verifier: not an identification
    client_key = hmac.new(salted, b"Client Key", hashlib.sha256).digest()
    return hmac.compare_digest(hashlib.sha256(client_key).digest(), stored_key)
