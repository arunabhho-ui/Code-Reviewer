import time
from datetime import datetime, timezone
from fastapi import APIRouter
from app.config import settings

router = APIRouter(tags=["health"])

START_TIME = time.time()

@router.get("/health")
async def health_check():
    """
    Health check endpoint returning system status, uptime, version, and server timestamp.
    """
    uptime_seconds = round(time.time() - START_TIME, 2)
    return {
        "status": "ok",
        "service": settings.PROJECT_NAME,
        "version": settings.VERSION,
        "uptime_seconds": uptime_seconds,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "groq_configured": bool(settings.GROQ_API_KEY),
        "environment": "production" if not settings.CORS_ORIGINS else "ready",
    }
