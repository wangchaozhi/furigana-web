from __future__ import annotations

import os
from contextlib import asynccontextmanager
from io import BytesIO
from urllib.parse import quote

from fastapi import FastAPI, HTTPException, Query, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse

from . import db
from .analyzer.sudachi import SudachiAnnotator
from .exporters.docx import build_docx
from .lyrics import search_lrclib
from .translator import available_providers, get_provider, translate_lines
from .models import (
    AnnotateRequest,
    AnnotateResponse,
    ExportDocxRequest,
    LyricsSearchResponse,
    OverrideCreate,
    OverrideItem,
    OverrideUpdate,
    ProjectCreate,
    ProjectItem,
    ProjectSummary,
    TranslationRequest,
    TranslationResponse,
    TranslationStatus,
)


@asynccontextmanager
async def lifespan(app: FastAPI):
    db.init_db()
    app.state.annotator = SudachiAnnotator()
    yield


app = FastAPI(title="Furigana Web API", version="1.4.1", lifespan=lifespan)

origins = [x.strip() for x in os.getenv("CORS_ORIGINS", "http://localhost:3000").split(",") if x.strip()]
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/api/annotate", response_model=AnnotateResponse)
def annotate(payload: AnnotateRequest) -> AnnotateResponse:
    overrides = db.list_applicable_overrides(payload.project_id)
    lines = app.state.annotator.annotate(payload.text, overrides)
    return AnnotateResponse(lines=lines)


@app.get("/api/lyrics/search", response_model=LyricsSearchResponse)
def search_lyrics(
    track: str = Query(min_length=1, max_length=200),
    artist: str = Query(default="", max_length=200),
) -> LyricsSearchResponse:
    try:
        return LyricsSearchResponse(results=search_lrclib(track, artist))
    except Exception as error:
        raise HTTPException(status_code=502, detail=f"歌词搜索失败：{error}") from error


@app.get("/api/translation/status", response_model=TranslationStatus)
def translation_status() -> TranslationStatus:
    providers = available_providers()
    return TranslationStatus(enabled=any(bool(item["configured"]) for item in providers), providers=providers)


@app.post("/api/translate", response_model=TranslationResponse)
def translate(payload: TranslationRequest) -> TranslationResponse:
    provider = get_provider(payload.provider)
    if not provider.configured:
        raise HTTPException(
            status_code=503,
            detail=f"{provider.label} is not configured on the API server.",
        )
    try:
        translations = translate_lines(payload.lines, payload.target_language, payload.provider)
    except Exception as error:
        raise HTTPException(status_code=502, detail=f"Translation failed: {error}") from error
    return TranslationResponse(translations=translations)


@app.post("/api/export/docx")
def export_docx(payload: ExportDocxRequest):
    content = build_docx(payload)
    filename = (payload.meta.title.strip() or "furigana") + ".docx"
    encoded = quote(filename)
    headers = {"Content-Disposition": f"attachment; filename*=UTF-8''{encoded}"}
    return StreamingResponse(
        BytesIO(content),
        media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        headers=headers,
    )


@app.get("/api/overrides", response_model=list[OverrideItem])
def list_overrides() -> list[OverrideItem]:
    return db.list_overrides()


@app.post("/api/overrides", response_model=OverrideItem)
def create_override(payload: OverrideCreate) -> OverrideItem:
    return db.upsert_override(payload)


@app.delete("/api/overrides/{override_id}", status_code=204)
def remove_override(override_id: int) -> Response:
    if not db.delete_override(override_id):
        raise HTTPException(status_code=404, detail="Override not found")
    return Response(status_code=204)


@app.put("/api/overrides/{override_id}", response_model=OverrideItem)
def edit_override(override_id: int, payload: OverrideUpdate) -> OverrideItem:
    try:
        item = db.update_override(override_id, payload)
    except Exception as error:
        raise HTTPException(status_code=409, detail="A rule already exists for this text and context") from error
    if item is None:
        raise HTTPException(status_code=404, detail="Override not found")
    return item


@app.get("/api/projects", response_model=list[ProjectSummary])
def list_projects() -> list[ProjectSummary]:
    return db.list_projects()


@app.post("/api/projects", response_model=ProjectItem)
def save_project(payload: ProjectCreate) -> ProjectItem:
    return db.save_project(payload)


@app.put("/api/projects/{project_id}", response_model=ProjectItem)
def update_project(project_id: int, payload: ProjectCreate) -> ProjectItem:
    project = db.update_project(project_id, payload)
    if project is None:
        raise HTTPException(status_code=404, detail="Project not found")
    return project


@app.get("/api/projects/{project_id}", response_model=ProjectItem)
def get_project(project_id: int) -> ProjectItem:
    project = db.get_project(project_id)
    if project is None:
        raise HTTPException(status_code=404, detail="Project not found")
    return project


@app.delete("/api/projects/{project_id}", status_code=204)
def remove_project(project_id: int) -> Response:
    if not db.delete_project(project_id):
        raise HTTPException(status_code=404, detail="Project not found")
    return Response(status_code=204)
