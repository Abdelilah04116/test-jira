"""
API Router
Central router aggregating all API endpoints
"""

from fastapi import APIRouter

from app.api.auth import router as auth_router
from app.api.jira import router as jira_router
from app.api.generate import router as generate_router
from app.api.analytics import router as analytics_router
from app.api.webhooks import router as webhooks_router
from app.api.system import router as system_router


# Create main API router
api_router = APIRouter(prefix="/api/v1")

# Include all sub-routers
api_router.include_router(auth_router)
api_router.include_router(jira_router)
api_router.include_router(generate_router)
api_router.include_router(analytics_router)
api_router.include_router(webhooks_router)
api_router.include_router(system_router)


# Health check endpoint at root level
@api_router.get("/health")
async def health_check():
    """
    API Health Check
    
    Returns basic health status of the API.
    """
    return {
        "status": "healthy",
        "service": "Jira QA AI Generator",
        "version": "1.0.0"
    }
