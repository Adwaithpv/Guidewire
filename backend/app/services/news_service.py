"""
News-based closure *pricing* signal (bandhs, curfews, hartals, strikes).

Tries NewsData.io first, then GNews, then a stable mock baseline.
Does not authorize payouts — claims still require verified zone events.
"""
from __future__ import annotations

import logging
import os
import re
from datetime import datetime, timedelta, timezone
from typing import Any

import httpx

log = logging.getLogger(__name__)

NEWSDATA_KEY = (os.getenv("NEWSDATA_API_KEY") or "").strip()
GNEWS_KEY = (os.getenv("GNEWS_API_KEY") or "").strip()

NEWSDATA_LATEST = "https://newsdata.io/api/1/latest"
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

_SEARCH_Q = "bandh OR curfew OR hartal OR strike OR shutdown OR section 144"


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


def _closure_risk_from_match_count(n: int) -> float:
    if n == 0:
        return 0.05
    if n == 1:
        return 0.10
    if n == 2:
        return 0.14
    if n <= 4:
        return 0.18
    return 0.22


def _build_provider_result(
    source: str,
    matched: list[dict[str, Any]],
    query_used: str,
) -> dict[str, Any]:
    n = len(matched)
    return {
        "source": source,
        "closure_risk": round(_closure_risk_from_match_count(n), 3),
        "articles_matched": n,
        "headlines": matched[:5],
        "query_used": query_used,
    }


def _filter_newsdata_results(raw: list[Any], geo: list[str]) -> list[dict[str, Any]]:
    matched: list[dict[str, Any]] = []
    for a in raw:
        if not isinstance(a, dict):
            continue
        title = (a.get("title") or "").strip()
        desc = (a.get("description") or "").strip()
        snippet = (a.get("content") or "")[:500] if a.get("content") else ""
        combined = f"{title} {desc} {snippet}"
        if not _text_has_disruption(combined):
            continue
        if not _text_matches_geo(combined, geo):
            continue
        matched.append(
            {
                "title": title[:200],
                "url": a.get("link"),
                "published_at": a.get("pubDate"),
            }
        )
    return matched


def _filter_gnews_articles(raw: list[Any], geo: list[str]) -> list[dict[str, Any]]:
    matched: list[dict[str, Any]] = []
    for a in raw:
        if not isinstance(a, dict):
            continue
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
    return matched


async def _try_newsdata(city: str, geo: list[str]) -> dict[str, Any] | None:
    if not NEWSDATA_KEY:
        return None
    params: dict[str, str | int] = {
        "apikey": NEWSDATA_KEY,
        "q": _SEARCH_Q,
        "country": "in",
        "language": "en",
        "size": 10,
    }
    try:
        async with httpx.AsyncClient(timeout=12) as client:
            resp = await client.get(NEWSDATA_LATEST, params=params)
            resp.raise_for_status()
            data = resp.json()
    except httpx.HTTPStatusError as exc:
        log.info(
            "NewsData.io HTTP %s for %s — trying GNews or mock next",
            exc.response.status_code,
            city,
        )
        return None
    except Exception as exc:
        log.info("NewsData.io request failed for %s (%s) — trying GNews or mock", city, exc)
        return None

    if data.get("status") != "success":
        log.info(
            "NewsData.io non-success for %s (%s) — trying GNews or mock",
            city,
            data.get("message") or data.get("status"),
        )
        return None

    raw_results = data.get("results") or []
    matched = _filter_newsdata_results(raw_results, geo)
    return _build_provider_result(
        "newsdata",
        matched,
        f"{_SEARCH_Q} (filtered for {city}, country=in)",
    )


async def _try_gnews(city: str, geo: list[str]) -> dict[str, Any] | None:
    if not GNEWS_KEY:
        return None
    params = {
        "q": _SEARCH_Q,
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
    except httpx.HTTPStatusError as exc:
        code = exc.response.status_code
        if code in (401, 403):
            log.info("GNews %s for %s — mock closure fallback", code, city)
        else:
            log.warning("GNews HTTP %s for %s — mock closure", code, city)
        return None
    except Exception as exc:
        log.warning("GNews request failed for %s: %s — mock closure", city, exc)
        return None

    articles = data.get("articles") or []
    matched = _filter_gnews_articles(articles, geo)
    return _build_provider_result(
        "gnews",
        matched,
        f"{_SEARCH_Q} (filtered for {city}, GNews)",
    )


async def get_closure_signal_from_news(city: str) -> dict[str, Any]:
    """
    Return closure_risk in [0,1] and evidence from recent India news for this city/region.
    Order: NewsData.io → GNews → mock.
    """
    geo = _geo_tokens_for_city(city)

    if not NEWSDATA_KEY and not GNEWS_KEY:
        log.info("No NEWSDATA_API_KEY or GNEWS_API_KEY — mock closure for %s", city)
        return _mock_closure(city)

    out = await _try_newsdata(city, geo)
    if out is not None:
        return out

    out = await _try_gnews(city, geo)
    if out is not None:
        log.info("Using GNews closure signal for %s (NewsData unavailable or failed)", city)
        return out

    return _mock_closure(city)
