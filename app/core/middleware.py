"""Security middleware for the web portal.

This module provides CSRF protection, rate limiting, and security headers.
"""

from typing import Callable

from fastapi import FastAPI, Request, Response
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.util import get_remote_address
from starlette.middleware.base import BaseHTTPMiddleware
from starlette_csrf import CSRFMiddleware

from app.core.config import settings


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """Middleware to add security headers to all responses."""

    async def dispatch(
        self, request: Request, call_next: Callable
    ) -> Response:
        """Add security headers to the response."""
        response = await call_next(request)

        # Basic security headers (always applied)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["X-XSS-Protection"] = "1; mode=block"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"

        # Permissions Policy (disable unnecessary browser features)
        response.headers["Permissions-Policy"] = (
            "geolocation=(), microphone=(), camera=()"
        )

        # HSTS - only in production (requires HTTPS)
        if settings.is_production:
            response.headers["Strict-Transport-Security"] = (
                "max-age=31536000; includeSubDomains"
            )

        # Content Security Policy
        # Note: 'unsafe-inline' is needed for Alpine.js and HTMX inline scripts
        # In production, consider using nonces for better security
        csp_directives = [
            "default-src 'self'",
            "script-src 'self' 'unsafe-inline' https://unpkg.com https://cdn.jsdelivr.net",
            "style-src 'self' 'unsafe-inline' https://fonts.googleapis.com https://cdn.jsdelivr.net",
            "font-src 'self' https://fonts.gstatic.com",
            "img-src 'self' data: https:",
            "connect-src 'self'",
            "frame-ancestors 'none'",
            "base-uri 'self'",
            "form-action 'self'",
        ]
        response.headers["Content-Security-Policy"] = "; ".join(csp_directives)

        return response


def configure_csrf(app: FastAPI) -> None:
    """
    Configure CSRF protection middleware.

    Args:
        app: The FastAPI application instance
    """
    app.add_middleware(
        CSRFMiddleware,
        secret=settings.SECRET_KEY,
        # Cookie settings for CSRF token
        cookie_name="csrf_token",
        cookie_path="/",
        cookie_domain=None,
        cookie_secure=settings.is_production,  # Only send over HTTPS in production
        cookie_httponly=False,  # JS needs to read this for HTMX
        cookie_samesite="lax",
        # Header name that client must send
        header_name="X-CSRF-Token",
        # Exempt certain endpoints (e.g., webhooks from external services)
        exempt_urls=[
            "/health",
            "/webhooks/gmail",  # Gmail Pub/Sub webhook
        ],
    )


def configure_rate_limiting(app: FastAPI) -> Limiter:
    """
    Configure rate limiting middleware.

    Args:
        app: The FastAPI application instance

    Returns:
        The configured Limiter instance for use in route decorators
    """
    limiter = Limiter(
        key_func=get_remote_address,
        default_limits=["200/minute"],  # Default limit for all endpoints
        storage_uri=settings.REDIS_URL,
        strategy="fixed-window",
        headers_enabled=True,  # Send rate limit info in headers
    )

    # Register the rate limit exceeded handler
    app.state.limiter = limiter
    app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

    return limiter


def add_security_headers(app: FastAPI) -> None:
    """
    Add security headers middleware to the application.

    Args:
        app: The FastAPI application instance
    """
    app.add_middleware(SecurityHeadersMiddleware)
