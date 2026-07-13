"""weather.one_liner — MockTransport."""
import asyncio

import httpx

from bot.weather import one_liner

SAMPLE = {
    "current": {"temperature_2m": 28.4, "weather_code": 1},
    "daily": {"temperature_2m_max": [31.2], "temperature_2m_min": [24.1],
              "precipitation_probability_max": [40]},
}


def test_one_liner_formats_korean_summary():
    def handler(request):
        assert request.url.params["latitude"] == "37.57"
        return httpx.Response(200, json=SAMPLE)
    out = asyncio.run(one_liner(37.57, 126.98, transport=httpx.MockTransport(handler)))
    assert out == "대체로 맑음, 지금 28°C (최저 24° / 최고 31°, 강수확률 40%)"


def test_unknown_code_falls_back():
    def handler(request):
        data = {**SAMPLE, "current": {"temperature_2m": 10.0, "weather_code": 999}}
        return httpx.Response(200, json=data)
    out = asyncio.run(one_liner(37.57, 126.98, transport=httpx.MockTransport(handler)))
    assert out.startswith("날씨, 지금 10°C")


def test_null_precipitation_probability():
    def handler(request):
        data = {**SAMPLE, "daily": {**SAMPLE["daily"], "precipitation_probability_max": [None]}}
        return httpx.Response(200, json=data)
    out = asyncio.run(one_liner(37.57, 126.98, transport=httpx.MockTransport(handler)))
    assert "?%" in out and "None" not in out
