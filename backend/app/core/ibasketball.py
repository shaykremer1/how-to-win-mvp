import re
from typing import Any

import requests
from bs4 import BeautifulSoup

from backend.app.services.common import infer_our_side_from_match_name, normalize_team_name

HEADERS = {"User-Agent": "Mozilla/5.0"}


def build_match_url(match_id: int) -> str:
    return f"https://ibasketball.co.il/match/{match_id}/"


def fetch_url(url: str) -> str:
    r = requests.get(url, headers=HEADERS, timeout=30)
    r.raise_for_status()
    return r.text


def _clean_spaces(s: str) -> str:
    return re.sub(r"\s+", " ", str(s or "")).strip()


def _extract_match_name(soup: BeautifulSoup) -> str | None:
    candidates = [
        soup.select_one("h1"),
        soup.select_one("h2"),
        soup.select_one("meta[property='og:title']"),
        soup.select_one("title"),
    ]
    for c in candidates:
        if c is None:
            continue
        if c.name == "meta":
            text = _clean_spaces(c.attrs.get("content", ""))
        else:
            text = _clean_spaces(c.get_text(" ", strip=True))
        if "נגד" in text:
            return text
    full_text = _clean_spaces(" ".join(soup.stripped_strings))
    m = re.search(r"([^\n|]{2,80}\sנגד\s[^\n|]{2,80})", full_text)
    return _clean_spaces(m.group(1)) if m else None


def extract_match_metadata(match_id: int) -> dict[str, Any]:
    html = fetch_url(build_match_url(match_id))
    soup = BeautifulSoup(html, "html.parser")

    match_name = _extract_match_name(soup) or ""
    our_side = infer_our_side_from_match_name(match_name)

    home_team = None
    away_team = None
    if "נגד" in match_name:
        left, right = [normalize_team_name(x) for x in match_name.split("נגד", 1)]
        home_team, away_team = left, right

    return {
        "match_name": match_name,
        "our_side": our_side,
        "home_team": home_team,
        "away_team": away_team,
    }
