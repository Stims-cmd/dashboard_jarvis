"""Discovers dashboard modules in backend/modules/ and exposes them to the API."""

import importlib
import pkgutil
from dataclasses import dataclass

from fastapi import APIRouter, Depends, FastAPI
from pydantic import BaseModel

import modules
from app.auth.deps import CurrentUser, require_user


@dataclass(frozen=True)
class ModuleInfo:
    id: str
    title: str
    order: int


class ModuleOut(BaseModel):
    id: str
    title: str


def discover_modules() -> list[tuple[ModuleInfo, APIRouter]]:
    found = []
    for module_finder in pkgutil.iter_modules(modules.__path__):
        package = importlib.import_module(f"modules.{module_finder.name}")
        found.append((package.MODULE, package.router))
    return sorted(found, key=lambda item: item[0].order)


def register_modules(app: FastAPI) -> None:
    discovered = discover_modules()
    for info, module_router in discovered:
        # Every module route requires a logged-in user.
        app.include_router(
            module_router, prefix=f"/api/modules/{info.id}", dependencies=[Depends(require_user)]
        )

    listing = APIRouter()

    @listing.get("/api/modules")
    def list_modules(_user: CurrentUser) -> list[ModuleOut]:
        return [ModuleOut(id=info.id, title=info.title) for info, _ in discovered]

    app.include_router(listing)
