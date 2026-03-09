from fastapi import APIRouter
from app.api.routes.creators import router as creators_router
from app.api.routes.picks import router as picks_router

api_router = APIRouter(prefix="/api/v1")
api_router.include_router(creators_router)
api_router.include_router(picks_router)
