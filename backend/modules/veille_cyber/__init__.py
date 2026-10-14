"""Veille cyber: news about recent cyberattacks (CERT-FR, French press), summarized daily."""

from app.modules_registry import ModuleInfo
from modules.veille_cyber.collector import collect
from modules.veille_cyber.routes import router

MODULE = ModuleInfo(id="veille_cyber", title="Veille cyber", order=1)

__all__ = ["MODULE", "collect", "router"]
