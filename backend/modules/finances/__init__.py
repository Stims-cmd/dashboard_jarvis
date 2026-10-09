"""Finances module (placeholder until its own step)."""

from fastapi import APIRouter

from app.modules_registry import ModuleInfo

MODULE = ModuleInfo(id="finances", title="Finances", order=2)
router = APIRouter()


@router.get("/status")
def status() -> dict[str, str]:
    return {"status": "not_implemented"}
