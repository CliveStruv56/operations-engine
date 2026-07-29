"""Heading-aware chunking (spec §5): ~600-token chunks, 15% overlap, tables
never split mid-row.

Rules:
- Chunks never span a heading boundary — each chunk belongs to one
  heading_path, and the joined path is prepended to the content so both the
  embedding and the tsvector index carry the section context.
- Text blocks accumulate until the target; the next chunk starts with an
  overlap tail taken at a sentence boundary.
- Tables are atomic. An oversized table splits at row boundaries with the
  header rows repeated on every part.
"""

from dataclasses import dataclass, field

from worker.blocks import Block, estimate_tokens


@dataclass
class Chunk:
    content: str
    heading_path: list[str]
    page_start: int | None
    page_end: int | None
    token_count: int = 0

    def __post_init__(self) -> None:
        self.token_count = estimate_tokens(self.content)


@dataclass
class _Buffer:
    heading_path: list[str]
    parts: list[Block] = field(default_factory=list)

    def tokens(self) -> int:
        return sum(estimate_tokens(b.text) for b in self.parts)


def chunk_blocks(
    blocks: list[Block],
    target_tokens: int = 600,
    overlap_ratio: float = 0.15,
) -> list[Chunk]:
    chunks: list[Chunk] = []
    buf: _Buffer | None = None

    def flush(next_heading: list[str] | None) -> None:
        nonlocal buf
        if buf is not None and buf.parts:
            chunks.append(_emit(buf))
            # Overlap only continues within the same section.
            if next_heading == buf.heading_path:
                tail = _overlap_tail(buf, int(target_tokens * overlap_ratio))
                buf = _Buffer(buf.heading_path, [tail] if tail else [])
                return
        buf = _Buffer(next_heading or [])

    for block in blocks:
        if buf is None or block.heading_path != buf.heading_path:
            flush(block.heading_path)
            buf.heading_path = block.heading_path

        if block.is_table:
            for part in _split_table(block, target_tokens):
                if buf.parts and buf.tokens() + estimate_tokens(part.text) > target_tokens:
                    flush(block.heading_path)
                if estimate_tokens(part.text) >= target_tokens:
                    # A full-size table part is its own chunk, no padding.
                    if buf.parts:
                        flush(block.heading_path)
                    chunks.append(_emit(_Buffer(block.heading_path, [part])))
                    buf = _Buffer(block.heading_path)
                else:
                    buf.parts.append(part)
            continue

        for para in _split_paragraphs(block):
            if buf.parts and buf.tokens() + estimate_tokens(para.text) > target_tokens:
                flush(block.heading_path)
            buf.parts.append(para)

    if buf is not None and buf.parts:
        chunks.append(_emit(buf))
    return chunks


def _emit(buf: _Buffer) -> Chunk:
    pages = [b.page for b in buf.parts if b.page is not None]
    body = "\n\n".join(b.text for b in buf.parts)
    if buf.heading_path:
        body = f"{' > '.join(buf.heading_path)}\n\n{body}"
    return Chunk(
        content=body,
        heading_path=buf.heading_path,
        page_start=min(pages) if pages else None,
        page_end=max(pages) if pages else None,
    )


def _overlap_tail(buf: _Buffer, overlap_tokens: int) -> Block | None:
    """Last sentences of the previous chunk, ≤ overlap_tokens. Tables don't
    carry into overlap."""
    last_text = next((b for b in reversed(buf.parts) if not b.is_table), None)
    if last_text is None or overlap_tokens <= 0:
        return None
    sentences = _split_sentences(last_text.text)
    tail: list[str] = []
    total = 0
    for sentence in reversed(sentences):
        total += estimate_tokens(sentence)
        if tail and total > overlap_tokens:
            break
        tail.insert(0, sentence)
    text = " ".join(tail).strip()
    if not text or estimate_tokens(text) > overlap_tokens:
        return None
    return Block(text, last_text.heading_path, last_text.page)


def _split_sentences(text: str) -> list[str]:
    out: list[str] = []
    start = 0
    for i, ch in enumerate(text):
        if ch in ".!?\n" and (i + 1 == len(text) or text[i + 1] in " \n"):
            piece = text[start : i + 1].strip()
            if piece:
                out.append(piece)
            start = i + 1
    rest = text[start:].strip()
    if rest:
        out.append(rest)
    return out


def _split_paragraphs(block: Block) -> list[Block]:
    """A single oversized paragraph still has to fit; split it at sentences."""
    paras = [p.strip() for p in block.text.split("\n\n") if p.strip()]
    out: list[Block] = []
    for para in paras:
        if estimate_tokens(para) <= 600:
            out.append(Block(para, block.heading_path, block.page))
            continue
        current = ""
        for sentence in _split_sentences(para):
            if current and estimate_tokens(current + " " + sentence) > 600:
                out.append(Block(current, block.heading_path, block.page))
                current = sentence
            else:
                current = f"{current} {sentence}".strip()
        if current:
            out.append(Block(current, block.heading_path, block.page))
    return out


def _split_table(table: Block, target_tokens: int) -> list[Block]:
    """Split a markdown table at row boundaries, repeating header rows."""
    if estimate_tokens(table.text) <= target_tokens:
        return [table]
    lines = table.text.splitlines()
    header: list[str] = []
    rows: list[str] = []
    for line in lines:
        stripped = line.strip()
        is_rule = stripped.startswith("|") and set(stripped) <= set("|-: ")
        if not rows and (is_rule or not header):
            header.append(line)
        else:
            rows.append(line)
    if not rows:  # not actually row-structured; treat as text
        return [table]

    parts: list[Block] = []
    header_text = "\n".join(header)
    current: list[str] = []
    for row in rows:
        candidate = header_text + "\n" + "\n".join([*current, row])
        if current and estimate_tokens(candidate) > target_tokens:
            parts.append(
                Block(
                    header_text + "\n" + "\n".join(current),
                    table.heading_path,
                    table.page,
                    is_table=True,
                )
            )
            current = [row]
        else:
            current.append(row)
    if current:
        parts.append(
            Block(
                header_text + "\n" + "\n".join(current),
                table.heading_path,
                table.page,
                is_table=True,
            )
        )
    return parts
