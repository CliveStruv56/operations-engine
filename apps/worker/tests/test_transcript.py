"""WebVTT → speaker turns under time-window headings.

Recorded shapes: Teams/Meet voice tags, Zoom's plain `Name:` prefixes, and
the rolling captions some exporters emit. The contract that matters
downstream: every block says who spoke, and its heading path says roughly
when — which is what the chunker prepends to every retrieved excerpt.
"""

from worker.chunking import chunk_blocks
from worker.transcript import parse_vtt

TEAMS_VTT = """﻿WEBVTT

NOTE duration:"00:21:00"

1
00:00:01.000 --> 00:00:04.000
<v Sarah Fry>Morning everyone, shall we make a start?</v>

2
00:00:04.500 --> 00:00:08.000
<v Sarah Fry>The main item is the <i>budget</i> for the hall.</v>

3
00:00:08.500 --> 00:00:12.000
<v Ade Okafor>The roof quote came in at forty-two thousand.</v>

4
00:11:02.000 --> 00:11:06.000 align:start position:0%
<v Sarah Fry>Moving on to the funding application.</v>
"""

ZOOM_VTT = """WEBVTT

00:00:00.000 --> 00:00:03.000
Morag Dunn: Can everyone see my screen?

00:00:03.500 --> 00:00:06.000
Morag Dunn: Can everyone see my screen? Good, let's begin.

00:00:06.500 --> 00:00:09.000
At 12:30 we break for lunch.
"""


def test_teams_voice_tags_become_speaker_turns():
    blocks = parse_vtt(TEAMS_VTT)
    assert [b.text for b in blocks] == [
        "Sarah Fry: Morning everyone, shall we make a start?"
        " The main item is the budget for the hall.",
        "Ade Okafor: The roof quote came in at forty-two thousand.",
        "Sarah Fry: Moving on to the funding application.",
    ]


def test_turns_carry_ten_minute_window_headings():
    blocks = parse_vtt(TEAMS_VTT)
    assert blocks[0].heading_path == ["Transcript", "0:00–0:10"]
    assert blocks[1].heading_path == ["Transcript", "0:00–0:10"]
    # The 11-minute cue lands in the second window, so retrieval can answer
    # "when did we discuss the funding application" with a neighbourhood.
    assert blocks[2].heading_path == ["Transcript", "0:10–0:20"]


def test_zoom_prefixes_and_rolling_captions():
    blocks = parse_vtt(ZOOM_VTT)
    # The second cue re-sends the first's words with more appended — merged,
    # not repeated. A line opening with a clock time is not a speaker.
    assert [b.text for b in blocks] == [
        "Morag Dunn: Can everyone see my screen? Good, let's begin.",
        "At 12:30 we break for lunch.",
    ]


def test_chunks_arrive_time_anchored():
    chunks = chunk_blocks(parse_vtt(TEAMS_VTT), target_tokens=600, overlap_ratio=0.15)
    assert chunks, "a transcript must produce retrievable chunks"
    assert chunks[0].heading_path == ["Transcript", "0:00–0:10"]
    assert "Sarah Fry:" in chunks[0].content


def test_garbage_in_nothing_out():
    assert parse_vtt("") == []
    assert parse_vtt("not a transcript at all\njust prose\n") == []
