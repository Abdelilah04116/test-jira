"""
Jira QA AI Generator - Main Application
FastAPI application entry point
"""

from contextlib import asynccontextmanager
from datetime import datetime, timezone

from fastapi import FastAPI, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError
from loguru import logger
import os
import sys
import asyncio

# Windows-specific fix for 'NotImplementedError' when using asyncio subprocesses
# This must be set beforeAny loop is created
if sys.platform == 'win32':
    asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())

# Fix for missing aiohttp.ClientConnectorDNSError in older versions or specific environments
# This must be done as early as possible
try:
    import aiohttp
    if not hasattr(aiohttp, "ClientConnectorDNSError"):
        try:
            from aiohttp import client_exceptions
            if hasattr(client_exceptions, "ClientConnectorDNSError"):
                aiohttp.ClientConnectorDNSError = client_exceptions.ClientConnectorDNSError
            else:
                class MockClientConnectorDNSError(OSError): pass
                aiohttp.ClientConnectorDNSError = MockClientConnectorDNSError
        except ImportError:
             class MockClientConnectorDNSError(OSError): pass
             aiohttp.ClientConnectorDNSError = MockClientConnectorDNSError
except ImportError:
    pass # app will likely fail later if aiohttp is missing, but this patch is just for the specific error


# Fix for common Windows initialization error: invalid TLS bundle path
# Often caused by PostgreSQL setting global environment variables
for env_var in ["REQUESTS_CA_BUNDLE", "CURL_CA_BUNDLE", "SSL_CERT_FILE"]:
    val = os.environ.get(env_var)
    if val and "PostgreSQL" in val and not os.path.exists(val):
        try:
            import certifi
            os.environ[env_var] = certifi.where()
        except ImportError:
            # Fallback: just unset the broken path
            del os.environ[env_var]

from app.api.router import api_router
from app.core.config import settings
from app.core.database import init_db, close_db
from app.core.ratelimit import add_rate_limit_exception_handler
from slowapi.middleware import SlowAPIMiddleware


# =============================================================================
# Logging Configuration
# =============================================================================

def setup_logging():
    """Configure Loguru logging"""
    logger.remove()  # Remove default handler
    
    # Console handler
    logger.add(
        sys.stdout,
        format="<green>{time:YYYY-MM-DD HH:mm:ss}</green> | "
               "<level>{level: <8}</level> | "
               "<cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> | "
               "<level>{message}</level>",
        level=settings.log_level,
        colorize=True,
    )
    
    # File handler for production
    if settings.is_production:
        logger.add(
            "logs/app_{time:YYYY-MM-DD}.log",
            rotation="1 day",
            retention="30 days",
            level="INFO",
            format="{time:YYYY-MM-DD HH:mm:ss} | {level: <8} | {name}:{function}:{line} | {message}",
        )


# =============================================================================
# Application Lifecycle
# =============================================================================

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan events"""
    # Startup
    setup_logging()
    logger.info(f"Starting {settings.app_name} v1.0.0")
    logger.info(f"Environment: {settings.app_env}")
    logger.info(f"Debug mode: {settings.debug}")
    
    # Initialize database
    try:
        await init_db()
        logger.info("Database initialized successfully")
    except Exception as e:
        logger.warning(f"Database initialization skipped: {e}")
    
    # Log LLM configuration
    logger.info(f"Default LLM provider: {settings.llm_provider}")
    
    yield
    
    # Shutdown
    logger.info("Shutting down application...")
    await close_db()
    logger.info("Application shutdown complete")


# =============================================================================
# FastAPI Application
# =============================================================================

app = FastAPI(
    title=settings.app_name,
    description="""
## 🚀 Jira QA AI Generator API

Enterprise-grade AI solution for automated QA generation from Jira User Stories.

### Features

- 📝 **Generate Gherkin Acceptance Criteria** from User Stories
- 🧪 **Generate Test Scenarios** (positive, negative, edge cases)
- 📤 **Automatic Publication to Jira** (subtasks, comments, custom fields)
- 🤖 **Multi-LLM Support**: Gemini, Claude, OpenAI

### Quick Start

1. Authenticate via `/api/v1/auth/login`
2. Fetch a story via `/api/v1/jira/story/{issue_id}`
3. Generate criteria via `/api/v1/generate/acceptance-criteria`
4. Generate tests via `/api/v1/generate/test-scenarios`
5. Or run the full pipeline via `/api/v1/generate/full-pipeline`

### Authentication

All endpoints (except health checks) require JWT authentication.
Include the token in the `Authorization` header:
```
Authorization: Bearer <your-access-token>
```
""",
    version="1.0.0",
    docs_url="/docs" if settings.debug else None,
    redoc_url="/redoc" if settings.debug else None,
    openapi_url="/openapi.json" if settings.debug else None,
    lifespan=lifespan,
)

# Initialize Rate Limiter
add_rate_limit_exception_handler(app)
app.add_middleware(SlowAPIMiddleware)


# =============================================================================
# Middleware
# =============================================================================

from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

import sys

@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request, exc):
    # On utilise warning car c'est visible dans vos logs
    logger.warning("=" * 40)
    logger.warning(f"🚨 ERREUR 422 SUR: {request.url.path}")
    logger.warning(f"DÉTAILS: {exc.errors()}")
    logger.warning("=" * 40)
    return JSONResponse(
        status_code=422,
        content={"detail": exc.errors()},
    )

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Request logging middleware
@app.middleware("http")
async def log_requests(request: Request, call_next):
    """Log all incoming requests"""
    start_time = datetime.now(timezone.utc)
    response = await call_next(request)
    duration = (datetime.now(timezone.utc) - start_time).total_seconds()
    logger.info(f"{request.method} {request.url.path} - {response.status_code} - {duration:.3f}s")
    return response


# =============================================================================
# Exception Handlers
# =============================================================================

@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    """Handle validation errors"""
    errors = []
    for error in exc.errors():
        errors.append({
            "loc": list(error["loc"]),
            "msg": error["msg"],
            "type": error["type"]
        })
    
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content={
            "error": "Validation Error",
            "details": errors,
            "code": "VALIDATION_ERROR"
        }
    )


@app.exception_handler(Exception)
async def general_exception_handler(request: Request, exc: Exception):
    """Handle unexpected exceptions"""
    logger.exception(f"Unhandled exception: {exc}")
    
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={
            "error": "Internal Server Error",
            "detail": str(exc) if settings.debug else "An unexpected error occurred",
            "code": "INTERNAL_ERROR"
        }
    )


# =============================================================================
# Routes
# =============================================================================

# Include API router
app.include_router(api_router)


# Root endpoint
@app.get("/")
async def root():
    """Root endpoint - service info"""
    return {
        "service": settings.app_name,
        "version": "1.0.0",
        "status": "running",
        "docs": "/docs" if settings.debug else "disabled",
        "api": "/api/v1"
    }


# Health check (publicly accessible)
@app.get("/health")
async def health():
    """Health check endpoint for load balancers"""
    return {
        "status": "healthy",
        "timestamp": datetime.now(timezone.utc).isoformat()
    }


# =============================================================================
# Main Entry Point
# =============================================================================

if __name__ == "__main__":
    import uvicorn
    
    uvicorn.run(
        "app.main:app",
        host=settings.host,
        port=settings.port,
        reload=settings.reload,
        workers=1 if settings.reload else settings.workers,
        log_level=settings.log_level.lower(),
    )
