from fastapi import APIRouter
from app.api.routes.creators import router as creators_router
from app.api.routes.picks import router as picks_router
from app.api.routes.scrape import router as scrape_router
from app.api.routes.health import router as health_router
from app.api.routes.submissions import router as submissions_router

api_router = APIRouter(prefix="/api/v1")
api_router.include_router(creators_router)
api_router.include_router(picks_router)
api_router.include_router(scrape_router)
api_router.include_router(health_router)
api_router.include_router(submissions_router)
