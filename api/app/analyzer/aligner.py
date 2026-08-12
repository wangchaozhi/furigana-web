from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass
from functools import lru_cache

from ..models import Segment

# CJK Unified Ideographs + Extension A + compatibility ideographs, plus common iteration marks.
_KANJI_RE = re.compile(r"[\u3400-\u4DBF\u4E00-\u9FFF\uF900-\uFAFF々〆ヵヶ〇]")
_HIRAGANA_RE = re.compile(r"[\u3040-\u309F]")
_KATAKANA_RE = re.compile(r"[\u30A0-\u30FF\u31F0-\u31FF]")


def contains_kanji(text: str) -> bool:
    return bool(_KANJI_RE.search(text))


def katakana_to_hiragana(text: str) -> str:
    out: list[str] = []
    for ch in text:
        cp = ord(ch)
        # Standard katakana letters map to hiragana by -0x60.
        if 0x30A1 <= cp <= 0x30F6:
            out.append(chr(cp - 0x60))
        else:
            out.append(ch)
    return "".join(out)


def normalize_reading(text: str) -> str:
    return katakana_to_hiragana(unicodedata.normalize("NFKC", text)).strip()


def _is_kana(ch: str) -> bool:
    return bool(_HIRAGANA_RE.fullmatch(ch) or _KATAKANA_RE.fullmatch(ch)) or ch in {"ー", "ゝ", "ゞ", "ヽ", "ヾ"}


def _kind(ch: str) -> str:
    if _KANJI_RE.fullmatch(ch):
        return "kanji"
    if _is_kana(ch):
        return "kana"
    return "other"


@dataclass(frozen=True)
class Group:
    kind: str
    text: str


def _groups(surface: str) -> list[Group]:
    if not surface:
        return []
    result: list[Group] = []
    current_kind = _kind(surface[0])
    buf = [surface[0]]
    for ch in surface[1:]:
        kind = _kind(ch)
        if kind == current_kind:
            buf.append(ch)
        else:
            result.append(Group(current_kind, "".join(buf)))
            current_kind = kind
            buf = [ch]
    result.append(Group(current_kind, "".join(buf)))
    return result


def _merge_plain(segments: list[Segment]) -> list[Segment]:
    merged: list[Segment] = []
    for seg in segments:
        if not seg.text:
            continue
        if merged and not merged[-1].ruby and not seg.ruby:
            merged[-1].text += seg.text
        else:
            merged.append(seg)
    return merged


def align_surface_reading(surface: str, reading: str) -> list[Segment]:
    """Align a Sudachi reading to a surface form and put ruby on Kanji runs only.

    Examples:
      白い / しろい -> [白(しろ), い]
      握り / にぎり -> [握(にぎ), り]
      明日 / あした -> [明日(あした)]
      お茶 / おちゃ -> [お, 茶(ちゃ)]

    The algorithm treats existing kana in the surface as fixed anchors and lets Kanji
    groups capture the reading between them. Tokens are short, so bounded backtracking
    is both simple and fast.
    """
    if not surface:
        return []
    if not contains_kanji(surface):
        return [Segment(text=surface)]

    reading_h = normalize_reading(reading)
    groups = _groups(surface)

    @lru_cache(maxsize=None)
    def solve(group_index: int, reading_index: int):
        if group_index == len(groups):
            return () if reading_index == len(reading_h) else None

        group = groups[group_index]
        if group.kind == "kana":
            literal = normalize_reading(group.text)
            if reading_h.startswith(literal, reading_index):
                tail = solve(group_index + 1, reading_index + len(literal))
                if tail is not None:
                    return ((group.kind, group.text, None),) + tail
            return None

        if group.kind == "other":
            # Most punctuation/ASCII comes as a separate token. If it appears inside a
            # token and also appears in the reading, treat it as a literal anchor.
            literal = normalize_reading(group.text)
            if reading_h.startswith(literal, reading_index):
                tail = solve(group_index + 1, reading_index + len(literal))
                if tail is not None:
                    return ((group.kind, group.text, None),) + tail
            return None

        # Kanji group: capture at least one reading character, leaving enough room for
        # all remaining fixed kana and one character per remaining Kanji group.
        min_remaining = 0
        for later in groups[group_index + 1 :]:
            if later.kind == "kana":
                min_remaining += len(normalize_reading(later.text))
            elif later.kind == "kanji":
                min_remaining += 1
            else:
                min_remaining += len(normalize_reading(later.text))

        max_end = len(reading_h) - min_remaining
        for end in range(reading_index + 1, max_end + 1):
            ruby = reading_h[reading_index:end]
            tail = solve(group_index + 1, end)
            if tail is not None:
                return ((group.kind, group.text, ruby),) + tail
        return None

    solved = solve(0, 0)
    if solved is None:
        # Conservative fallback. If there is exactly one Kanji group, assign the full
        # reading to that group and leave existing kana untouched. If there are multiple
        # Kanji groups we avoid fabricating per-group readings and leave them unannotated.
        kanji_groups = [g for g in groups if g.kind == "kanji"]
        out: list[Segment] = []
        if len(kanji_groups) == 1:
            target = kanji_groups[0]
            for g in groups:
                out.append(Segment(text=g.text, ruby=reading_h if g is target else None))
            return _merge_plain(out)
        return [Segment(text=surface)]

    segments = [Segment(text=text, ruby=ruby) for _, text, ruby in solved]
    return _merge_plain(segments)
