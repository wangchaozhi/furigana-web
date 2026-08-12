from __future__ import annotations

from collections import defaultdict

from sudachipy import dictionary, tokenizer

from ..models import AnnotatedLine, OverrideItem, Segment
from .aligner import align_surface_reading, contains_kanji, normalize_reading


class SudachiAnnotator:
    def __init__(self) -> None:
        self._tokenizer = dictionary.Dictionary().create()
        self._mode = tokenizer.Tokenizer.SplitMode.C

    @staticmethod
    def _override_map(overrides: list[OverrideItem]) -> dict[str, list[OverrideItem]]:
        by_surface: dict[str, list[OverrideItem]] = defaultdict(list)
        for item in overrides:
            by_surface[item.surface].append(item)
        for items in by_surface.values():
            items.sort(key=lambda x: len(x.context), reverse=True)
        return by_surface

    @staticmethod
    def _find_override(surface: str, line: str, mapping: dict[str, list[OverrideItem]]) -> str | None:
        for item in mapping.get(surface, []):
            if not item.context or item.context in line:
                return normalize_reading(item.reading)
        return None

    def annotate(self, text: str, overrides: list[OverrideItem]) -> list[AnnotatedLine]:
        override_map = self._override_map(overrides)
        lines: list[AnnotatedLine] = []
        # split("\n") preserves intentionally empty lines and trailing blank lines.
        for source_line in text.replace("\r\n", "\n").replace("\r", "\n").split("\n"):
            segments: list[Segment] = []
            morphemes = self._tokenizer.tokenize(source_line, self._mode) if source_line else []
            cursor = 0

            for m in morphemes:
                surface = m.surface()
                try:
                    begin = int(m.begin())
                    end = int(m.end())
                except Exception:
                    begin = cursor
                    end = cursor + len(surface)

                if begin > cursor:
                    segments.append(Segment(text=source_line[cursor:begin]))

                if contains_kanji(surface):
                    reading = self._find_override(surface, source_line, override_map)
                    if reading is None:
                        reading = m.reading_form() or surface
                    token_segments = align_surface_reading(surface, reading)
                    # UI edits operate on the final Kanji segment (e.g. 白 inside 白い),
                    # while Sudachi overrides above operate on a whole morpheme. Apply
                    # segment-level rules as a second pass so both forms are supported.
                    for seg in token_segments:
                        if seg.ruby:
                            segment_override = self._find_override(seg.text, source_line, override_map)
                            if segment_override is not None:
                                seg.ruby = segment_override
                    segments.extend(token_segments)
                else:
                    segments.append(Segment(text=surface))
                cursor = end

            if cursor < len(source_line):
                segments.append(Segment(text=source_line[cursor:]))

            if not source_line:
                segments = []

            lines.append(AnnotatedLine(source=source_line, segments=segments))
        return lines
