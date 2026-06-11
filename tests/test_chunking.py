from bot.discord_bot import chunk_message


def test_short_text_is_single_chunk():
    assert chunk_message("안녕") == ["안녕"]


def test_long_text_splits_at_2000():
    chunks = chunk_message("a" * 4500)
    assert [len(c) for c in chunks] == [2000, 2000, 500]


def test_empty_text_becomes_placeholder():
    assert chunk_message("") == ["(빈 응답)"]
    assert chunk_message("   ") == ["(빈 응답)"]
