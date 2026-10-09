"""Leboncoin module (placeholder until its own step)."""

from fastapi import APIRouter

from app.modules_registry import ModuleInfo

MODULE = ModuleInfo(id="leboncoin", title="Leboncoin", order=4)
router = APIRouter()


@router.get("/status")
def status() -> dict[str, str]:
    return {"status": "not_implemented"}
