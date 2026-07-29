"""Chunker contract tests (spec §5): heading awareness, size target, overlap,
tables never split mid-row."""

from worker.blocks import Block, estimate_tokens
from worker.chunking import chunk_blocks
from worker.parsing import _parse_text

SENTENCE = "The quick brown fox jumps over the lazy dog near the river bank today. "


def make_text(sentences: int) -> str:
    return (SENTENCE * sentences).strip()


def test_small_blocks_merge_into_one_chunk():
    blocks = [Block("First paragraph."), Block("Second paragraph.")]
    chunks = chunk_blocks(blocks)
    assert len(chunks) == 1
    assert "First paragraph." in chunks[0].content
    assert "Second paragraph." in chunks[0].content


def test_chunks_respect_target_size():
    blocks = [Block(make_text(10)) for _ in range(20)]  # ~180 tokens each
    chunks = chunk_blocks(blocks, target_tokens=600)
    assert len(chunks) > 1
    # Allow the heading/overlap margin but nothing should balloon.
    assert all(c.token_count <= 800 for c in chunks)


def test_heading_boundary_starts_new_chunk():
    blocks = [
        Block("Intro text.", heading_path=["Intro"]),
        Block("Policy details.", heading_path=["Policies", "Leave"]),
    ]
    chunks = chunk_blocks(blocks)
    assert len(chunks) == 2
    assert chunks[0].heading_path == ["Intro"]
    assert chunks[1].heading_path == ["Policies", "Leave"]
    assert chunks[1].content.startswith("Policies > Leave")


def test_overlap_carries_sentences_within_section():
    blocks = [Block(make_text(12), heading_path=["S"]) for _ in range(6)]
    chunks = chunk_blocks(blocks, target_tokens=400, overlap_ratio=0.15)
    assert len(chunks) >= 2
    # The second chunk begins with text repeated from the end of the first.
    first_body = chunks[0].content
    second_body = chunks[1].content.removeprefix("S\n\n")
    overlap_head = second_body[:60].strip()
    assert overlap_head and overlap_head in first_body


def test_pages_tracked():
    blocks = [Block("Page one text.", page=1), Block("Page three text.", page=3)]
    chunks = chunk_blocks(blocks)
    assert chunks[0].page_start == 1
    assert chunks[0].page_end == 3


def test_large_table_splits_at_rows_with_header_repeated():
    header = "| Item | Cost |\n|---|---|"
    rows = "\n".join(f"| item {i} with a fairly long description | {i}.00 |" for i in range(200))
    table = Block(f"{header}\n{rows}", is_table=True)
    chunks = chunk_blocks([table], target_tokens=300)
    assert len(chunks) > 1
    for chunk in chunks:
        body = chunk.content
        assert "| Item | Cost |" in body  # header repeated on every part
        # No dangling half rows: every data line still has both cells.
        for line in body.splitlines():
            if line.startswith("| item"):
                assert line.rstrip().endswith("|")
    # Every row survives exactly once across parts.
    all_rows = "\n".join(c.content for c in chunks)
    assert all(f"| item {i} " in all_rows for i in range(200))


def test_small_table_stays_atomic_and_merges():
    table = Block("| A | B |\n|---|---|\n| 1 | 2 |", is_table=True)
    chunks = chunk_blocks([Block("Before."), table, Block("After.")])
    assert len(chunks) == 1
    assert "| 1 | 2 |" in chunks[0].content


def test_oversized_paragraph_splits_at_sentences():
    blocks = [Block(make_text(80))]  # ~1400 tokens in one paragraph
    chunks = chunk_blocks(blocks, target_tokens=600)
    assert len(chunks) >= 2
    assert all(c.token_count <= 800 for c in chunks)
    for chunk in chunks:
        assert chunk.content.strip().endswith(".")  # sentence-boundary splits


def test_estimate_tokens_rough_scale():
    assert estimate_tokens("word " * 100) == pytest_approx_range(100, 160)


def pytest_approx_range(low: int, high: int):
    class _InRange:
        def __eq__(self, other):
            return low <= other <= high

    return _InRange()


def test_text_parser_headings_and_tables():
    raw = (
        "# Handbook\n\nWelcome text.\n\n## Leave\n\nHoliday rules.\n\n"
        "| Type | Days |\n|---|---|\n| Annual | 25 |"
    )
    blocks = _parse_text(raw)
    assert blocks[0].heading_path == ["Handbook"]
    assert blocks[1].heading_path == ["Handbook", "Leave"]
    assert blocks[2].is_table
