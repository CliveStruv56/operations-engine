"""The parse → chunk interface: parsers emit Blocks, the chunker consumes
them. Keeping this dataclass dependency-free lets the chunker be unit-tested
without Docling installed."""

from dataclasses import dataclass, field


@dataclass
class Block:
    text: str
    heading_path: list[str] = field(default_factory=list)
    page: int | None = None
    is_table: bool = False


def estimate_tokens(text: str) -> int:
    """Same cheap ~4 chars/token estimate the API uses for routing."""
    return len(text) // 4 + 1
