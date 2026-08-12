from __future__ import annotations

from typing import Optional
from pydantic import BaseModel, Field


class Segment(BaseModel):
    text: str
    ruby: Optional[str] = None


class AnnotatedLine(BaseModel):
    source: str
    segments: list[Segment]


class AnnotateRequest(BaseModel):
    text: str


class AnnotateResponse(BaseModel):
    lines: list[AnnotatedLine]


class DocumentMeta(BaseModel):
    title: str = ""
    artist: str = ""
    year: str = ""


class ExportDocxRequest(BaseModel):
    meta: DocumentMeta = Field(default_factory=DocumentMeta)
    lines: list[AnnotatedLine]


class OverrideCreate(BaseModel):
    surface: str = Field(min_length=1)
    reading: str = Field(min_length=1)
    context: str = ""


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
