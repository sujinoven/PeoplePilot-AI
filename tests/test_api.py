import pytest
from fastapi.testclient import TestClient

from src.api import create_app
from src.sessions import SessionStore


class FakeAssistant:
    def __init__(self):
        self.questions = []

    def ask_detailed(self, question):
        self.questions.append(question)
        return {"answer": f"echo: {question}", "route": "policy_question", "tools_used": [], "pages": [18]}


class BrokenAssistant:
    def ask_detailed(self, question):
        raise RuntimeError("OpenAI is down")


@pytest.fixture
def client():
    return TestClient(create_app(SessionStore(FakeAssistant)))


def test_health(client):
    assert client.get("/api/health").json() == {"status": "ok"}


def test_chat_returns_answer_route_tools_pages_and_a_session_id(client):
    body = client.post("/api/chat", json={"message": "What is the CL policy?"}).json()
    assert body["answer"] == "echo: What is the CL policy?"
    assert body["route"] == "policy_question"
    assert body["tools_used"] == []
    assert body["pages"] == [18]
    assert len(body["session_id"]) >= 8


def test_same_session_id_reuses_the_assistant():
    store = SessionStore(FakeAssistant)
    client = TestClient(create_app(store))
    client.post("/api/chat", json={"message": "one", "session_id": "session-12345"})
    client.post("/api/chat", json={"message": "two", "session_id": "session-12345"})
    assert len(store) == 1
    client.post("/api/chat", json={"message": "three"})
    assert len(store) == 2


def test_the_message_is_trimmed_before_it_reaches_the_assistant():
    store = SessionStore(FakeAssistant)
    client = TestClient(create_app(store))
    client.post("/api/chat", json={"message": "  hello  ", "session_id": "session-12345"})
    assert store.get("session-12345").questions == ["hello"]


@pytest.mark.parametrize("message", ["", "   ", "x" * 1001])
def test_empty_or_too_long_messages_are_rejected(client, message):
    assert client.post("/api/chat", json={"message": message}).status_code == 422


def test_a_malformed_session_id_is_rejected(client):
    r = client.post("/api/chat", json={"message": "hi", "session_id": "../etc/passwd"})
    assert r.status_code == 422


def test_an_assistant_failure_becomes_a_safe_502():
    client = TestClient(create_app(SessionStore(BrokenAssistant)))
    r = client.post("/api/chat", json={"message": "hi"})
    assert r.status_code == 502
    assert "OpenAI" not in r.text