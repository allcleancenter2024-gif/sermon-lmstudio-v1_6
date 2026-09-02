from __future__ import annotations

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from app.auth import create_session, create_user, revoke_session, session_user, user_count, verify_password


class AuthRequest(BaseModel):
    username: str = Field(min_length=3, max_length=80)
    password: str = Field(min_length=10, max_length=256)


def build_auth_router(auth_db) -> APIRouter:
    router = APIRouter(prefix="/api/auth")

    @router.get("/status")
    def auth_status(request: Request):
        username = session_user(request.cookies.get("sermon_session"))
        return {"authenticated": bool(username), "username": username, "setup_required": user_count(auth_db) == 0}

    @router.post("/register")
    def auth_register(data: AuthRequest):
        if user_count(auth_db) != 0:
            raise HTTPException(403, "초기 계정이 이미 등록되어 있습니다.")
        if not create_user(auth_db, data.username, data.password):
            raise HTTPException(409, "사용자명이 이미 존재합니다.")
        return {"ok": True, "message": "초기 계정이 생성되었습니다. 로그인하세요."}

    @router.post("/login")
    def auth_login(data: AuthRequest):
        if not verify_password(auth_db, data.username, data.password):
            raise HTTPException(401, "사용자명 또는 비밀번호가 올바르지 않습니다.")
        response = JSONResponse({"ok": True, "username": data.username.strip().lower()})
        response.set_cookie("sermon_session", create_session(data.username), httponly=True, samesite="lax", secure=False, max_age=43200, path="/")
        return response

    @router.post("/logout")
    def auth_logout(request: Request):
        revoke_session(request.cookies.get("sermon_session"))
        response = JSONResponse({"ok": True})
        response.delete_cookie("sermon_session", path="/")
        return response

    return router


__all__ = ["AuthRequest", "build_auth_router"]
