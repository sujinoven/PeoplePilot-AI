from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from frontend.server import create_app
from src.sessions import SessionStore


class FakeAssistant:
    def __init__(self):
        self.questions = []

    def ask(self, question):
        self.questions.append(question)
        return f"Policy answer for: {question} [Page 18]"


class BrokenAssistant:
    def ask(self, question):
        raise RuntimeError("secret provider failure")


@pytest.fixture
def store():
    return SessionStore(FakeAssistant)


@pytest.fixture
def client(store):
    return TestClient(create_app(store))


def test_home_and_static_assets_are_served(client):
    home = client.get("/")
    assert home.status_code == 200
    assert "PeoplePilot" in home.text
    assert client.get("/static/styles.css").status_code == 200
    assert client.get("/static/app.js").status_code == 200


def test_health_endpoint(client):
    assert client.get("/api/health").json() == {"status": "ok"}


def test_chat_returns_answer_and_session_id(client):
    response = client.post("/api/chat", json={"message": "What is the leave policy?"})
    assert response.status_code == 200
    body = response.json()
    assert body["answer"].endswith("[Page 18]")
    assert len(body["session_id"]) >= 8


def test_same_session_reuses_assistant_and_trims_messages(store):
    client = TestClient(create_app(store))
    session_id = "browser-session-123"
    client.post("/api/chat", json={"message": "  first question  ", "session_id": session_id})
    client.post("/api/chat", json={"message": "follow up", "session_id": session_id})
    assert len(store) == 1
    assert store.get(session_id).questions == ["first question", "follow up"]


@pytest.mark.parametrize("message", ["", "   ", "x" * 1001])
def test_invalid_messages_are_rejected(client, message):
    assert client.post("/api/chat", json={"message": message}).status_code == 422


def test_invalid_session_id_is_rejected(client):
    response = client.post("/api/chat", json={"message": "hello", "session_id": "../unsafe"})
    assert response.status_code == 422


def test_assistant_error_is_safe():
    client = TestClient(create_app(SessionStore(BrokenAssistant)))
    response = client.post("/api/chat", json={"message": "hello"})
    assert response.status_code == 502
    assert "secret provider failure" not in response.text


def test_handbook_is_available(client):
    response = client.get("/handbook")
    assert response.status_code == 200
    assert response.headers["content-type"] == "application/pdf"
    assert response.content.startswith(b"%PDF")


def test_frontend_files_stay_inside_frontend_directory():
    frontend_dir = Path(__file__).resolve().parents[1]
    assert (frontend_dir / "server.py").is_file()
    assert (frontend_dir / "static" / "index.html").is_file()
