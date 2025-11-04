"""Session management utilities for web portal authentication."""

from datetime import datetime, timezone
from typing import Optional
from uuid import UUID

from starlette.requests import Request
from starlette.middleware.sessions import SessionMiddleware


def get_session_user_id(request: Request) -> Optional[UUID]:
    """
    Get the authenticated user's ID from the session.

    Args:
        request: The incoming request

    Returns:
        User UUID if authenticated, None otherwise
    """
    user_id_str = request.session.get("user_id")
    if not user_id_str:
        return None

    try:
        return UUID(user_id_str)
    except (ValueError, TypeError):
        # Invalid UUID format, clear the session
        request.session.clear()
        return None


def get_session_created_at(request: Request) -> Optional[datetime]:
    """
    Get the session creation timestamp.

    Args:
        request: The incoming request

    Returns:
        Session creation datetime if available, None otherwise
    """
    created_at_str = request.session.get("created_at")
    if not created_at_str:
        return None

    try:
        return datetime.fromisoformat(created_at_str)
    except (ValueError, TypeError):
        return None


def is_session_expired(request: Request, max_age_hours: int = 24) -> bool:
    """
    Check if the current session has exceeded its maximum age.

    Args:
        request: The incoming request
        max_age_hours: Maximum session age in hours (default: 24)

    Returns:
        True if session is expired, False otherwise
    """
    created_at = get_session_created_at(request)
    if not created_at:
        return True

    # Calculate age
    now = datetime.now(timezone.utc)
    # Make created_at timezone-aware if it isn't
    if created_at.tzinfo is None:
        created_at = created_at.replace(tzinfo=timezone.utc)

    age_hours = (now - created_at).total_seconds() / 3600
    return age_hours >= max_age_hours


def set_session_user_id(request: Request, user_id: UUID) -> None:
    """
    Store the authenticated user's ID in the session.

    Args:
        request: The incoming request
        user_id: The user's UUID
    """
    request.session["user_id"] = str(user_id)

    # Set creation timestamp if not already set
    if "created_at" not in request.session:
        request.session["created_at"] = datetime.now(timezone.utc).isoformat()


def clear_session(request: Request) -> None:
    """
    Clear all session data (used for logout).

    Args:
        request: The incoming request
    """
    request.session.clear()


def regenerate_session(request: Request) -> None:
    """
    Regenerate the session (防止 session fixation attacks).

    This copies important data from the old session, clears it,
    and creates a new session with fresh data. This should be called
    after successful authentication.

    Args:
        request: The incoming request
    """
    # Save important session data
    user_id = request.session.get("user_id")

    # Clear the old session
    request.session.clear()

    # Restore important data with a new creation timestamp
    if user_id:
        request.session["user_id"] = user_id
    request.session["created_at"] = datetime.now(timezone.utc).isoformat()
