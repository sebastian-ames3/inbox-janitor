"""Authentication dependencies for the web portal.

Provides get_current_user dependency for protecting routes.
"""

from fastapi import Depends, HTTPException, Request, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.session import (
    get_session_user_id,
    is_session_expired,
    clear_session,
)
from app.models.user import User


async def get_current_user(
    request: Request,
    db: AsyncSession = Depends(get_db)
) -> User:
    """
    FastAPI dependency to get the currently authenticated user.

    Validates the session and returns the user object from the database.

    Args:
        request: The incoming request (for session access)
        db: Database session (injected by FastAPI)

    Returns:
        The authenticated User object

    Raises:
        HTTPException: 401 if not authenticated or session expired

    Usage:
        @router.get("/dashboard")
        async def dashboard(user: User = Depends(get_current_user)):
            return {"email": user.email}
    """
    # Check if user_id exists in session
    user_id = get_session_user_id(request)
    if not user_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated. Please log in.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # Check if session has expired (max age: 24 hours)
    if is_session_expired(request, max_age_hours=24):
        clear_session(request)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Session expired. Please log in again.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # Query database for user
    result = await db.execute(
        select(User).where(User.id == user_id, User.is_active == True)
    )
    user = result.scalar_one_or_none()

    # If user not found or inactive, clear session and raise error
    if not user:
        clear_session(request)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found or account deactivated. Please log in again.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    return user


async def get_current_user_optional(
    request: Request,
    db: AsyncSession = Depends(get_db)
) -> User | None:
    """
    Optional authentication dependency.

    Returns the user if authenticated, None otherwise.
    Does not raise an error if not authenticated.

    Args:
        request: The incoming request
        db: Database session

    Returns:
        User object if authenticated, None otherwise

    Usage:
        @router.get("/")
        async def landing(user: User | None = Depends(get_current_user_optional)):
            if user:
                # Redirect to dashboard
                ...
            else:
                # Show landing page
                ...
    """
    try:
        return await get_current_user(request, db)
    except HTTPException:
        return None
