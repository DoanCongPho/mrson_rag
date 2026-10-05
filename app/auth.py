from datetime import datetime, timedelta, timezone

import jwt
from fastapi import APIRouter, Depends, HTTPException, Request, Response
from google.auth.transport import requests as google_requests
from google.oauth2 import id_token
from pydantic import BaseModel
from sqlalchemy.orm import Session

from config import settings
from db.models import User
from db.session import get_db

SESSION_COOKIE = "mrson_session"
JWT_ALGORITHM = "HS256"
MIN_SECRET_LENGTH = 32

router = APIRouter()

# Reused across requests so Google's public certificates are fetched over one session.
_google_request = google_requests.Request()


class GoogleLoginRequest(BaseModel):
    credential: str


class UserOut(BaseModel):
    id: int
    name: str
    email: str | None = None
    avatar_url: str | None = None


def _require_auth_config() -> None:
    if not settings.google_client_id or len(settings.session_secret) < MIN_SECRET_LENGTH:
        raise HTTPException(
            status_code=503,
            detail="Login is not configured (GOOGLE_CLIENT_ID / SESSION_SECRET)",
        )


def create_session_token(user_id: int) -> str:
    now = datetime.now(timezone.utc)
    payload = {"sub": str(user_id), "iat": now, "exp": now + timedelta(days=settings.session_days)}
    return jwt.encode(payload, settings.session_secret, algorithm=JWT_ALGORITHM)


def read_session_token(token: str) -> int | None:
    try:
        payload = jwt.decode(token, settings.session_secret, algorithms=[JWT_ALGORITHM])
        return int(payload["sub"])
    except (jwt.InvalidTokenError, KeyError, ValueError):
        return None


def _set_session_cookie(response: Response, user_id: int) -> None:
    response.set_cookie(
        SESSION_COOKIE,
        create_session_token(user_id),
        max_age=settings.session_days * 24 * 3600,
        httponly=True,
        samesite="lax",
        secure=settings.cookie_secure,
    )


def get_current_user(request: Request, db: Session = Depends(get_db)) -> User:
    token = request.cookies.get(SESSION_COOKIE)
    user_id = read_session_token(token) if token and settings.session_secret else None
    user = db.get(User, user_id) if user_id is not None else None
    if user is None:
        raise HTTPException(status_code=401, detail="Not logged in")
    return user


def _to_user_out(user: User) -> UserOut:
    return UserOut(id=user.id, name=user.name, email=user.email, avatar_url=user.avatar_url)


@router.post("/auth/google", response_model=UserOut)
def login_with_google(body: GoogleLoginRequest, response: Response, db: Session = Depends(get_db)):
    _require_auth_config()
    try:
        claims = id_token.verify_oauth2_token(body.credential, _google_request, settings.google_client_id)
    except ValueError as exc:
        raise HTTPException(status_code=401, detail="Invalid Google credential") from exc
    if not claims.get("email_verified", False):
        raise HTTPException(status_code=401, detail="Google email is not verified")

    user = db.query(User).filter(User.google_sub == claims["sub"]).first()
    if user is None:
        user = User(google_sub=claims["sub"])
        db.add(user)
    # Refresh profile fields on every login so name/avatar changes on Google show up.
    user.name = (claims.get("name") or claims.get("email") or "User")[:50]
    user.email = claims.get("email")
    user.avatar_url = claims.get("picture")
    db.commit()

    _set_session_cookie(response, user.id)
    return _to_user_out(user)


@router.post("/auth/logout", status_code=204)
def logout(response: Response):
    response.delete_cookie(SESSION_COOKIE, httponly=True, samesite="lax", secure=settings.cookie_secure)


@router.get("/me", response_model=UserOut)
def me(user: User = Depends(get_current_user)):
    return _to_user_out(user)
