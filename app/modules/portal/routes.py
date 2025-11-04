"""Portal routes for user-facing pages (landing, dashboard, settings)."""

from fastapi import APIRouter, Request, Depends
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.modules.portal.dependencies import get_current_user, get_current_user_optional
from app.models.user import User

# Initialize templates
templates = Jinja2Templates(directory="app/templates")

# Create router
router = APIRouter(tags=["portal"])


@router.get("/", response_class=HTMLResponse)
async def landing_page(
    request: Request,
    user: User | None = Depends(get_current_user_optional),
    db: AsyncSession = Depends(get_db)
):
    """
    Landing page - marketing site.

    If user is already logged in, redirect to dashboard.
    Otherwise, show landing page with "Connect Gmail" CTA.
    """
    # Redirect logged-in users to dashboard
    if user:
        return RedirectResponse(url="/dashboard", status_code=302)

    # Show landing page for anonymous users
    return templates.TemplateResponse(
        "landing.html",
        {"request": request, "user": None}
    )


@router.get("/welcome", response_class=HTMLResponse)
async def welcome_page(
    request: Request,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Welcome page - shown after successful OAuth connection.

    Displays success message and next steps.
    Requires authentication.
    """
    return templates.TemplateResponse(
        "auth/welcome.html",
        {"request": request, "user": user}
    )


@router.get("/auth/error", response_class=HTMLResponse)
async def auth_error_page(
    request: Request,
    reason: str = None,
    error_message: str = None
):
    """
    OAuth error page - shown when OAuth flow fails.

    Query Params:
        reason: Technical reason for failure (optional)
        error_message: User-friendly error message (optional)
    """
    return templates.TemplateResponse(
        "auth/error.html",
        {
            "request": request,
            "user": None,
            "reason": reason,
            "error_message": error_message
        }
    )
