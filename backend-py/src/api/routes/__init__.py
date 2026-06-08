"""API routes package."""

from __future__ import annotations

from fastapi import APIRouter

from . import agents, health, runs, workflows

router = APIRouter()

router.include_router(health.router)
router.include_router(agents.router)
router.include_router(runs.router)
router.include_router(workflows.router)

__all__ = ["router"]