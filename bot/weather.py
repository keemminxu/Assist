"""open-meteo 현재 날씨 1줄 (결정적 — LLM 웹검색을 안 거친다)."""
from __future__ import annotations

import httpx

_WMO = {
    0: "맑음", 1: "대체로 맑음", 2: "구름 조금", 3: "흐림",
    45: "안개", 48: "서리 안개",
    51: "이슬비", 53: "이슬비", 55: "이슬비",
    61: "비", 63: "비", 65: "강한 비",
    66: "얼어붙는 비", 67: "얼어붙는 비",
    71: "눈", 73: "눈", 75: "폭설", 77: "싸락눈",
    80: "소나기", 81: "소나기", 82: "강한 소나기",
    85: "소낙눈", 86: "소낙눈",
    95: "뇌우", 96: "뇌우(우박)", 99: "뇌우(우박)",
}


async def one_liner(lat: float, lon: float, transport=None) -> str:
    async with httpx.AsyncClient(timeout=10.0, transport=transport) as c:
        resp = await c.get("https://api.open-meteo.com/v1/forecast", params={
            "latitude": lat, "longitude": lon,
            "current": "temperature_2m,weather_code",
            "daily": "temperature_2m_max,temperature_2m_min,precipitation_probability_max",
            "timezone": "Asia/Seoul", "forecast_days": 1,
        })
        resp.raise_for_status()
        d = resp.json()
    cur, day = d["current"], d["daily"]
    desc = _WMO.get(cur["weather_code"], "날씨")
    prob = day["precipitation_probability_max"][0]
    prob_txt = "?" if prob is None else f"{prob}"
    return (f"{desc}, 지금 {cur['temperature_2m']:.0f}°C "
            f"(최저 {day['temperature_2m_min'][0]:.0f}° / 최고 {day['temperature_2m_max'][0]:.0f}°, "
            f"강수확률 {prob_txt}%)")
