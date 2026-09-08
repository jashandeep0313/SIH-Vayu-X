"""JWT authentication and role-based access.

Roles: admin, analyst, responder, public.
"""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

router = APIRouter()


class LoginRequest(BaseModel):
    username: str
    password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    role: str


@router.post("/login", response_model=TokenResponse)
async def login(payload: LoginRequest) -> TokenResponse:
    # TODO(backend): verify credentials against users table, issue JWT
    raise HTTPException(status_code=501, detail="Not implemented — Phase 4")


@router.post("/refresh", response_model=TokenResponse)
async def refresh() -> TokenResponse:
    # TODO(backend): validate refresh token, issue new access token
    raise HTTPException(status_code=501, detail="Not implemented — Phase 4")


@router.get("/me")
async def me() -> dict:
    # TODO(backend): decode bearer token, return user profile and role
    raise HTTPException(status_code=501, detail="Not implemented — Phase 4")
