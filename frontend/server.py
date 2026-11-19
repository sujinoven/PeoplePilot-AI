"""FastAPI entrypoint for the PeoplePilot web experience.

This module intentionally lives beside the existing application instead of
changing it. Run it with:

    uv run uvicorn frontend.server:app --reload
"""

from __future__ import annotations

import logging
import re
import uuid
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from src.sessions import SessionStore


log = logging.getLogger("peoplepilot.frontend")

BASE_DIR = Path(__file__).resolve().parent
PROJECT_DIR = BASE_DIR.parent
STATIC_DIR = BASE_DIR / "static"
HANDBOOK_PATH = PROJECT_DIR / "data" / "Employee_Handbook.pdf"

SESSION_ID_PATTERN = re.compile(r"^[A-Za-z0-9-]{8,64}$")
MAX_MESSAGE_CHARS = 1000


class ChatRequest(BaseModel):
    """A single browser chat turn."""

    message: str = Field(min_length=1, max_length=MAX_MESSAGE_CHARS)
    session_id: str | None = None


def _create_assistant():
    """Load the model and handbook only when the first chat request arrives."""

    from src.assistant import HRAssistant

    return HRAssistant()


def create_app(store: SessionStore | None = None) -> FastAPI:
    """Create the frontend app, optionally with an injected test session store."""

    session_store = store if store is not None else SessionStore(_create_assistant)
    web_app = FastAPI(
        title="PeoplePilot HR Assistant",
        description="Employee-facing web experience for the PeoplePilot assistant.",
        docs_url=None,
        redoc_url=None,
    )
    web_app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")

    @web_app.get("/", include_in_schema=False)
    def index() -> FileResponse:
        return FileResponse(STATIC_DIR / "index.html")

    @web_app.get("/api/health")
    def health() -> dict[str, str]:
        return {"status": "ok"}

    @web_app.post("/api/chat")
    def chat(request: ChatRequest) -> dict[str, str]:
        message = request.message.strip()
        if not message:
            raise HTTPException(status_code=422, detail="message must not be empty")

        session_id = request.session_id or uuid.uuid4().hex
        if not SESSION_ID_PATTERN.fullmatch(session_id):
            raise HTTPException(status_code=422, detail="invalid session_id")

        try:
            answer = session_store.get(session_id).ask(message)
        except Exception:
            log.exception("frontend chat failed")
            raise HTTPException(
                status_code=502,
                detail="The assistant could not answer right now. Please try again.",
            ) from None

        return {"session_id": session_id, "answer": answer}

    @web_app.get("/handbook", include_in_schema=False)
    def handbook() -> FileResponse:
        if not HANDBOOK_PATH.is_file():
            raise HTTPException(status_code=404, detail="Employee handbook not found")
        return FileResponse(
            HANDBOOK_PATH,
            media_type="application/pdf",
            filename="Employee_Handbook.pdf",
            content_disposition_type="inline",
        )

    return web_app


app = create_app()
