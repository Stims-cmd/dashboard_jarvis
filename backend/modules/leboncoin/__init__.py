"""Leboncoin: ads received through the owner's saved-search alert emails.

The only data source is the dedicated mailbox receiving those alerts: no scraping,
no request to leboncoin.fr.
"""

from app.modules_registry import ModuleInfo
from modules.leboncoin.collector import collect
from modules.leboncoin.routes import router

MODULE = ModuleInfo(id="leboncoin", title="Leboncoin", order=4)

__all__ = ["MODULE", "collect", "router"]
