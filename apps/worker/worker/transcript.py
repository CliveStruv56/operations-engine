"""Meeting transcripts (WebVTT) → Blocks, speaker-aware.

Recording and transcription are commoditised — Teams, Meet, Zoom and Fathom
all emit a .vtt — so the vault accepts the artefact and never competes with
the recorder. What a naive text parse loses is exactly what makes a
transcript useful: who said it and roughly when. So cues are merged into
speaker turns ("Sarah Fry: …"), and turns are grouped under ten-minute
headings ("Transcript › 0:10–0:20"). The chunker never spans a heading
boundary and prepends the heading path to each chunk, which means every
retrieved excerpt arrives time-anchored and speaker-attributed without the
chunker learning anything new.

Dependency-free (stdlib + Block) so the whole path is unit-testable without
Docling, same rule as the chunker.
"""

import re

from worker.blocks import Block

#: Coarse enough that a one-hour meeting is six sections, fine enough that
#: "when did we discuss the budget" retrieves a usable neighbourhood.
WINDOW_MINUTES = 10

#: `00:00:04.000 --> 00:00:09.500`, hours optional, settings after ignored.
_TIMING = re.compile(
    r"^(?:(\d+):)?(\d{1,2}):(\d{2})[.,](\d{3})\s*-->\s*(?:\d+:)?\d{1,2}:\d{2}[.,]\d{3}"
)
#: Teams/Meet voice spans: `<v Sarah Fry>`, `<v.quiet Sarah Fry>`.
_VOICE = re.compile(r"<v(?:\.[^\s>]*)?\s+([^>]+)>")
#: Everything else angle-bracketed: `</v>`, `<c>`, inline `<00:00:01.000>`.
_TAGS = re.compile(r"</?[^>]*>")
#: Zoom-style plain prefix: `Sarah Fry: text`. Bounded so a clock time or a
#: URL in the first words does not read as a speaker.
_SPEAKER_PREFIX = re.compile(r"^([^:\d][^:]{0,58}):\s+(.+)$", re.S)


def _start_seconds(line: str) -> float | None:
    match = _TIMING.match(line.strip())
    if match is None:
        return None
    hours = int(match.group(1) or 0)
    return hours * 3600 + int(match.group(2)) * 60 + int(match.group(3))


def _window_label(window: int) -> str:
    def fmt(minutes: int) -> str:
        return f"{minutes // 60}:{minutes % 60:02d}"

    start = window * WINDOW_MINUTES
    return f"{fmt(start)}–{fmt(start + WINDOW_MINUTES)}"


def _clean(payload: str) -> tuple[str | None, str]:
    """(speaker, text) from one cue payload, tags stripped."""
    voice = _VOICE.search(payload)
    speaker = voice.group(1).strip() if voice else None
    text = " ".join(_TAGS.sub("", payload).split()).strip()
    if speaker is None:
        prefix = _SPEAKER_PREFIX.match(text)
        if prefix:
            speaker, text = prefix.group(1).strip(), prefix.group(2).strip()
    return speaker, text


def parse_vtt(raw: str) -> list[Block]:
    # Cue = a timing line plus the payload lines under it. Headers, NOTE and
    # STYLE blocks, cue identifiers and settings all fall out for free: only
    # lines under a timing line are read.
    cues: list[tuple[float, str]] = []  # (start_seconds, payload)
    payload_lines: list[str] | None = None
    start = 0.0
    for line in raw.replace("﻿", "", 1).splitlines():
        seconds = _start_seconds(line)
        if seconds is not None:
            payload_lines = []
            start = seconds
            cues.append((start, ""))
            continue
        if not line.strip():
            payload_lines = None
            continue
        if payload_lines is not None:
            payload_lines.append(line.strip())
            cues[-1] = (start, " ".join(payload_lines))

    # Cues → speaker turns, merging consecutive cues from the same voice and
    # dropping the rolling-caption repeats some exporters emit.
    turns: list[tuple[float, str | None, str]] = []  # (start, speaker, text)
    for cue_start, payload in cues:
        speaker, text = _clean(payload)
        if not text:
            continue
        if turns:
            last_start, last_speaker, last_text = turns[-1]
            same_window = int(last_start // (WINDOW_MINUTES * 60)) == int(
                cue_start // (WINDOW_MINUTES * 60)
            )
            if speaker == last_speaker and same_window:
                # Rolling captions re-send the last words verbatim (skip) or
                # extended (replace); a genuinely new cue appends.
                if text in last_text:
                    continue
                if last_text in text:
                    turns[-1] = (last_start, last_speaker, text)
                else:
                    turns[-1] = (last_start, last_speaker, f"{last_text} {text}")
                continue
        turns.append((cue_start, speaker, text))

    return [
        Block(
            text=f"{speaker}: {text}" if speaker else text,
            heading_path=["Transcript", _window_label(int(turn_start // (WINDOW_MINUTES * 60)))],
        )
        for turn_start, speaker, text in turns
    ]
