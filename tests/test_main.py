"""main 조립 부품 — options factory가 페르소나·allowlist를 실제로 적용하는지 검증."""
from bot.main import make_options_factory


def test_options_factory_applies_persona_allowlist_and_server():
    factory = make_options_factory({"marker": "srv"}, "무슨 페르소나", ["mcp__assist__muse_post"])
    opts = factory("sonnet")
    assert opts.system_prompt == "무슨 페르소나"
    assert opts.allowed_tools == ["mcp__assist__muse_post"]
    assert opts.mcp_servers == {"assist": {"marker": "srv"}}
    assert opts.model == "sonnet"
    assert opts.permission_mode == "dontAsk"
