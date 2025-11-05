"""
Health check utilities for monitoring application components.

Checks:
- Database connectivity
- Redis connectivity (Celery broker)
- External API availability (Gmail, OpenAI)
- Webhook activity (last received timestamp)
"""

import logging
from datetime import datetime
from typing import Dict, Any

from sqlalchemy import text
from sqlalchemy.exc import OperationalError
import redis

from app.core.config import settings
from app.core.database import AsyncSessionLocal

logger = logging.getLogger(__name__)


async def check_database() -> Dict[str, Any]:
    """
    Check PostgreSQL database connectivity.

    Returns:
        Dict with status, latency, and error (if any)
    """
    start_time = datetime.utcnow()

    try:
        async with AsyncSessionLocal() as session:
            # Simple query to test connection
            result = await session.execute(text("SELECT 1"))
            result.scalar()

        latency_ms = (datetime.utcnow() - start_time).total_seconds() * 1000

        return {
            "status": "healthy",
            "latency_ms": round(latency_ms, 2),
        }
    except OperationalError as e:
        logger.error(f"Database health check failed: {e}")
        return {
            "status": "unhealthy",
            "error": str(e),
        }
    except Exception as e:
        logger.error(f"Unexpected database error: {e}")
        return {
            "status": "unhealthy",
            "error": str(e),
        }


async def check_redis() -> Dict[str, Any]:
    """
    Check Redis connectivity (Celery broker).

    Returns:
        Dict with status, latency, and error (if any)
    """
    start_time = datetime.utcnow()

    try:
        # Parse Redis URL (format: redis://host:port/db)
        redis_client = redis.from_url(settings.CELERY_BROKER_URL, socket_connect_timeout=2)

        # Ping Redis
        redis_client.ping()

        latency_ms = (datetime.utcnow() - start_time).total_seconds() * 1000

        redis_client.close()

        return {
            "status": "healthy",
            "latency_ms": round(latency_ms, 2),
        }
    except redis.ConnectionError as e:
        logger.error(f"Redis health check failed: {e}")
        return {
            "status": "unhealthy",
            "error": str(e),
        }
    except Exception as e:
        logger.error(f"Unexpected Redis error: {e}")
        return {
            "status": "unhealthy",
            "error": str(e),
        }


async def check_gmail_api() -> Dict[str, Any]:
    """
    Check Gmail API availability.

    Note: This is a lightweight check - doesn't make actual API calls.
    Just verifies credentials are configured.

    Returns:
        Dict with status and configuration state
    """
    try:
        if not settings.GOOGLE_CLIENT_ID or not settings.GOOGLE_CLIENT_SECRET:
            return {
                "status": "unhealthy",
                "error": "Gmail OAuth credentials not configured",
            }

        return {
            "status": "healthy",
            "configured": True,
        }
    except Exception as e:
        logger.error(f"Gmail API health check failed: {e}")
        return {
            "status": "unhealthy",
            "error": str(e),
        }


async def check_openai_api() -> Dict[str, Any]:
    """
    Check OpenAI API availability.

    Note: This is a lightweight check - doesn't make actual API calls.
    Just verifies API key is configured.

    Returns:
        Dict with status and configuration state
    """
    try:
        if not settings.OPENAI_API_KEY:
            return {
                "status": "unhealthy",
                "error": "OpenAI API key not configured",
            }

        return {
            "status": "healthy",
            "configured": True,
        }
    except Exception as e:
        logger.error(f"OpenAI API health check failed: {e}")
        return {
            "status": "unhealthy",
            "error": str(e),
        }


async def check_last_webhook() -> Dict[str, Any]:
    """
    Check when the last webhook was received.

    This helps detect if Gmail Pub/Sub is working correctly.
    If no webhook in 30+ minutes, may indicate watch expiration or Pub/Sub issues.

    Returns:
        Dict with status, seconds since last webhook, and warning (if stale)
    """
    try:
        async with AsyncSessionLocal() as session:
            # Query most recent webhook timestamp
            query = text("""
                SELECT MAX(last_webhook_received_at)
                FROM mailboxes
                WHERE is_active = true
            """)
            result = await session.execute(query)
            last_webhook = result.scalar()

            if not last_webhook:
                return {
                    "status": "unknown",
                    "message": "No webhooks received yet (no active mailboxes)",
                }

            seconds_since = (datetime.utcnow() - last_webhook).total_seconds()

            # Warning thresholds
            if seconds_since > 1800:  # 30 minutes
                return {
                    "status": "warning",
                    "seconds_since_last": round(seconds_since, 0),
                    "message": "No webhooks in 30+ minutes - check Gmail watch",
                }
            elif seconds_since > 600:  # 10 minutes
                return {
                    "status": "healthy",
                    "seconds_since_last": round(seconds_since, 0),
                    "message": "Webhook activity normal (fallback polling active)",
                }
            else:
                return {
                    "status": "healthy",
                    "seconds_since_last": round(seconds_since, 0),
                }
    except Exception as e:
        logger.error(f"Webhook health check failed: {e}")
        return {
            "status": "unhealthy",
            "error": str(e),
        }


async def get_health_metrics() -> Dict[str, Any]:
    """
    Get comprehensive health metrics for all components.

    Returns:
        Dict with overall status and component-specific metrics
    """
    metrics = {
        "database": await check_database(),
        "redis": await check_redis(),
        "gmail_api": await check_gmail_api(),
        "openai_api": await check_openai_api(),
        "last_webhook": await check_last_webhook(),
    }

    # Determine overall status
    unhealthy_components = [
        component for component, status in metrics.items()
        if status.get("status") == "unhealthy"
    ]

    if unhealthy_components:
        overall_status = "unhealthy"
    elif any(status.get("status") == "warning" for status in metrics.values()):
        overall_status = "degraded"
    else:
        overall_status = "healthy"

    return {
        "status": overall_status,
        "timestamp": datetime.utcnow().isoformat(),
        "components": metrics,
    }
