"""Conversation API and /chat tests. Router, retrieval and OpenAI are faked; users,
chats and messages are written to the configured DB and deleted after each test."""
import uuid
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient

import app.main as main
from app.auth import SESSION_COOKIE, create_session_token
from app.router import RouteDecision
from config import settings
from db.models import Chunk, User
from db.session import SessionLocal


@pytest.fixture(autouse=True)
def secret(monkeypatch):
    monkeypatch.setattr(settings, "session_secret", "x" * 40)


@pytest.fixture
def make_client():
    created = []

    def _make() -> TestClient:
        with SessionLocal() as db:
            user = User(name="test", google_sub=f"test-{uuid.uuid4()}")
            db.add(user)
            db.commit()
            created.append(user.id)
            client = TestClient(main.app)
            client.cookies.set(SESSION_COOKIE, create_session_token(user.id))
            return client

    yield _make
    with SessionLocal() as db:
        for user_id in created:
            db.delete(db.get(User, user_id))  # ORM delete so chats/messages/logs cascade
        db.commit()


@pytest.fixture
def fake_pipeline(monkeypatch):
    """Answer every question from 2 real chunks, without calling OpenAI."""
    with SessionLocal() as db:
        chunks = db.query(Chunk).filter(Chunk.is_active.is_(True)).limit(2).all()
    state = SimpleNamespace(should_retrieve=True, categories=[], route_calls=[], searched=[], llm_messages=[])

    def fake_route(query, history_text="", summary=None):
        state.route_calls.append({"query": query, "history_text": history_text, "summary": summary})
        return RouteDecision(should_retrieve=state.should_retrieve, category="all", top_k=2,
                             standalone_query=f"standalone: {query}")

    def fake_retrieve(query, top_k, category):
        state.categories.append(category)
        state.searched.append(query)
        return [(chunks[0], 0.9), (chunks[1], 0.5)]

    def fake_create(**kw):
        state.llm_messages.append(kw["messages"])
        return completion

    completion = SimpleNamespace(
        choices=[SimpleNamespace(message=SimpleNamespace(content="answer [1]"))],
        usage=SimpleNamespace(prompt_tokens=100, completion_tokens=20),
    )
    monkeypatch.setattr(main, "route", fake_route)
    monkeypatch.setattr(main, "retrieve", fake_retrieve)
    monkeypatch.setattr(main, "to_context", lambda hits: [])
    monkeypatch.setattr(main.client.chat.completions, "create", fake_create)
    return state


def test_requires_login():
    client = TestClient(main.app)
    assert client.get("/conversations").status_code == 401
    assert client.post("/chat", json={"query": "hi", "category": "part2"}).status_code == 401


def test_chat_creates_chat_in_mode_and_history_reloads(make_client, fake_pipeline):
    client = make_client()
    r = client.post("/chat", json={"query": "value line là gì", "category": "part2"})
    assert r.status_code == 200
    cid = r.json()["conversation_id"]
    client.post("/chat", json={"query": "cho ví dụ", "conversation_id": cid})
    assert fake_pipeline.categories == ["part2", "part2"]  # stored mode is used for retrieval

    part2 = client.get("/conversations", params={"category": "part2"}).json()
    assert [c["id"] for c in part2] == [cid]
    assert part2[0]["title"] == "value line là gì"
    assert client.get("/conversations", params={"category": "writing"}).json() == []

    messages = client.get(f"/conversations/{cid}/messages").json()
    assert [m["role"] for m in messages] == ["user", "assistant", "user", "assistant"]
    assert [s["rank"] for s in messages[1]["sources"]] == [1, 2]
    assert messages[0]["sources"] == []


def test_list_is_ordered_by_last_activity(make_client, fake_pipeline):
    client = make_client()
    first = client.post("/chat", json={"query": "first", "category": "part3"}).json()["conversation_id"]
    second = client.post("/chat", json={"query": "second", "category": "part3"}).json()["conversation_id"]
    client.post("/chat", json={"query": "again", "conversation_id": first})
    ids = [c["id"] for c in client.get("/conversations", params={"category": "part3"}).json()]
    assert ids == [first, second]


def test_new_chat_needs_category_and_mode_must_match(make_client, fake_pipeline):
    client = make_client()
    assert client.post("/chat", json={"query": "q"}).status_code == 400
    cid = client.post("/chat", json={"query": "q", "category": "writing"}).json()["conversation_id"]
    r = client.post("/chat", json={"query": "q", "conversation_id": cid, "category": "part2"})
    assert r.status_code == 400


def test_no_retrieval_path_saves_messages(make_client, fake_pipeline):
    fake_pipeline.should_retrieve = False
    client = make_client()
    cid = client.post("/chat", json={"query": "hello", "category": "part2"}).json()["conversation_id"]
    assert [m["role"] for m in client.get(f"/conversations/{cid}/messages").json()] == ["user", "assistant"]


def test_users_cannot_see_each_others_chats(make_client, fake_pipeline):
    alice, bob = make_client(), make_client()
    cid = alice.post("/chat", json={"query": "secret", "category": "part2"}).json()["conversation_id"]
    assert bob.get("/conversations").json() == []
    assert bob.get(f"/conversations/{cid}/messages").status_code == 404
    assert bob.patch(f"/conversations/{cid}", json={"title": "x"}).status_code == 404
    assert bob.delete(f"/conversations/{cid}").status_code == 404
    assert bob.post("/chat", json={"query": "q", "conversation_id": cid}).status_code == 404


def test_rename_and_delete(make_client, fake_pipeline):
    client = make_client()
    cid = client.post("/chat", json={"query": "q", "category": "part2"}).json()["conversation_id"]
    assert client.patch(f"/conversations/{cid}", json={"title": "Value line notes"}).json()["title"] == "Value line notes"
    assert client.delete(f"/conversations/{cid}").status_code == 204
    assert client.get(f"/conversations/{cid}/messages").status_code == 404


def test_daily_limit(make_client, fake_pipeline, monkeypatch):
    monkeypatch.setattr(settings, "daily_message_limit", 2)
    client = make_client()
    assert client.post("/chat", json={"query": "1", "category": "part2"}).status_code == 200
    assert client.post("/chat", json={"query": "2", "category": "part2"}).status_code == 200
    assert client.post("/chat", json={"query": "3", "category": "part2"}).status_code == 429
