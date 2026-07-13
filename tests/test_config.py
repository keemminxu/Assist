"""Settings — fail-closed 검증."""
import pytest

from bot.config import ConfigError, Settings

BASE_ENV = {
    "DISCORD_TOKEN": "tok",
    "ASSIST_CHANNEL_ID": "111",
    "DIARY_CHANNEL_ID": "222",
    "ALLOWED_USER_IDS": "42, 7",
    "SUPABASE_URL": "https://desk.supabase.co",
    "SUPABASE_SERVICE_KEY": "desk-key",
    "BLOG_SUPABASE_URL": "https://blog.supabase.co",
    "BLOG_SUPABASE_SERVICE_KEY": "blog-key",
    "GCAL_IDS": "a@gmail.com, fam@group.calendar.google.com",
}


def test_happy_path_parses_everything():
    s = Settings.from_env(BASE_ENV)
    assert s.assist_channel_id == 111
    assert s.diary_channel_id == 222
    assert s.allowed_user_ids == frozenset({42, 7})
    assert s.gcal_ids == ("a@gmail.com", "fam@group.calendar.google.com")
    assert s.claude_model == "sonnet"          # 기본값
    assert s.claude_fallback_model == "haiku"  # 기본값
    assert s.gcal_sa_key == ".gcal-sa.json"    # 기본값
    assert s.weather_lat == pytest.approx(37.57)


def test_empty_allowed_users_refuses_to_boot():
    env = {**BASE_ENV, "ALLOWED_USER_IDS": ""}
    with pytest.raises(ConfigError):
        Settings.from_env(env)


def test_missing_allowed_users_refuses_to_boot():
    env = {k: v for k, v in BASE_ENV.items() if k != "ALLOWED_USER_IDS"}
    with pytest.raises(ConfigError):
        Settings.from_env(env)


def test_missing_required_var_raises_keyerror():
    env = {k: v for k, v in BASE_ENV.items() if k != "DISCORD_TOKEN"}
    with pytest.raises(KeyError):
        Settings.from_env(env)


def test_empty_gcal_ids_refuses_to_boot():
    env = {**BASE_ENV, "GCAL_IDS": " , "}
    with pytest.raises(ConfigError):
        Settings.from_env(env)
