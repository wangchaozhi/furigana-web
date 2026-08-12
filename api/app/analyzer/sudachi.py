from __future__ import annotations

from collections import defaultdict

from sudachipy import dictionary, tokenizer

from ..models import AnnotatedLine, OverrideItem, Segment
from .aligner import align_surface_reading, contains_kanji, normalize_reading


class SudachiAnnotator:
    def __init__(self) -> None:
        self._dictionary = dictionary.Dictionary()
        self._tokenizer = self._dictionary.create()
        self._mode = tokenizer.Tokenizer.SplitMode.C

    def _lookup_readings(self, surface: str) -> list[str]:
        readings: list[str] = []
        try:
            entries = self._dictionary.lookup(surface)
        except Exception:
            return readings
        for entry in entries:
            reading = normalize_reading(entry.reading_form() or "")
            if reading and reading not in readings:
                readings.append(reading)
        return readings[:8]

    def _attach_candidates(self, surface: str, segments: list[Segment], selected: str, from_rule: bool) -> None:
        readings = [normalize_reading(selected), *self._lookup_readings(surface)]
        aligned_options = [align_surface_reading(surface, reading) for reading in dict.fromkeys(readings)]
        base_shape = [segment.text for segment in segments]
        for index, segment in enumerate(segments):
            if not segment.ruby:
                continue
            candidates = [segment.ruby]
            for option in aligned_options:
                if [part.text for part in option] != base_shape or not option[index].ruby:
                    continue
                candidate = option[index].ruby
                if candidate not in candidates:
                    candidates.append(candidate)
            segment.candidates = candidates
            segment.confidence = "high" if from_rule or len(candidates) == 1 else "medium"

    @staticmethod
    def _override_map(overrides: list[OverrideItem]) -> dict[str, list[OverrideItem]]:
        by_surface: dict[str, list[OverrideItem]] = defaultdict(list)
        for item in overrides:
            by_surface[item.surface].append(item)
        for items in by_surface.values():
            priority = {"sentence": 0, "project": 1, "global": 2}
            items.sort(key=lambda x: (priority[x.scope], -len(x.context)))
        return by_surface

    @staticmethod
    def _find_override(surface: str, line: str, mapping: dict[str, list[OverrideItem]]) -> str | None:
        for item in mapping.get(surface, []):
            if item.scope != "sentence" or item.context in line:
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
                    token_from_rule = reading is not None
                    if reading is None:
                        reading = m.reading_form() or surface
                    token_segments = align_surface_reading(surface, reading)
                    self._attach_candidates(surface, token_segments, reading, token_from_rule)
                    # UI edits operate on the final Kanji segment (e.g. 白 inside 白い),
                    # while Sudachi overrides above operate on a whole morpheme. Apply
                    # segment-level rules as a second pass so both forms are supported.
                    for seg in token_segments:
                        if seg.ruby:
                            segment_override = self._find_override(seg.text, source_line, override_map)
                            if segment_override is not None:
                                seg.ruby = segment_override
                                seg.candidates = [segment_override, *[x for x in seg.candidates if x != segment_override]]
                                seg.confidence = "high"
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
