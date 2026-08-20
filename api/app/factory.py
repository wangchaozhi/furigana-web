from __future__ import annotations

import os
import logging
import time
import uuid
from contextlib import asynccontextmanager
from io import BytesIO
from typing import Any
from urllib.parse import quote

from fastapi import Depends, FastAPI, HTTPException, Query, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse

from .analyzer.sudachi import SudachiAnnotator
from .auth import CurrentUser, auth_required, current_user
from .exporters.docx import build_docx
from .lyrics import search_lrclib
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
from .translator import available_providers, get_provider, translate_lines

logger = logging.getLogger("furigana.api")


def create_app(database: Any) -> FastAPI:
    @asynccontextmanager
    async def lifespan(app: FastAPI):
        if os.getenv("SKIP_DB_INIT", "").lower() not in {"1", "true", "yes", "on"}:
            database.init_db()
        app.state.annotator = SudachiAnnotator()
        yield

    app = FastAPI(title="Furigana Web API", version="1.5.0", lifespan=lifespan)
    origins = [x.strip() for x in os.getenv("CORS_ORIGINS", "http://localhost:3000").split(",") if x.strip()]
    origin_regex = os.getenv("CORS_ORIGIN_REGEX") or None
    app.add_middleware(
        CORSMiddleware,
        allow_origins=origins,
        allow_origin_regex=origin_regex,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.middleware("http")
    async def request_observability(request: Request, call_next):
        request_id = request.headers.get("X-Request-ID", "")[:100] or uuid.uuid4().hex
        started = time.perf_counter()
        try:
            response = await call_next(request)
        except Exception:
            logger.exception("request_failed method=%s path=%s request_id=%s", request.method, request.url.path, request_id)
            raise
        duration_ms = (time.perf_counter() - started) * 1000
        response.headers["X-Request-ID"] = request_id
        logger.info(
            "request_completed method=%s path=%s status=%s duration_ms=%.1f request_id=%s",
            request.method,
            request.url.path,
            response.status_code,
            duration_ms,
            request_id,
        )
        return response

    def identified_user(user: CurrentUser = Depends(current_user)) -> CurrentUser:
        database.ensure_user(user.id, user.email)
        return user

    @app.get("/health")
    def health() -> dict[str, str]:
        return {"status": "ok"}

    @app.get("/api/auth/config")
    def auth_config() -> dict[str, bool]:
        return {"required": auth_required()}

    @app.get("/api/auth/me")
    def auth_me(user: CurrentUser = Depends(identified_user)) -> dict[str, str]:
        return {"id": user.id, "email": user.email}

    @app.post("/api/annotate", response_model=AnnotateResponse)
    def annotate(payload: AnnotateRequest, user: CurrentUser = Depends(identified_user)) -> AnnotateResponse:
        overrides = database.list_applicable_overrides(payload.project_id, user.id)
        return AnnotateResponse(lines=app.state.annotator.annotate(payload.text, overrides))

    @app.get("/api/lyrics/search", response_model=LyricsSearchResponse)
    def search_lyrics(
        track: str = Query(min_length=1, max_length=200),
        artist: str = Query(default="", max_length=200),
        _user: CurrentUser = Depends(identified_user),
    ) -> LyricsSearchResponse:
        try:
            return LyricsSearchResponse(results=search_lrclib(track, artist))
        except Exception as error:
            raise HTTPException(status_code=502, detail=f"歌词搜索失败：{error}") from error

    @app.get("/api/translation/status", response_model=TranslationStatus)
    def translation_status(_user: CurrentUser = Depends(identified_user)) -> TranslationStatus:
        providers = available_providers()
        return TranslationStatus(enabled=any(bool(item["configured"]) for item in providers), providers=providers)

    @app.post("/api/translate", response_model=TranslationResponse)
    def translate(payload: TranslationRequest, _user: CurrentUser = Depends(identified_user)) -> TranslationResponse:
        provider = get_provider(payload.provider)
        if not provider.configured:
            raise HTTPException(status_code=503, detail=f"{provider.label} is not configured on the API server.")
        try:
            translations = translate_lines(payload.lines, payload.target_language, payload.provider)
        except Exception as error:
            raise HTTPException(status_code=502, detail=f"Translation failed: {error}") from error
        return TranslationResponse(translations=translations)

    @app.post("/api/export/docx")
    def export_docx(payload: ExportDocxRequest, _user: CurrentUser = Depends(identified_user)):
        content = build_docx(payload)
        filename = (payload.meta.title.strip() or "furigana") + ".docx"
        headers = {"Content-Disposition": f"attachment; filename*=UTF-8''{quote(filename)}"}
        return StreamingResponse(
            BytesIO(content),
            media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            headers=headers,
        )

    @app.get("/api/overrides", response_model=list[OverrideItem])
    def list_overrides(user: CurrentUser = Depends(identified_user)) -> list[OverrideItem]:
        return database.list_overrides(user.id)

    @app.post("/api/overrides", response_model=OverrideItem)
    def create_override(payload: OverrideCreate, user: CurrentUser = Depends(identified_user)) -> OverrideItem:
        try:
            return database.upsert_override(payload, user.id)
        except ValueError as error:
            raise HTTPException(status_code=404, detail=str(error)) from error

    @app.delete("/api/overrides/{override_id}", status_code=204)
    def remove_override(override_id: int, user: CurrentUser = Depends(identified_user)) -> Response:
        if not database.delete_override(override_id, user.id):
            raise HTTPException(status_code=404, detail="Override not found")
        return Response(status_code=204)

    @app.put("/api/overrides/{override_id}", response_model=OverrideItem)
    def edit_override(
        override_id: int,
        payload: OverrideUpdate,
        user: CurrentUser = Depends(identified_user),
    ) -> OverrideItem:
        try:
            item = database.update_override(override_id, payload, user.id)
        except Exception as error:
            raise HTTPException(status_code=409, detail="A rule already exists for this text and context") from error
        if item is None:
            raise HTTPException(status_code=404, detail="Override not found")
        return item

    @app.get("/api/projects", response_model=list[ProjectSummary])
    def list_projects(user: CurrentUser = Depends(identified_user)) -> list[ProjectSummary]:
        return database.list_projects(user.id)

    @app.post("/api/projects", response_model=ProjectItem)
    def save_project(payload: ProjectCreate, user: CurrentUser = Depends(identified_user)) -> ProjectItem:
        return database.save_project(payload, user.id)

    @app.put("/api/projects/{project_id}", response_model=ProjectItem)
    def update_project(
        project_id: int,
        payload: ProjectCreate,
        user: CurrentUser = Depends(identified_user),
    ) -> ProjectItem:
        project = database.update_project(project_id, payload, user.id)
        if project is None:
            raise HTTPException(status_code=404, detail="Project not found")
        return project

    @app.get("/api/projects/{project_id}", response_model=ProjectItem)
    def get_project(project_id: int, user: CurrentUser = Depends(identified_user)) -> ProjectItem:
        project = database.get_project(project_id, user.id)
        if project is None:
            raise HTTPException(status_code=404, detail="Project not found")
        return project

    @app.delete("/api/projects/{project_id}", status_code=204)
    def remove_project(project_id: int, user: CurrentUser = Depends(identified_user)) -> Response:
        if not database.delete_project(project_id, user.id):
            raise HTTPException(status_code=404, detail="Project not found")
        return Response(status_code=204)

    return app
