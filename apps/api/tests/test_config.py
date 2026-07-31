import pytest
from pydantic import ValidationError

from app.config import Settings


def test_cors_rejects_bare_wildcard() -> None:
    with pytest.raises(ValidationError):
        Settings(cors_origins="*")


def test_cors_rejects_wildcard_among_origins() -> None:
    with pytest.raises(ValidationError):
        Settings(cors_origins="https://app.example.com,*")


def test_cors_rejects_empty() -> None:
    with pytest.raises(ValidationError):
        Settings(cors_origins=" , ")


def test_cors_strips_whitespace() -> None:
    s = Settings(cors_origins="https://a.example.com, https://b.example.com")
    assert s.cors_origin_list == ["https://a.example.com", "https://b.example.com"]
