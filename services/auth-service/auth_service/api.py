"""
Auth service FastAPI router.

Endpoints:
  POST /auth/register   — create account
  POST /auth/login      — exchange credentials for JWT
  POST /auth/link       — link an external platform account
  GET  /auth/me         — return current user info
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel, EmailStr

from .jwt import create_access_token, decode_access_token
from .linked_accounts import Platform

router = APIRouter(prefix="/auth", tags=["auth"])
bearer = HTTPBearer()


# ---------------------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------------------

class RegisterIn(BaseModel):
    email: EmailStr
    password: str
    display_name: str


class LoginIn(BaseModel):
    email: EmailStr
    password: str


class TokenOut(BaseModel):
    access_token: str
    token_type: str = "bearer"


class LinkAccountIn(BaseModel):
    platform: Platform
    external_identifier: str
    credential: str


# ---------------------------------------------------------------------------
# Routes (stubs)
# ---------------------------------------------------------------------------

@router.post("/register", response_model=TokenOut, status_code=status.HTTP_201_CREATED)
async def register(body: RegisterIn) -> TokenOut:
    # TODO: hash password, create user in DB, issue token
    raise HTTPException(status_code=501, detail="Not yet implemented")


@router.post("/login", response_model=TokenOut)
async def login(body: LoginIn) -> TokenOut:
    # TODO: verify credentials, issue token
    raise HTTPException(status_code=501, detail="Not yet implemented")


@router.post("/link")
async def link_account(
    body: LinkAccountIn,
    creds: HTTPAuthorizationCredentials = Depends(bearer),
) -> dict:
    # TODO: verify JWT, verify external credential, store linked account
    raise HTTPException(status_code=501, detail="Not yet implemented")


@router.get("/me")
async def get_me(creds: HTTPAuthorizationCredentials = Depends(bearer)) -> dict:
    try:
        payload = decode_access_token(creds.credentials)
    except Exception:
        raise HTTPException(status_code=401, detail="Invalid or expired token")
    # TODO: fetch full user record from DB
    return {"user_id": payload.get("sub")}
