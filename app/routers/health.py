from __future__ import annotations

from fastapi import APIRouter, Request

from app.core import DB_PATH, DEFAULT_SERMON_MINUTES, SUPPORTED_SERMON_MINUTES, LMStudioClient, db_stats, get_lmstudio_url, rag_stats

router = APIRouter()
APP_VERSION = "40.9.10"


@router.get("/api/runtime")
def runtime_info(request: Request):
    return {"runtime_id": "sermon-lmstudio-local", "app_version": APP_VERSION,
            "supported_minutes": list(SUPPORTED_SERMON_MINUTES), "default_minutes": DEFAULT_SERMON_MINUTES,
            "local_url": str(request.base_url).rstrip("/"), "lmstudio_url": get_lmstudio_url()}


@router.get("/api/health")
def health():
    client = LMStudioClient()
    try:
        catalog = client.model_catalog()
        connected = bool(catalog["models"])
        return {"connected": connected, "app_version": APP_VERSION, "supported_minutes": list(SUPPORTED_SERMON_MINUTES), "default_minutes": DEFAULT_SERMON_MINUTES, "lmstudio_url": get_lmstudio_url(), **catalog, "database": db_stats(), "rag": rag_stats(), "message": "" if connected else (catalog["openai_error"] or "모델 목록을 찾지 못했습니다.")}
    except (ConnectionError, RuntimeError) as exc:
        return {"connected": False, "app_version": APP_VERSION, "supported_minutes": list(SUPPORTED_SERMON_MINUTES), "default_minutes": DEFAULT_SERMON_MINUTES, "lmstudio_url": get_lmstudio_url(), "models": [], "generation_models": [], "embedding_models": [], "source": "unavailable", "openai_models_ok": False, "warnings": [], "database": db_stats(), "rag": rag_stats(), "message": str(exc)}
