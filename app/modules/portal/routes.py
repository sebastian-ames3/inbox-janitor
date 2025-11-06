"""Portal routes for user-facing pages (landing, dashboard, settings)."""

from fastapi import APIRouter, Request, Depends, HTTPException
from fastapi.responses import HTMLResponse, RedirectResponse, Response
from fastapi.templating import Jinja2Templates
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.core.database import get_db
from app.modules.portal.dependencies import get_current_user, get_current_user_optional
from app.modules.portal.forms import SettingsUpdate, SettingsToggle
from app.models.user import User
from app.models.user_settings import UserSettings
from app.models.mailbox import Mailbox

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


@router.get("/dashboard", response_class=HTMLResponse)
async def dashboard_page(
    request: Request,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Settings dashboard - main settings page.

    Displays all user settings with forms to update them.
    Requires authentication.
    """
    # Fetch user settings
    result = await db.execute(
        select(UserSettings).where(UserSettings.user_id == user.id)
    )
    settings = result.scalar_one_or_none()

    if not settings:
        # Create default settings if they don't exist
        settings = UserSettings(user_id=user.id)
        db.add(settings)
        await db.commit()
        await db.refresh(settings)

    # Fetch user's primary mailbox
    result = await db.execute(
        select(Mailbox).where(
            Mailbox.user_id == user.id,
            Mailbox.is_active == True
        ).order_by(Mailbox.created_at.desc())
    )
    mailbox = result.scalar_one_or_none()

    if not mailbox:
        # No active mailbox - redirect to landing page
        return RedirectResponse(url="/", status_code=302)

    # Get CSRF token from request cookies
    csrf_token = request.cookies.get('csrf_token', '')

    return templates.TemplateResponse(
        "portal/dashboard.html",
        {
            "request": request,
            "user": user,
            "settings": settings,
            "mailbox": mailbox,
            "csrf_token": csrf_token
        }
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


# API Routes for Settings Updates

@router.post("/api/settings/update", response_class=HTMLResponse)
async def update_settings(
    request: Request,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Update user settings (thresholds and digest schedule).

    Handles form submission from dashboard.
    Returns HTMX response with success message.
    """
    # Parse form data
    form_data = await request.form()

    # Build settings update model
    try:
        settings_update = SettingsUpdate(
            confidence_auto_threshold=float(form_data.get('confidence_auto_threshold', 0.85)),
            confidence_review_threshold=float(form_data.get('confidence_review_threshold', 0.55)),
            digest_schedule=form_data.get('digest_schedule', 'weekly'),
            action_mode_enabled=form_data.get('action_mode_enabled', 'false').lower() == 'true',
            auto_trash_promotions=form_data.get('auto_trash_promotions', 'true').lower() == 'true',
            auto_trash_social=form_data.get('auto_trash_social', 'true').lower() == 'true',
            keep_receipts=form_data.get('keep_receipts', 'true').lower() == 'true'
        )
    except Exception as e:
        return HTMLResponse(
            content=f'<p class="text-danger-600">❌ Invalid settings: {str(e)}</p>',
            status_code=400
        )

    # Fetch user settings
    result = await db.execute(
        select(UserSettings).where(UserSettings.user_id == user.id)
    )
    settings = result.scalar_one_or_none()

    if not settings:
        settings = UserSettings(user_id=user.id)
        db.add(settings)

    # Update settings
    settings.confidence_auto_threshold = settings_update.confidence_auto_threshold
    settings.confidence_review_threshold = settings_update.confidence_review_threshold
    settings.digest_schedule = settings_update.digest_schedule
    settings.action_mode_enabled = settings_update.action_mode_enabled
    settings.auto_trash_promotions = settings_update.auto_trash_promotions
    settings.auto_trash_social = settings_update.auto_trash_social
    settings.keep_receipts = settings_update.keep_receipts

    await db.commit()

    # Return success message (HTMX will insert this)
    return HTMLResponse(
        content='<p class="text-success-600">✓ Settings saved successfully!</p>',
        status_code=200
    )


@router.post("/api/settings/toggle")
async def toggle_setting(
    settings_toggle: SettingsToggle,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Toggle a single boolean setting (used by HTMX auto-save).

    Body:
        {
            "field": "action_mode_enabled",
            "value": true
        }

    Returns:
        Empty 200 response on success
    """
    # Fetch user settings
    result = await db.execute(
        select(UserSettings).where(UserSettings.user_id == user.id)
    )
    settings = result.scalar_one_or_none()

    if not settings:
        settings = UserSettings(user_id=user.id)
        db.add(settings)

    # Update the specific field
    setattr(settings, settings_toggle.field, settings_toggle.value)

    await db.commit()

    return {"status": "success"}


@router.get("/account", response_class=HTMLResponse)
async def account_page(
    request: Request,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Account management page.

    Displays user info, connected mailboxes, billing, and account actions.
    Requires authentication.
    """
    # Fetch all user's mailboxes
    result = await db.execute(
        select(Mailbox).where(Mailbox.user_id == user.id).order_by(Mailbox.created_at.desc())
    )
    mailboxes = result.scalars().all()

    return templates.TemplateResponse(
        "portal/account.html",
        {
            "request": request,
            "user": user,
            "mailboxes": mailboxes
        }
    )


@router.get("/api/account/export")
async def export_account_data(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Export all user data (GDPR compliance).

    Returns JSON file with:
    - User profile
    - Connected mailboxes
    - Settings
    - Email actions (last 30 days)

    NOTE: Does not include OAuth tokens (security)
    """
    from datetime import datetime, timedelta
    from app.models.email_action import EmailAction
    from app.models.sender_stats import SenderStats

    # Fetch user settings
    result = await db.execute(
        select(UserSettings).where(UserSettings.user_id == user.id)
    )
    settings = result.scalar_one_or_none()

    # Fetch mailboxes (without tokens)
    result = await db.execute(
        select(Mailbox).where(Mailbox.user_id == user.id)
    )
    mailboxes = result.scalars().all()

    # Fetch email actions (last 30 days)
    thirty_days_ago = datetime.utcnow() - timedelta(days=30)
    result = await db.execute(
        select(EmailAction).where(
            EmailAction.mailbox_id.in_([m.id for m in mailboxes]),
            EmailAction.created_at >= thirty_days_ago
        ).order_by(EmailAction.created_at.desc())
    )
    actions = result.scalars().all()

    # Fetch sender stats
    result = await db.execute(
        select(SenderStats).where(SenderStats.user_id == user.id)
    )
    sender_stats = result.scalars().all()

    # Build export data
    export_data = {
        "export_date": datetime.utcnow().isoformat(),
        "user": {
            "id": str(user.id),
            "email": user.email,
            "created_at": user.created_at.isoformat()
        },
        "settings": {
            "confidence_auto_threshold": settings.confidence_auto_threshold if settings else 0.85,
            "confidence_review_threshold": settings.confidence_review_threshold if settings else 0.55,
            "digest_schedule": settings.digest_schedule if settings else "weekly",
            "action_mode_enabled": settings.action_mode_enabled if settings else False,
            "auto_trash_promotions": settings.auto_trash_promotions if settings else True,
            "auto_trash_social": settings.auto_trash_social if settings else True,
            "keep_receipts": settings.keep_receipts if settings else True,
            "blocked_senders": settings.blocked_senders if settings else [],
            "allowed_domains": settings.allowed_domains if settings else []
        },
        "mailboxes": [
            {
                "id": str(m.id),
                "provider": m.provider,
                "email_address": m.email_address,
                "is_active": m.is_active,
                "connected_at": m.created_at.isoformat()
            }
            for m in mailboxes
        ],
        "email_actions_last_30_days": [
            {
                "id": str(a.id),
                "message_id": a.message_id,
                "from_address": a.from_address,
                "subject": a.subject,
                "action": a.action,
                "reason": a.reason,
                "confidence": a.confidence,
                "created_at": a.created_at.isoformat(),
                "undone_at": a.undone_at.isoformat() if a.undone_at else None
            }
            for a in actions
        ],
        "sender_stats": [
            {
                "sender_address": s.sender_address,
                "total_received": s.total_received,
                "opened_count": s.opened_count,
                "replied_count": s.replied_count,
                "last_received_at": s.last_received_at.isoformat() if s.last_received_at else None
            }
            for s in sender_stats
        ]
    }

    # Return as downloadable JSON
    import json
    from fastapi.responses import Response

    return Response(
        content=json.dumps(export_data, indent=2),
        media_type="application/json",
        headers={
            "Content-Disposition": f"attachment; filename=inbox-janitor-export-{datetime.utcnow().strftime('%Y%m%d')}.json"
        }
    )


@router.post("/api/account/pause")
async def pause_account(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Pause email processing for all user mailboxes.

    Marks all mailboxes as inactive without deleting data.
    User can resume by reactivating mailboxes.
    """
    # Mark all mailboxes as inactive
    result = await db.execute(
        select(Mailbox).where(
            Mailbox.user_id == user.id,
            Mailbox.is_active == True
        )
    )
    mailboxes = result.scalars().all()

    for mailbox in mailboxes:
        mailbox.is_active = False

    await db.commit()

    return {
        "status": "paused",
        "message": f"Paused {len(mailboxes)} mailbox(es)",
        "paused_count": len(mailboxes)
    }


@router.post("/api/account/delete")
async def delete_account(
    request: Request,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Permanently delete user account.

    This endpoint:
    1. Revokes all OAuth tokens
    2. Marks all mailboxes as inactive
    3. Schedules data deletion (7 days)
    4. Clears session

    NOTE: Actual deletion happens after 7-day grace period
    """
    from app.modules.auth.gmail_oauth import gmail_oauth

    # Revoke all OAuth tokens
    result = await db.execute(
        select(Mailbox).where(
            Mailbox.user_id == user.id,
            Mailbox.is_active == True
        )
    )
    mailboxes = result.scalars().all()

    for mailbox in mailboxes:
        try:
            await gmail_oauth.revoke_token(mailbox.encrypted_access_token)
        except Exception:
            pass  # Continue even if revocation fails
        mailbox.is_active = False

    # Mark user for deletion
    from datetime import datetime, timedelta
    user.deletion_scheduled_at = datetime.utcnow()
    user.deletion_date = datetime.utcnow() + timedelta(days=7)

    await db.commit()

    # Clear session
    from app.core.session import clear_session
    clear_session(request)

    return {
        "status": "deleted",
        "message": "Account scheduled for deletion. Data will be removed in 7 days.",
        "deletion_date": user.deletion_date.isoformat()
    }


@router.get("/audit", response_class=HTMLResponse)
async def audit_log_page(
    request: Request,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    page: int = 1,
    per_page: int = 50,
    action_filter: str = None,
    search: str = None
):
    """
    Audit log page - view email action history.

    Displays last 30 days of email actions with:
    - Pagination (50 items per page)
    - Filtering by action type
    - Search by sender or subject
    - Summary stats
    - Undo functionality

    Query Params:
        page: Page number (default: 1)
        per_page: Items per page (default: 50)
        action_filter: Filter by action type ('archive', 'trash', 'keep', 'undo')
        search: Search term for sender or subject
    """
    from datetime import datetime, timedelta
    from app.models.email_action import EmailAction
    from sqlalchemy import func, or_

    # Fetch user's mailboxes
    result = await db.execute(
        select(Mailbox).where(Mailbox.user_id == user.id)
    )
    mailboxes = result.scalars().all()
    mailbox_ids = [m.id for m in mailboxes]

    if not mailbox_ids:
        # No mailboxes, show empty state
        return templates.TemplateResponse(
            "portal/audit.html",
            {
                "request": request,
                "user": user,
                "actions": [],
                "stats": {"total": 0, "archived": 0, "trashed": 0, "undone": 0},
                "page": 1,
                "per_page": per_page,
                "total_pages": 0,
                "total_actions": 0,
                "action_filter": action_filter,
                "search": search,
                "now": datetime.utcnow()
            }
        )

    # Build query for actions (last 30 days)
    thirty_days_ago = datetime.utcnow() - timedelta(days=30)
    query = select(EmailAction).where(
        EmailAction.mailbox_id.in_(mailbox_ids),
        EmailAction.created_at >= thirty_days_ago
    )

    # Apply filters
    if action_filter:
        query = query.where(EmailAction.action == action_filter)

    if search:
        search_term = f"%{search}%"
        query = query.where(
            or_(
                EmailAction.from_address.ilike(search_term),
                EmailAction.subject.ilike(search_term)
            )
        )

    # Get total count for pagination
    count_query = select(func.count()).select_from(EmailAction).where(
        EmailAction.mailbox_id.in_(mailbox_ids),
        EmailAction.created_at >= thirty_days_ago
    )
    if action_filter:
        count_query = count_query.where(EmailAction.action == action_filter)
    if search:
        search_term = f"%{search}%"
        count_query = count_query.where(
            or_(
                EmailAction.from_address.ilike(search_term),
                EmailAction.subject.ilike(search_term)
            )
        )

    result = await db.execute(count_query)
    total_actions = result.scalar()
    total_pages = (total_actions + per_page - 1) // per_page  # Ceiling division

    # Fetch paginated actions
    query = query.order_by(EmailAction.created_at.desc())
    query = query.limit(per_page).offset((page - 1) * per_page)

    result = await db.execute(query)
    actions = result.scalars().all()

    # Calculate stats (all time, last 30 days)
    from sqlalchemy import case

    stats_query = select(
        func.count(EmailAction.id).label('total'),
        func.sum(
            case((EmailAction.action == 'archive', 1), else_=0)
        ).label('archived'),
        func.sum(
            case((EmailAction.action == 'trash', 1), else_=0)
        ).label('trashed'),
        func.sum(
            case((EmailAction.undone_at.isnot(None), 1), else_=0)
        ).label('undone')
    ).where(
        EmailAction.mailbox_id.in_(mailbox_ids),
        EmailAction.created_at >= thirty_days_ago
    )

    result = await db.execute(stats_query)
    stats_row = result.first()
    stats = {
        "total": stats_row.total or 0,
        "archived": stats_row.archived or 0,
        "trashed": stats_row.trashed or 0,
        "undone": stats_row.undone or 0
    }

    return templates.TemplateResponse(
        "portal/audit.html",
        {
            "request": request,
            "user": user,
            "actions": actions,
            "stats": stats,
            "page": page,
            "per_page": per_page,
            "total_pages": total_pages,
            "total_actions": total_actions,
            "action_filter": action_filter,
            "search": search or "",
            "now": datetime.utcnow()
        }
    )


@router.post("/api/actions/{action_id}/undo")
async def undo_action(
    action_id: str,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Undo an email action.

    Restores email to original location and marks action as undone.

    Path Params:
        action_id: UUID of email action to undo

    Returns:
        Success message

    Raises:
        404: Action not found
        400: Action cannot be undone (expired or already undone)
    """
    from datetime import datetime
    from app.models.email_action import EmailAction

    # Fetch action
    result = await db.execute(
        select(EmailAction).where(EmailAction.id == action_id)
    )
    action = result.scalar_one_or_none()

    if not action:
        raise HTTPException(status_code=404, detail="Action not found")

    # Verify action belongs to user's mailbox
    result = await db.execute(
        select(Mailbox).where(
            Mailbox.id == action.mailbox_id,
            Mailbox.user_id == user.id
        )
    )
    mailbox = result.scalar_one_or_none()

    if not mailbox:
        raise HTTPException(status_code=404, detail="Action not found")

    # Check if already undone
    if action.undone_at:
        raise HTTPException(status_code=400, detail="Action already undone")

    # Check if undo window expired
    if action.can_undo_until and action.can_undo_until < datetime.utcnow():
        raise HTTPException(status_code=400, detail="Undo window expired (30 days)")

    # TODO: Actually restore the email via Gmail API
    # For now, just mark as undone in database
    # In Week 5, add: await gmail_api.restore_email(mailbox, action.message_id, action.action)

    # Mark as undone
    action.undone_at = datetime.utcnow()
    await db.commit()

    return {
        "status": "undone",
        "message": "Action undone successfully",
        "action_id": str(action.id)
    }
