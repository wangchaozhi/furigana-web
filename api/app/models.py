from __future__ import annotations

from typing import Literal, Optional
from pydantic import BaseModel, Field


class Segment(BaseModel):
    text: str
    ruby: Optional[str] = None


class AnnotatedLine(BaseModel):
    source: str
    segments: list[Segment]


class AnnotateRequest(BaseModel):
    text: str
    project_id: Optional[int] = None


class AnnotateResponse(BaseModel):
    lines: list[AnnotatedLine]


class DocumentMeta(BaseModel):
    title: str = ""
    artist: str = ""
    year: str = ""


class LayoutSettings(BaseModel):
    font_size: int = Field(default=18, ge=12, le=32)
    line_spacing: float = Field(default=2.5, ge=1.2, le=4)
    ruby_scale: float = Field(default=0.55, ge=0.35, le=0.9)
    page_margin: int = Field(default=56, ge=16, le=96)
    font_family: Literal["gothic", "mincho", "system"] = "gothic"
    vertical: bool = False


class ExportDocxRequest(BaseModel):
    meta: DocumentMeta = Field(default_factory=DocumentMeta)
    layout: LayoutSettings = Field(default_factory=LayoutSettings)
    lines: list[AnnotatedLine]


class OverrideCreate(BaseModel):
    surface: str = Field(min_length=1)
    reading: str = Field(min_length=1)
    context: str = ""
    scope: Literal["sentence", "project", "global"] = "sentence"
    project_id: Optional[int] = None


class OverrideItem(OverrideCreate):
    id: int
    created_at: str


class OverrideUpdate(OverrideCreate):
    pass


class ProjectCreate(BaseModel):
    title: str = ""
    artist: str = ""
    year: str = ""
    source_text: str
    layout: LayoutSettings = Field(default_factory=LayoutSettings)
    lines: list[AnnotatedLine]


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
