import logging
import re
import uuid

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

from .sessions import SessionStore

log = logging.getLogger("peoplepilot.api")

SESSION_ID = re.compile(r"^[A-Za-z0-9-]{8,64}$")
MAX_MESSAGE_CHARS = 1000


class ChatRequest(BaseModel):
    message: str = Field(min_length=1, max_length=MAX_MESSAGE_CHARS)
    session_id: str | None = None


def _real_assistant():
    # Imported here, not at the top: loading it embeds the handbook, which calls OpenAI.
    from .assistant import HRAssistant

    return HRAssistant()


def create_app(store: SessionStore | None = None) -> FastAPI:
    if store is None:
        store = SessionStore(_real_assistant)
    app = FastAPI(title="PeoplePilot HR Assistant")

    @app.get("/api/health")
    def health():
        return {"status": "ok"}

    @app.post("/api/chat")
    def chat(req: ChatRequest):
        message = req.message.strip()
        if not message:
            raise HTTPException(status_code=422, detail="message must not be empty")
        session_id = req.session_id or uuid.uuid4().hex
        if not SESSION_ID.match(session_id):
            raise HTTPException(status_code=422, detail="invalid session_id")
        try:
            turn = store.get(session_id).ask_detailed(message)
        except Exception:
            log.exception("chat failed")
            raise HTTPException(status_code=502, detail="The assistant could not answer right now. Please try again.")
        return {"session_id": session_id, **turn}

    return app


app = create_app()