from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, HTTPException, Query

from ..core.config import AppSettings
from ..core.preflight import run_preflight
from ..core.security import secret_store
from ..models.schemas import ApiKeyInput, SettingsUpdate
from ..services.openai_service import openai_service
from ..storage.database import db

router = APIRouter(tags=["settings"])


@router.get("/settings")
def get_settings():
    key = secret_store.get()
    return {"values": db.settings(), "openai": {"registered": bool(key), "masked_key": secret_store.mask(key)}}


@router.put("/settings")
def update_settings(payload: SettingsUpdate):
    current = db.settings()
    try:
        validated = AppSettings(**(current | payload.values)).to_dict()
        Path(validated["output_folder"]).expanduser().mkdir(parents=True, exist_ok=True)
    except Exception as exc:
        raise HTTPException(422, str(exc)) from exc
    return {"values": db.update_settings(validated)}


@router.put("/settings/openai-key")
def save_key(payload: ApiKeyInput):
    try:
        storage = secret_store.set(payload.api_key)
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc
    return {"registered": True, "masked_key": secret_store.mask(payload.api_key), "storage": storage}


@router.delete("/settings/openai-key")
def delete_key():
    secret_store.delete()
    return {"registered": False, "masked_key": None}


@router.post("/settings/openai-test")
def test_key():
    try:
        return openai_service.test_connection(db.settings()["openai_model"])
    except Exception as exc:
        raise HTTPException(400, str(exc)) from exc


@router.get("/system/check")
def system_check(check_yahoo: bool = Query(False), check_tts: bool = Query(False)):
    return {"checks": run_preflight(check_yahoo=check_yahoo, check_tts=check_tts)}
