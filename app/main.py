"""
Inbox Janitor - Main FastAPI Application

Entry point for the application. Mounts all module routers.
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from starlette.middleware.sessions import SessionMiddleware
from contextlib import asynccontextmanager

from app.core.config import settings
from app.core.database import init_db, close_db
from app.core.middleware import (
    configure_csrf,
    configure_rate_limiting,
    add_security_headers,
)
from app.modules.auth.routes import router as auth_router
from app.modules.portal.routes import router as portal_router
from app.api.webhooks import router as webhook_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Application lifespan events.

    Runs on startup and shutdown.
    """
    # Startup
    print(f"Starting {settings.APP_NAME}...")
    print(f"Environment: {settings.ENVIRONMENT}")

    # Initialize Sentry error monitoring
    from app.core.sentry import init_sentry
    init_sentry()

    # Initialize database (only in development - use Alembic in production)
    if settings.ENVIRONMENT == "development":
        await init_db()

    yield

    # Shutdown
    print("Shutting down...")
    await close_db()


# Create FastAPI app
app = FastAPI(
    title=settings.APP_NAME,
    description="Privacy-first email hygiene SaaS - headless inbox cleanup with AI classification",
    version="0.1.0",
    docs_url="/docs" if settings.DEBUG else None,  # Disable docs in production
    redoc_url="/redoc" if settings.DEBUG else None,
    lifespan=lifespan,
)

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://localhost:8000"] if settings.DEBUG else [settings.APP_URL],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Configure security middleware (order matters!)
# 1. Session Management - must be first to handle session cookies
app.add_middleware(
    SessionMiddleware,
    secret_key=settings.SESSION_SECRET_KEY,
    max_age=86400,  # 24 hours in seconds
    same_site="lax",  # CSRF protection
    https_only=settings.is_production,  # Only send over HTTPS in production
    session_cookie="session",
)

# 2. CSRF Protection - depends on session being available
configure_csrf(app)

# 3. Rate Limiting - protect endpoints from abuse
limiter = configure_rate_limiting(app)

# 4. Security Headers - last, applied to all responses
add_security_headers(app)

# Configure Jinja2 templates
templates = Jinja2Templates(directory="app/templates")

# Mount static files (CSS, JS, images)
app.mount("/static", StaticFiles(directory="app/static"), name="static")

# Mount routers
app.include_router(portal_router)  # No prefix - serves landing page at /
app.include_router(auth_router)
app.include_router(webhook_router, prefix="/webhooks", tags=["webhooks"])

# TODO: Add remaining routers as they're implemented
# app.include_router(classifier_router, prefix="/classify", tags=["classifier"])


@app.get("/health")
async def health_check():
    """
    Health check endpoint for monitoring.

    Used by Railway, Docker, and load balancers.

    Returns comprehensive metrics for:
    - Database connectivity
    - Redis (Celery broker)
    - External APIs (Gmail, OpenAI)
    - Webhook activity

    Status codes:
    - healthy: All systems operational
    - degraded: Some warnings but functional
    - unhealthy: Critical components down
    """
    from app.core.health import get_health_metrics

    metrics = await get_health_metrics()

    return {
        "service": settings.APP_NAME,
        "version": "0.1.0",
        "environment": settings.ENVIRONMENT,
        **metrics,
    }


@app.get("/success")
async def oauth_success(email: str):
    """
    OAuth success page - shown after successful Gmail connection.

    Query Params:
        email: Connected Gmail address
    """
    return {
        "status": "success",
        "message": "Gmail account connected successfully!",
        "email": email,
        "next_steps": [
            "Your account is now connected",
            "We'll send you a welcome email soon",
            "Check your inbox for your weekly digest",
        ],
    }


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=8000,
        reload=settings.DEBUG,
    )
