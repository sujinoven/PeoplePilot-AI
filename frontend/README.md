# PeoplePilot Frontend

A responsive employee-facing interface for the existing PeoplePilot HR assistant. The frontend and its FastAPI adapter are self-contained in this directory; no existing backend files need to change.

## Run locally

From the project root, ensure the existing `.env` contains a valid `OPENAI_API_KEY`, then run:

```bash
python -m uvicorn frontend.server:app --reload
```

Open <http://127.0.0.1:8000> in a browser. The first real question can take longer because the assistant loads and embeds the employee handbook lazily.

If `uv` cannot access its cache on Windows, use the existing virtual environment directly:

```powershell
.\.venv\Scripts\python.exe -m uvicorn frontend.server:app --reload
```

## What is included

- Responsive desktop and mobile HR assistant interface
- Suggested HR questions and multi-turn conversations
- Browser-local message and session persistence
- A new-conversation control
- Loading, error, retry, message-length, and connectivity states
- Safe response rendering with handbook page links
- Keyboard navigation and reduced-motion support

## Architecture

`frontend.server` serves the static interface and provides a small API adapter. Each generated browser session ID maps to one existing `HRAssistant` instance through `src.sessions.SessionStore`, preserving LangGraph conversation context while the server process is running.

The browser stores only the generated session ID and visible messages in `localStorage`. Restarting the server clears the assistant's in-memory conversation state. Starting a new conversation clears the browser copy and causes the next message to create a fresh server session.

## API

### `GET /api/health`

Returns:

```json
{"status": "ok"}
```

### `POST /api/chat`

Request:

```json
{
  "message": "What is the casual leave policy?",
  "session_id": "optional-existing-session-id"
}
```

Response:

```json
{
  "session_id": "generated-or-existing-session-id",
  "answer": "The assistant response"
}
```

Messages are trimmed, must contain visible text, and cannot exceed 1,000 characters. Session IDs accept letters, numbers, and hyphens and must be 8–64 characters long.

### `GET /handbook`

Opens the existing employee handbook inline. Page citations such as `[Page 18]` are rendered as links to this route.

## Tests

Frontend tests use fake assistants and never call OpenAI:

```bash
uv run pytest frontend/tests -q
```

To run all repository tests:

```bash
uv run pytest tests frontend/tests -q
```

## Troubleshooting

- **Assistant unavailable:** Confirm the frontend server is running and reload the page.
- **A chat request fails:** Check `OPENAI_API_KEY` in `.env`. If LangSmith tracing is enabled, also check `LANGSMITH_API_KEY`.
- **The first answer is slow:** Initial startup builds the in-memory handbook index; later turns reuse it.
- **A refreshed chat has lost context:** The server was probably restarted. Choose **New conversation** to clear the browser's saved transcript and begin a matching server session.
