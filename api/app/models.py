from __future__ import annotations

from typing import Annotated, Literal, Optional
from pydantic import BaseModel, Field, field_validator

MAX_TEXT_LENGTH = 100_000
MAX_DOCUMENT_LINES = 5_000
MAX_SEGMENTS_PER_LINE = 2_000
ReadingCandidate = Annotated[str, Field(max_length=500)]


class Segment(BaseModel):
    text: str = Field(max_length=5_000)
    ruby: Optional[str] = Field(default=None, max_length=500)
    candidates: list[ReadingCandidate] = Field(default_factory=list, max_length=50)
    confidence: Optional[Literal["high", "medium", "low"]] = None


class AnnotatedLine(BaseModel):
    source: str = Field(max_length=10_000)
    segments: list[Segment] = Field(max_length=MAX_SEGMENTS_PER_LINE)
    translation: str = Field(default="", max_length=10_000)


class AnnotateRequest(BaseModel):
    text: str = Field(min_length=1, max_length=MAX_TEXT_LENGTH)
    project_id: Optional[int] = None


class AnnotateResponse(BaseModel):
    lines: list[AnnotatedLine]


class LyricsSearchResult(BaseModel):
    id: int
    track_name: str
    artist_name: str = ""
    album_name: str = ""
    duration: float = 0
    plain_lyrics: str
    has_synced_lyrics: bool = False


class LyricsSearchResponse(BaseModel):
    results: list[LyricsSearchResult]


class DocumentMeta(BaseModel):
    title: str = Field(default="", max_length=300)
    artist: str = Field(default="", max_length=300)
    year: str = Field(default="", max_length=50)


class LayoutSettings(BaseModel):
    font_size: int = Field(default=18, ge=12, le=32)
    line_spacing: float = Field(default=2.5, ge=1.2, le=4)
    ruby_scale: float = Field(default=0.55, ge=0.35, le=0.9)
    page_margin: int = Field(default=56, ge=16, le=96)
    font_family: Literal["gothic", "mincho", "system"] = "gothic"
    vertical: bool = False
    columns: Literal[1, 2] = 1
    vertical_row_gap: int = Field(default=24, ge=0, le=160)


class ExportDocxRequest(BaseModel):
    meta: DocumentMeta = Field(default_factory=DocumentMeta)
    layout: LayoutSettings = Field(default_factory=LayoutSettings)
    translation_language: Literal["none", "zh", "en"] = "none"
    lines: list[AnnotatedLine] = Field(max_length=MAX_DOCUMENT_LINES)


class TranslationRequest(BaseModel):
    lines: list[str] = Field(min_length=1, max_length=500)
    target_language: Literal["zh", "en"]
    provider: Literal["azure", "libretranslate", "baidu", "youdao", "google", "deepl", "openai"] = "openai"

    @field_validator("lines")
    @classmethod
    def validate_lines(cls, lines: list[str]) -> list[str]:
        if any(len(line) > 2000 for line in lines):
            raise ValueError("Each line must contain at most 2000 characters")
        if sum(len(line) for line in lines) > 50_000:
            raise ValueError("Translation input must contain at most 50000 characters")
        return lines


class TranslationResponse(BaseModel):
    translations: list[str]


class TranslationStatus(BaseModel):
    enabled: bool
    providers: list[dict[str, str | bool]]


class OverrideCreate(BaseModel):
    surface: str = Field(min_length=1, max_length=200)
    reading: str = Field(min_length=1, max_length=500)
    context: str = Field(default="", max_length=10_000)
    scope: Literal["sentence", "project", "global"] = "sentence"
    project_id: Optional[int] = None


class OverrideItem(OverrideCreate):
    id: int
    created_at: str


class OverrideUpdate(OverrideCreate):
    pass


class ProjectCreate(BaseModel):
    title: str = Field(default="", max_length=300)
    artist: str = Field(default="", max_length=300)
    year: str = Field(default="", max_length=50)
    source_text: str = Field(max_length=MAX_TEXT_LENGTH)
    layout: LayoutSettings = Field(default_factory=LayoutSettings)
    translation_language: Literal["none", "zh", "en"] = "none"
    lines: list[AnnotatedLine] = Field(max_length=MAX_DOCUMENT_LINES)


class ProjectItem(ProjectCreate):
    id: int
    created_at: str
    updated_at: str


class ProjectSummary(BaseModel):
    id: int
    title: str
    artist: str
    year: str
    created_at: str
    updated_at: str
