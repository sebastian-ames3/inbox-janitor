"""
Inbox Janitor - Main FastAPI Application

Entry point for the application. Mounts all module routers.
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager

from app.core.config import settings
from app.core.database import init_db, close_db
from app.modules.auth.routes import router as auth_router
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

# Mount routers
app.include_router(auth_router)
app.include_router(webhook_router, prefix="/webhooks", tags=["webhooks"])

# TODO: Add remaining routers as they're implemented
# app.include_router(classifier_router, prefix="/classify", tags=["classifier"])


@app.get("/")
async def root():
    """Root endpoint - API information."""
    return {
        "service": settings.APP_NAME,
        "version": "0.1.0",
        "status": "running",
        "environment": settings.ENVIRONMENT,
        "docs": "/docs" if settings.DEBUG else "disabled",
    }


@app.get("/health")
async def health_check():
    """
    Health check endpoint for monitoring.

    Used by Railway, Docker, and load balancers.
    """
    return {
        "status": "healthy",
        "service": settings.APP_NAME,
        "environment": settings.ENVIRONMENT,
        "version": "0.1.0",
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
