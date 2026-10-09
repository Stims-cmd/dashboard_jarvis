"""Finances: manual tracking of balances, regulated savings rates, ceilings and goals."""

from app.modules_registry import ModuleInfo
from modules.finances.routes import router

MODULE = ModuleInfo(id="finances", title="Finances", order=2)

__all__ = ["MODULE", "router"]
