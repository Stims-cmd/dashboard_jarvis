"""OSINT about the owner only: breaches, web mentions, accounts, public profiles."""

from app.modules_registry import ModuleInfo
from modules.osint.collector import collect
from modules.osint.routes import router

MODULE = ModuleInfo(id="osint", title="OSINT", order=3)

__all__ = ["MODULE", "collect", "router"]
