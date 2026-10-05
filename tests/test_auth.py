"""Login flow tests. Google's token check is faked; users are written to the
configured DB (DATABASE_URL) and deleted after each test."""
import uuid
from datetime import datetime, timedelta, timezone

import jwt
import pytest
from fastapi.testclient import TestClient

import app.auth as auth
from app.main import app
from config import settings
from db.models import User
from db.session import SessionLocal

SECRET = "x" * 40


@pytest.fixture
def configured(monkeypatch):
    monkeypatch.setattr(settings, "google_client_id", "test-client-id")
    monkeypatch.setattr(settings, "session_secret", SECRET)


@pytest.fixture
def google_sub():
    sub = f"test-{uuid.uuid4()}"
    yield sub
    with SessionLocal() as db:
        db.query(User).filter(User.google_sub == sub).delete()
        db.commit()


def fake_google(monkeypatch, claims):
    def verify(credential, request, audience):
        assert audience == "test-client-id"
        if credential != "good-token":
            raise ValueError("bad token")
        return claims

    monkeypatch.setattr(auth.id_token, "verify_oauth2_token", verify)


def test_session_token_roundtrip(configured):
    assert auth.read_session_token(auth.create_session_token(42)) == 42


def test_session_token_rejects_tampered_and_expired(configured):
    token = auth.create_session_token(42)
    assert auth.read_session_token(token[:-2] + "xx") is None
    expired = jwt.encode(
        {"sub": "42", "exp": datetime.now(timezone.utc) - timedelta(seconds=1)}, SECRET, algorithm="HS256"
    )
    assert auth.read_session_token(expired) is None


def test_login_not_configured_returns_503(monkeypatch):
    monkeypatch.setattr(settings, "google_client_id", "")
    r = TestClient(app).post("/auth/google", json={"credential": "anything"})
    assert r.status_code == 503


def test_me_requires_login(configured):
    assert TestClient(app).get("/me").status_code == 401


def test_invalid_google_credential(configured, monkeypatch, google_sub):
    fake_google(monkeypatch, {"sub": google_sub, "email_verified": True})
    assert TestClient(app).post("/auth/google", json={"credential": "bad"}).status_code == 401


def test_unverified_email_rejected(configured, monkeypatch, google_sub):
    fake_google(monkeypatch, {"sub": google_sub, "email": "a@b.c", "email_verified": False})
    assert TestClient(app).post("/auth/google", json={"credential": "good-token"}).status_code == 401


def test_login_me_logout(configured, monkeypatch, google_sub):
    claims = {"sub": google_sub, "email": "student@example.com", "email_verified": True,
              "name": "Student One", "picture": "https://example.com/a.png"}
    fake_google(monkeypatch, claims)
    client = TestClient(app)

    r = client.post("/auth/google", json={"credential": "good-token"})
    assert r.status_code == 200
    assert "httponly" in r.headers["set-cookie"].lower()
    user_id = r.json()["id"]
    assert client.get("/me").json() == {
        "id": user_id, "name": "Student One", "email": "student@example.com",
        "avatar_url": "https://example.com/a.png",
    }

    # Logging in again updates the profile instead of creating a second user.
    claims["name"] = "Student Renamed"
    assert client.post("/auth/google", json={"credential": "good-token"}).json()["id"] == user_id
    assert client.get("/me").json()["name"] == "Student Renamed"
    with SessionLocal() as db:
        assert db.query(User).filter(User.google_sub == google_sub).count() == 1

    assert client.post("/auth/logout").status_code == 204
    assert client.get("/me").status_code == 401
