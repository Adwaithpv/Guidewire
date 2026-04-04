"""
News-based closure *pricing* signal (bandhs, curfews, hartals, strikes).

Does not authorize payouts by itself — claims still require a verified parametric
event for the worker's zone (e.g. /events/ingest/closure). Uses GNews when
GNEWS_API_KEY is set; otherwise a stable low baseline.
"""
from __future__ import annotations

import logging
import os
import re
from datetime import datetime, timedelta, timezone
from typing import Any

import httpx

log = logging.getLogger(__name__)

GNEWS_KEY = (os.getenv("GNEWS_API_KEY") or "").strip()
GNEWS_SEARCH = "https://gnews.io/api/v4/search"

# Match article text to worker geography (city + common aliases + state for regional bandhs)
_CITY_GEO_TOKENS: dict[str, list[str]] = {
    "Mumbai": ["mumbai", "bombay", "maharashtra", "thane", "navi mumbai"],
    "Delhi": ["delhi", "new delhi", "ncr", "gurgaon", "gurugram", "noida", "ghaziabad"],
    "Bengaluru": ["bengaluru", "bangalore", "karnataka"],
    "Chennai": ["chennai", "madras", "tamil nadu", "tamilnadu"],
    "Kolkata": ["kolkata", "calcutta", "west bengal"],
    "Hyderabad": ["hyderabad", "telangana", "secunderabad"],
    "Pune": ["pune", "maharashtra", "pimpri"],
    "Ahmedabad": ["ahmedabad", "gujarat", "gandhinagar"],
    "Jaipur": ["jaipur", "rajasthan"],
    "Lucknow": ["lucknow", "uttar pradesh", "up bandh"],
}

_DISRUPTION_TERMS = (
    "bandh",
    "hartal",
    "curfew",
    "section 144",
    "section-144",
    "144 imposed",
    "indefinite strike",
    "trade union strike",
    "shutdown",
    "roads closed",
    "road blocked",
    "market shut",
    "shops closed",
    "internet suspended",
    "mobile internet",
    "metro closed",
    "dm orders",
    "district magistrate",
    "prohibitory orders",
    "strike hits",
    "transport strike",
)


def _geo_tokens_for_city(city: str) -> list[str]:
    tokens = _CITY_GEO_TOKENS.get(
        city,
        [city.lower(), re.sub(r"\s+", " ", city.lower())],
    )
    return list(dict.fromkeys(t.lower() for t in tokens))


def _text_matches_geo(text: str, geo_tokens: list[str]) -> bool:
    t = text.lower()
    return any(tok in t for tok in geo_tokens)


def _text_has_disruption(text: str) -> bool:
    t = text.lower()
    return any(term in t for term in _DISRUPTION_TERMS)


def _mock_closure(city: str) -> dict[str, Any]:
    return {
        "source": "mock",
        "closure_risk": 0.06,
        "articles_matched": 0,
        "headlines": [],
        "query_used": None,
    }


async def get_closure_signal_from_news(city: str) -> dict[str, Any]:
    """
    Return closure_risk in [0,1] and evidence from recent India news for this city/region.
    """
    if not GNEWS_KEY:
        log.info("No GNEWS_API_KEY — using mock closure signal for %s", city)
        return _mock_closure(city)

    geo = _geo_tokens_for_city(city)
    # Broad India search; we require city/state + disruption terms in the headline/body locally.
    q = 'bandh OR hartal OR curfew OR "section 144" OR shutdown OR strike'
    params = {
        "q": q,
        "lang": "en",
        "country": "in",
        "max": 20,
        "from": (datetime.now(timezone.utc) - timedelta(days=3)).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "apikey": GNEWS_KEY,
        "sortby": "publishedAt",
    }

    try:
        async with httpx.AsyncClient(timeout=12) as client:
            resp = await client.get(GNEWS_SEARCH, params=params)
            resp.raise_for_status()
            data = resp.json()
    except Exception as exc:
        log.warning("GNews API error for %s: %s — mock closure", city, exc)
        return _mock_closure(city)

    articles = data.get("articles") or []
    matched: list[dict[str, Any]] = []
    for a in articles:
        title = (a.get("title") or "").strip()
        desc = (a.get("description") or "").strip()
        combined = f"{title} {desc}"
        if not _text_has_disruption(combined):
            continue
        if not _text_matches_geo(combined, geo):
            continue
        matched.append(
            {
                "title": title[:200],
                "url": a.get("url"),
                "published_at": a.get("publishedAt"),
            }
        )

    n = len(matched)
    # Pricing-only signal: cap below weather/AQI so headlines do not dominate premiums
    if n == 0:
        closure_risk = 0.05
    elif n == 1:
        closure_risk = 0.10
    elif n == 2:
        closure_risk = 0.14
    elif n <= 4:
        closure_risk = 0.18
    else:
        closure_risk = 0.22

    return {
        "source": "gnews",
        "closure_risk": round(closure_risk, 3),
        "articles_matched": n,
        "headlines": matched[:5],
        "query_used": f"{q} (filtered for {city})",
    }
