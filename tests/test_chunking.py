"""chunk_message — 마크다운 줄 경계 분할."""
from bot.discord_bot import chunk_message


def test_short_text_single_chunk():
    assert chunk_message("안녕") == ["안녕"]


def test_empty_text_placeholder():
    assert chunk_message("  \n ") == ["(빈 응답)"]


def test_splits_on_line_boundary():
    text = "\n".join(["A" * 900, "B" * 900, "C" * 900])
    chunks = chunk_message(text, limit=2000)
    assert len(chunks) == 2
    assert chunks[0] == "A" * 900 + "\n" + "B" * 900     # 줄 중간에서 안 자름
    assert chunks[1] == "C" * 900
    assert all(len(c) <= 2000 for c in chunks)


def test_single_long_line_hard_split():
    chunks = chunk_message("X" * 4500, limit=2000)
    assert [len(c) for c in chunks] == [2000, 2000, 500]
