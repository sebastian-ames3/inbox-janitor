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


async def check_worker_activity() -> Dict[str, Any]:
    """
    Check if Celery worker is processing tasks.

    Verifies worker activity by checking recent EmailAction records.

    Returns:
        Dict with status and recent activity count
    """
    try:
        async with AsyncSessionLocal() as session:
            # Count email actions created in last 15 minutes
            query = text("""
                SELECT COUNT(*)
                FROM email_actions
                WHERE created_at > NOW() - INTERVAL '15 minutes'
            """)
            result = await session.execute(query)
            recent_actions = result.scalar()

            # Get total count
            total_query = text("SELECT COUNT(*) FROM email_actions")
            total_result = await session.execute(total_query)
            total_actions = total_result.scalar()

            return {
                "status": "healthy" if recent_actions > 0 or total_actions > 0 else "unknown",
                "recent_actions_15min": recent_actions,
                "total_actions": total_actions,
                "message": "Worker processing tasks" if recent_actions > 0 else
                          ("Tasks processed previously" if total_actions > 0 else "No tasks processed yet")
            }
    except Exception as e:
        logger.error(f"Worker activity check failed: {e}")
        return {
            "status": "unknown",
            "error": str(e),
        }


async def check_worker_pause_status() -> Dict[str, Any]:
    """
    Check if worker is paused via WORKER_PAUSED environment variable.

    Returns:
        Dict with status and pause information
    """
    import os

    worker_paused = os.getenv('WORKER_PAUSED', 'false').lower() == 'true'

    if worker_paused:
        try:
            async with AsyncSessionLocal() as session:
                # Find oldest active pause event
                query = text("""
                    SELECT paused_at, skipped_count
                    FROM worker_pause_events
                    WHERE resumed_at IS NULL
                    ORDER BY paused_at ASC
                    LIMIT 1
                """)
                result = await session.execute(query)
                pause_data = result.fetchone()

                if pause_data:
                    paused_at, skipped_count = pause_data
                    duration_seconds = (datetime.utcnow() - paused_at).total_seconds()

                    return {
                        "status": "warning" if duration_seconds > 300 else "degraded",
                        "worker_paused": True,
                        "pause_duration_seconds": round(duration_seconds, 0),
                        "skipped_count": skipped_count,
                        "message": f"Worker paused for {round(duration_seconds, 0)}s - {skipped_count} emails skipped"
                    }

                return {
                    "status": "warning",
                    "worker_paused": True,
                    "message": "Worker paused but no pause events recorded"
                }
        except Exception as e:
            logger.error(f"Worker pause status check failed: {e}")
            return {
                "status": "warning",
                "worker_paused": True,
                "error": str(e)
            }

    return {
        "status": "healthy",
        "worker_paused": False,
        "message": "Worker active"
    }


async def check_mailbox_health() -> Dict[str, Any]:
    """
    Check mailbox health (active vs inactive counts).

    Returns:
        Dict with active/inactive mailbox counts and status
    """
    try:
        async with AsyncSessionLocal() as session:
            # Count active and inactive mailboxes
            query = text("""
                SELECT
                    COUNT(*) FILTER (WHERE is_active = true) as active_count,
                    COUNT(*) FILTER (WHERE is_active = false) as inactive_count,
                    COUNT(*) as total_count
                FROM mailboxes
            """)
            result = await session.execute(query)
            row = result.fetchone()

            active_count, inactive_count, total_count = row

            if total_count == 0:
                return {
                    "status": "unknown",
                    "active_mailboxes": 0,
                    "inactive_mailboxes": 0,
                    "message": "No mailboxes configured"
                }

            # Calculate inactive percentage
            inactive_percentage = (inactive_count / total_count) * 100 if total_count > 0 else 0

            # Determine status based on inactive percentage
            if inactive_percentage > 50:
                status = "unhealthy"
                message = f"{inactive_percentage:.0f}% mailboxes inactive - possible OAuth issue"
            elif inactive_percentage > 20:
                status = "degraded"
                message = f"{inactive_percentage:.0f}% mailboxes inactive"
            else:
                status = "healthy"
                message = "Mailbox connectivity healthy"

            return {
                "status": status,
                "active_mailboxes": active_count,
                "inactive_mailboxes": inactive_count,
                "inactive_percentage": round(inactive_percentage, 1),
                "message": message
            }
    except Exception as e:
        logger.error(f"Mailbox health check failed: {e}")
        return {
            "status": "unknown",
            "error": str(e),
        }


async def check_last_classification() -> Dict[str, Any]:
    """
    Check when the last email was classified.

    Returns:
        Dict with status and seconds since last classification
    """
    try:
        async with AsyncSessionLocal() as session:
            query = text("""
                SELECT MAX(created_at)
                FROM email_actions
            """)
            result = await session.execute(query)
            last_classification = result.scalar()

            if not last_classification:
                return {
                    "status": "unknown",
                    "message": "No classifications yet"
                }

            seconds_since = (datetime.utcnow() - last_classification).total_seconds()

            # Determine status based on time since last classification
            if seconds_since > 3600:  # 1 hour
                status = "warning"
                message = "No classifications in over 1 hour"
            elif seconds_since > 600:  # 10 minutes
                status = "healthy"
                message = "Classification activity normal"
            else:
                status = "healthy"
                message = "Recently classified emails"

            return {
                "status": status,
                "seconds_since_last": round(seconds_since, 0),
                "last_classification": last_classification.isoformat(),
                "message": message
            }
    except Exception as e:
        logger.error(f"Last classification check failed: {e}")
        return {
            "status": "unknown",
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
        "worker_activity": await check_worker_activity(),
        "worker_pause_status": await check_worker_pause_status(),
        "mailbox_health": await check_mailbox_health(),
        "last_classification": await check_last_classification(),
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
