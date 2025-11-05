"""
Test-only API routes for E2E testing.

SECURITY NOTE: These routes are ONLY available in development/test environments.
They are disabled in production to prevent security vulnerabilities.
"""

from datetime import datetime, timezone
from uuid import UUID

from fastapi import APIRouter, HTTPException, Request, status
from pydantic import BaseModel

from app.core.config import get_settings
from app.core.session import set_session_user_id

settings = get_settings()

# Router for test-only endpoints
router = APIRouter(prefix="/api/test", tags=["test"])


class CreateSessionRequest(BaseModel):
    """Request body for creating a test session."""

    user_id: str = "00000000-0000-0000-0000-000000000001"  # Default to test user


class CreateSessionResponse(BaseModel):
    """Response for session creation."""

    success: bool
    user_id: str
    message: str


@router.post("/create-session", response_model=CreateSessionResponse)
async def create_test_session(
    request: Request, session_request: CreateSessionRequest
) -> CreateSessionResponse:
    """
    Create an authenticated session for E2E testing.

    This endpoint is ONLY available in development and test environments.
    It creates a session with the specified user_id, allowing E2E tests
    to access protected pages without going through the full OAuth flow.

    Security:
    - Disabled in production (returns 403)
    - Only accepts test user IDs
    - Used exclusively for Playwright E2E tests

    Args:
        request: FastAPI request object
        session_request: Request body with user_id

    Returns:
        Success response with session details

    Raises:
        HTTPException: 403 if called in production environment
        HTTPException: 400 if user_id is invalid
    """

    # CRITICAL: Block in production
    if settings.ENVIRONMENT == "production":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Test endpoints are not available in production",
        )

    # Validate user_id format
    try:
        user_id = UUID(session_request.user_id)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid user_id format: {session_request.user_id}",
        )

    # Create session using existing session utilities
    set_session_user_id(request, user_id)

    return CreateSessionResponse(
        success=True,
        user_id=str(user_id),
        message=f"Session created for user {user_id}",
    )


@router.get("/session-status")
async def get_session_status(request: Request):
    """
    Check current session status (test helper).

    Returns the current user_id from session if authenticated,
    or null if not authenticated.

    This is useful for debugging E2E tests.
    """

    # CRITICAL: Block in production
    if settings.ENVIRONMENT == "production":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Test endpoints are not available in production",
        )

    user_id = request.session.get("user_id")
    created_at = request.session.get("created_at")

    return {
        "authenticated": user_id is not None,
        "user_id": user_id,
        "created_at": created_at,
        "session_data": dict(request.session),
    }
