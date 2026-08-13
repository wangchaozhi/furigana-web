from __future__ import annotations

import json
import re
import unicodedata
from typing import Any, Callable
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from .models import LyricsSearchResult


LRCLIB_SEARCH_URL = "https://lrclib.net/api/search"
USER_AGENT = "FuriganaStudio/1.4 (+https://github.com/wangchaozhi/furigana-web)"
_TIMESTAMP = re.compile(r"^(?:\[\d{1,3}:\d{2}(?:\.\d{1,3})?\])+\s*")


def _request_json(url: str, *, timeout: float = 15.0) -> Any:
    try:
        request = Request(url, headers={"User-Agent": USER_AGENT, "Accept": "application/json"})
        with urlopen(request, timeout=timeout) as response:
            return json.loads(response.read())
    except HTTPError as error:
        detail = error.read().decode(errors="replace")[:300]
        raise ValueError(f"LRCLIB returned HTTP {error.code}: {detail}") from error
    except (URLError, TimeoutError) as error:
        raise ValueError(f"Could not connect to LRCLIB: {error}") from error


def _plain_from_synced(value: str) -> str:
    lines = []
    for line in value.replace("\r", "").split("\n"):
        text = _TIMESTAMP.sub("", line).strip()
        if text:
            lines.append(text)
    return "\n".join(lines)


def _clean_text(value: Any) -> str:
    if not isinstance(value, str):
        return ""
    return value.replace("\r\n", "\n").replace("\r", "\n").strip()


def _normalized(value: str) -> str:
    normalized = unicodedata.normalize("NFKC", value).casefold()
    return "".join(character for character in normalized if character.isalnum())


def _score(item: LyricsSearchResult, track: str, artist: str) -> tuple[int, int, float]:
    title = _normalized(item.track_name)
    expected_title = _normalized(track)
    result_artist = _normalized(item.artist_name)
    expected_artist = _normalized(artist)

    score = 0
    if title == expected_title:
        score += 100
    elif expected_title and (expected_title in title or title in expected_title):
        score += 45
    if expected_artist:
        if result_artist == expected_artist:
            score += 70
        elif expected_artist in result_artist or result_artist in expected_artist:
            score += 30
    if item.has_synced_lyrics:
        score += 5
    line_count = len([line for line in item.plain_lyrics.splitlines() if line.strip()])
    score += min(line_count, 40)
    return score, line_count, -abs(item.duration - 240) if item.duration else -9999


def search_lrclib(
    track: str,
    artist: str = "",
    *,
    transport: Callable[..., Any] = _request_json,
) -> list[LyricsSearchResult]:
    params = {"track_name": track.strip()}
    if artist.strip():
        params["artist_name"] = artist.strip()
    payload = transport(f"{LRCLIB_SEARCH_URL}?{urlencode(params)}", timeout=15.0)
    if not isinstance(payload, list):
        raise ValueError("LRCLIB returned an unexpected response")

    results: list[LyricsSearchResult] = []
    for raw in payload[:50]:
        if not isinstance(raw, dict):
            continue
        plain = _clean_text(raw.get("plainLyrics"))
        synced = _clean_text(raw.get("syncedLyrics"))
        if not plain and synced:
            plain = _plain_from_synced(synced)
        if not plain:
            continue
        try:
            results.append(
                LyricsSearchResult(
                    id=int(raw["id"]),
                    track_name=_clean_text(raw.get("trackName")) or track.strip(),
                    artist_name=_clean_text(raw.get("artistName")),
                    album_name=_clean_text(raw.get("albumName")),
                    duration=max(0, float(raw.get("duration") or 0)),
                    plain_lyrics=plain[:100_000],
                    has_synced_lyrics=bool(synced),
                )
            )
        except (KeyError, TypeError, ValueError):
            continue

    results.sort(key=lambda item: _score(item, track, artist), reverse=True)
    return results[:10]
