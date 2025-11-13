# Task List: PRD-0006 Security Monitoring & Alerting

**PRD:** [PRD-0006: Security Monitoring & Alerting](./PRD-0006-security-monitoring-alerting.md)
**Total Estimated Time:** 24 hours (3 days)
**Priority:** P0 (CRITICAL - Deploy before billing launch)

---

## Task Overview

- [ ] **1.0 Create alerting infrastructure** (6 hours)
- [ ] **2.0 Add monitoring to WORKER_PAUSED** (4 hours)
- [ ] **3.0 Add monitoring to Sentry body detection** (4 hours)
- [ ] **4.0 Add monitoring to Gmail watch failures** (4 hours)
- [ ] **5.0 Create dashboard health indicators** (4 hours)
- [ ] **6.0 Deploy and verify** (2 hours)

---

## 1.0 Create alerting infrastructure (6 hours)

### 1.1 Create core alerting module (2 hours)
**Files:** `app/core/alerting.py` (new file)

**Implementation:**
```python
"""
Admin alerting system for security events and operational issues.

Sends alerts via:
- Email (Postmark)
- SMS (Twilio) - Future
- Slack (webhook) - Future
"""

import os
from datetime import datetime
from typing import List, Optional
import sentry_sdk
from app.modules.digest.email_service import send_email


async def send_admin_alert(
    title: str,
    message: str,
    severity: str = "MEDIUM",
    notify_via: List[str] = None
):
    """
    Send alert to admin via multiple channels.

    Args:
        title: Alert title (e.g., "Worker Paused >5 Minutes")
        message: Alert message with details
        severity: "CRITICAL", "HIGH", "MEDIUM", "LOW"
        notify_via: ["email", "sms", "slack"] (default: ["email"])

    Examples:
        await send_admin_alert(
            title="Worker Paused",
            message="Classification paused for 6 minutes",
            severity="HIGH",
            notify_via=["email"]
        )
    """
    if notify_via is None:
        notify_via = ["email"]

    alert = {
        "timestamp": datetime.utcnow().isoformat(),
        "severity": severity,
        "title": title,
        "message": message,
        "environment": os.getenv("ENVIRONMENT", "production")
    }

    # Log to Sentry (tagged for filtering)
    sentry_sdk.capture_message(
        f"[{severity}] {title}",
        level=_severity_to_sentry_level(severity),
        extras=alert
    )

    # Send email
    if "email" in notify_via:
        await _send_email_alert(alert)

    # Future: Add SMS
    if "sms" in notify_via and severity == "CRITICAL":
        # await _send_sms_alert(alert)
        pass

    # Future: Add Slack
    if "slack" in notify_via:
        # await _send_slack_alert(alert)
        pass


def _severity_to_sentry_level(severity: str) -> str:
    """Map severity to Sentry level."""
    mapping = {
        "CRITICAL": "fatal",
        "HIGH": "error",
        "MEDIUM": "warning",
        "LOW": "info"
    }
    return mapping.get(severity, "warning")


async def _send_email_alert(alert: dict):
    """Send alert email to admin."""
    admin_email = os.getenv("ADMIN_EMAIL", "admin@inboxjanitor.app")

    await send_email(
        to=admin_email,
        subject=f"[{alert['severity']}] {alert['title']}",
        template="admin_alert",
        data=alert
    )
```

**Acceptance Criteria:**
- [ ] Module created
- [ ] send_admin_alert() function implemented
- [ ] Email integration working
- [ ] Sentry integration working

---

### 1.2 Create admin alert email template (1 hour)
**Files:** `app/templates/emails/admin_alert.html` (new file)

**Template:**
```html
<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <style>
        .alert { padding: 20px; border-radius: 4px; margin: 20px 0; }
        .critical { background-color: #fee; border-left: 4px solid #f00; }
        .high { background-color: #ffd; border-left: 4px solid #f90; }
        .medium { background-color: #ffe; border-left: 4px solid: #ff0; }
    </style>
</head>
<body>
    <div class="alert {{ severity | lower }}">
        <h2>🚨 {{ title }}</h2>
        <p><strong>Severity:</strong> {{ severity }}</p>
        <p><strong>Time:</strong> {{ timestamp }}</p>
        <p><strong>Environment:</strong> {{ environment }}</p>
    </div>

    <div style="margin: 20px 0;">
        <h3>Details:</h3>
        <pre style="background: #f5f5f5; padding: 15px; border-radius: 4px;">{{ message }}</pre>
    </div>

    <hr>
    <p style="color: #666; font-size: 12px;">
        This is an automated alert from Inbox Janitor monitoring system.
    </p>
</body>
</html>
```

**Acceptance Criteria:**
- [ ] Template created
- [ ] Renders correctly for all severity levels
- [ ] Test email sent successfully

---

### 1.3 Create security violations database table (2 hours)
**Files:** `alembic/versions/XXX_add_security_monitoring.py` (new migration)

**Migration:**
```python
"""Add security monitoring tables

Revision ID: XXX
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

def upgrade():
    # Create security_violations table
    op.create_table(
        'security_violations',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('violation_type', sa.String(), nullable=False),  # 'body_content_logged', 'token_exposed', etc.
        sa.Column('severity', sa.String(), nullable=False),  # 'CRITICAL', 'HIGH', 'MEDIUM'
        sa.Column('event_metadata', postgresql.JSONB(), nullable=True),  # Forensic data (encrypted)
        sa.Column('detected_at', sa.TIMESTAMP(timezone=True), server_default=sa.text('NOW()'), nullable=False),
        sa.Column('resolved_at', sa.TIMESTAMP(timezone=True), nullable=True),
        sa.Column('resolution_notes', sa.Text(), nullable=True),
    )

    # Create index on detected_at
    op.create_index('idx_security_violations_detected_at', 'security_violations', ['detected_at'])

    # Create worker_pause_events table
    op.create_table(
        'worker_pause_events',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('mailbox_id', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('message_id', sa.String(), nullable=True),
        sa.Column('paused_at', sa.TIMESTAMP(timezone=True), server_default=sa.text('NOW()'), nullable=False),
        sa.Column('resumed_at', sa.TIMESTAMP(timezone=True), nullable=True),
        sa.Column('skipped_count', sa.Integer(), default=0),
    )

def downgrade():
    op.drop_table('worker_pause_events')
    op.drop_table('security_violations')
```

**Acceptance Criteria:**
- [ ] Migration created
- [ ] Run migration locally: `alembic upgrade head`
- [ ] Tables created successfully
- [ ] Indexes created

---

### 1.4 Add environment variable for admin email (30 minutes)
**Files:** Railway dashboard

**Actions:**
1. Add `ADMIN_EMAIL` to Railway secrets
2. Document in `.env.example`
3. Update `app/core/config.py` if needed

**Acceptance Criteria:**
- [ ] ADMIN_EMAIL added to Railway
- [ ] .env.example updated
- [ ] Test alert sent to admin email

---

### 1.5 Write tests for alerting system (30 minutes)
**Files:** `tests/core/test_alerting.py` (new file)

**Tests:**
```python
@pytest.mark.asyncio
async def test_send_admin_alert(mocker):
    """Test admin alert sends email."""
    mock_email = mocker.patch("app.core.alerting.send_email")

    await send_admin_alert(
        title="Test Alert",
        message="This is a test",
        severity="HIGH"
    )

    assert mock_email.called
    assert "HIGH" in mock_email.call_args[1]["subject"]


@pytest.mark.asyncio
async def test_send_admin_alert_logs_to_sentry(mocker):
    """Test admin alert logs to Sentry."""
    mock_sentry = mocker.patch("sentry_sdk.capture_message")

    await send_admin_alert(
        title="Test Alert",
        message="This is a test",
        severity="CRITICAL"
    )

    assert mock_sentry.called
    assert "CRITICAL" in mock_sentry.call_args[0][0]
```

**Acceptance Criteria:**
- [ ] All tests pass
- [ ] Email sending tested
- [ ] Sentry logging tested

---

## 2.0 Add monitoring to WORKER_PAUSED (4 hours)

### 2.1 Implement pause detection and alerting (2 hours)
**Files:** `app/tasks/classify.py`

**Changes:**
Replace lines 56-61 with comprehensive monitoring:

```python
async def check_worker_paused(mailbox_id: str, message_id: str, session: AsyncSession):
    """
    Check if worker is paused and handle appropriately.

    If paused:
    - Record pause event in database
    - Alert admin if paused >5 minutes
    - Return status for retry later
    """
    if os.getenv('WORKER_PAUSED', 'false').lower() != 'true':
        return None  # Not paused, continue

    # Record pause event
    await record_pause_event(mailbox_id, message_id, session)

    # Check pause duration
    pause_duration = await get_pause_duration(session)

    # Alert if paused >5 minutes
    if pause_duration > 300:  # 5 minutes
        await send_admin_alert(
            title="🚨 Worker Paused >5 Minutes",
            message=f"Classification worker has been paused for {pause_duration}s.\n\n"
                    f"Set WORKER_PAUSED=false in Railway to resume.\n"
                    f"Skipped emails will be processed when resumed.",
            severity="HIGH"
        )

    logger.warning(
        "Worker paused - classification skipped",
        extra={
            "mailbox_id": mailbox_id,
            "message_id": message_id,
            "pause_duration_seconds": pause_duration
        }
    )

    return {"status": "paused", "message": "Worker paused - will retry when resumed"}
```

**Helper Functions:**
```python
async def record_pause_event(mailbox_id: str, message_id: str, session: AsyncSession):
    """Record worker pause event in database."""
    from app.models.worker_pause_event import WorkerPauseEvent

    event = WorkerPauseEvent(
        mailbox_id=mailbox_id,
        message_id=message_id
    )
    session.add(event)
    await session.commit()


async def get_pause_duration(session: AsyncSession) -> int:
    """Get duration worker has been paused (seconds)."""
    from app.models.worker_pause_event import WorkerPauseEvent

    # Get earliest unresolved pause event
    result = await session.execute(
        select(WorkerPauseEvent.paused_at)
        .where(WorkerPauseEvent.resumed_at.is_(None))
        .order_by(WorkerPauseEvent.paused_at.asc())
        .limit(1)
    )

    first_pause = result.scalar_one_or_none()
    if first_pause:
        return (datetime.utcnow() - first_pause).total_seconds()

    return 0
```

**Acceptance Criteria:**
- [ ] Pause detection implemented
- [ ] Events recorded in database
- [ ] Alert sent after 5 minutes
- [ ] Helper functions working

---

### 2.2 Create WorkerPauseEvent model (1 hour)
**Files:** `app/models/worker_pause_event.py` (new file)

**Model:**
```python
from sqlalchemy import Column, String, Integer, TIMESTAMP
from sqlalchemy.dialects.postgresql import UUID
from app.models.base import Base
import uuid


class WorkerPauseEvent(Base):
    __tablename__ = "worker_pause_events"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    mailbox_id = Column(UUID(as_uuid=True), nullable=True)
    message_id = Column(String, nullable=True)
    paused_at = Column(TIMESTAMP(timezone=True), nullable=False, server_default="NOW()")
    resumed_at = Column(TIMESTAMP(timezone=True), nullable=True)
    skipped_count = Column(Integer, default=0)
```

**Acceptance Criteria:**
- [ ] Model created
- [ ] Model registered in `app/models/__init__.py`
- [ ] Migration applied

---

### 2.3 Write tests for worker pause monitoring (1 hour)
**Files:** `tests/tasks/test_classify.py`

**Tests:**
```python
@pytest.mark.asyncio
async def test_worker_pause_sends_alert_after_5_minutes(mocker, session):
    """Admin alerted if worker paused >5 minutes."""
    mock_alert = mocker.patch("app.core.alerting.send_admin_alert")

    # Simulate pause started 6 minutes ago
    from freezegun import freeze_time

    with freeze_time("2025-01-01 12:00:00"):
        # Record initial pause
        await record_pause_event("mailbox-123", "msg-456", session)

    with freeze_time("2025-01-01 12:06:00"):
        # Check after 6 minutes
        await check_worker_paused("mailbox-123", "msg-789", session)

    # Verify alert sent
    assert mock_alert.called
    assert "Worker Paused >5 Minutes" in mock_alert.call_args[1]["title"]
```

**Acceptance Criteria:**
- [ ] Test passes
- [ ] Alert triggered at correct time
- [ ] Database events recorded

---

## 3.0 Add monitoring to Sentry body detection (4 hours)

### 3.1 Implement body detection alerting (2 hours)
**Files:** `app/core/sentry.py`

**Changes:**
Replace lines 124-127 with comprehensive monitoring:

```python
async def check_body_content_violation(event: dict) -> dict:
    """
    Detect and handle email body content in Sentry events.

    If detected:
    - Send immediate admin alert
    - Store forensic metadata
    - Redact body content
    - Send redacted event to Sentry
    """
    event_str = str(event)

    if "html_body" not in event_str and "raw_content" not in event_str:
        return event  # No violation

    # Extract forensic metadata
    forensics = {
        "timestamp": datetime.utcnow().isoformat(),
        "event_id": event.get("event_id"),
        "user_id": event.get("user", {}).get("id"),
        "request_path": event.get("request", {}).get("url"),
        "function_name": _extract_function_name(event),
        "line_number": _extract_line_number(event)
    }

    # Store in database
    await store_security_violation(
        violation_type="body_content_logged",
        severity="CRITICAL",
        event_metadata=forensics
    )

    # Send IMMEDIATE admin alert
    await send_admin_alert(
        title="🚨 CRITICAL: Email Body Detected in Logs",
        message=f"Body content detected in Sentry event.\n\n"
                f"Event ID: {forensics['event_id']}\n"
                f"User ID: {forensics['user_id']}\n"
                f"Function: {forensics['function_name']}:{forensics['line_number']}\n"
                f"Time: {forensics['timestamp']}\n\n"
                f"IMMEDIATE ACTION REQUIRED: Review code and check for GDPR violation.",
        severity="CRITICAL",
        notify_via=["email"]  # Future: add SMS for CRITICAL
    )

    # Redact body content
    event_redacted = redact_body_content(event)

    # Tag redacted event
    event_redacted.setdefault("tags", {})
    event_redacted["tags"]["security_violation"] = "body_content_detected"

    return event_redacted  # Send redacted version


def _extract_function_name(event: dict) -> str:
    """Extract function name from Sentry event."""
    try:
        frames = event.get("exception", {}).get("values", [{}])[0].get("stacktrace", {}).get("frames", [])
        if frames:
            return frames[-1].get("function", "unknown")
    except:
        pass
    return "unknown"


def _extract_line_number(event: dict) -> int:
    """Extract line number from Sentry event."""
    try:
        frames = event.get("exception", {}).get("values", [{}])[0].get("stacktrace", {}).get("frames", [])
        if frames:
            return frames[-1].get("lineno", 0)
    except:
        pass
    return 0


async def store_security_violation(
    violation_type: str,
    severity: str,
    event_metadata: dict
):
    """Store security violation in database."""
    from app.models.security_violation import SecurityViolation
    from app.core.database import get_db

    async for session in get_db():
        violation = SecurityViolation(
            violation_type=violation_type,
            severity=severity,
            event_metadata=event_metadata
        )
        session.add(violation)
        await session.commit()
        break
```

**Acceptance Criteria:**
- [ ] Body detection alerting implemented
- [ ] Forensic data stored
- [ ] Event redacted before sending
- [ ] Admin alerted immediately

---

### 3.2 Create SecurityViolation model (1 hour)
**Files:** `app/models/security_violation.py` (new file)

**Model:**
```python
from sqlalchemy import Column, String, Text, TIMESTAMP
from sqlalchemy.dialects.postgresql import UUID, JSONB
from app.models.base import Base
import uuid


class SecurityViolation(Base):
    __tablename__ = "security_violations"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    violation_type = Column(String, nullable=False)
    severity = Column(String, nullable=False)
    event_metadata = Column(JSONB, nullable=True)
    detected_at = Column(TIMESTAMP(timezone=True), nullable=False, server_default="NOW()")
    resolved_at = Column(TIMESTAMP(timezone=True), nullable=True)
    resolution_notes = Column(Text, nullable=True)
```

**Acceptance Criteria:**
- [ ] Model created
- [ ] Model registered
- [ ] Migration applied

---

### 3.3 Write tests for body detection monitoring (1 hour)
**Files:** `tests/core/test_sentry.py`

**Tests:**
```python
@pytest.mark.asyncio
async def test_body_detection_sends_alert(mocker):
    """Admin alerted immediately on body content detection."""
    mock_alert = mocker.patch("app.core.alerting.send_admin_alert")

    event = {
        "exception": {
            "values": [{"value": "Error: html_body=<html>..."}]
        }
    }

    await check_body_content_violation(event)

    # Verify immediate alert
    assert mock_alert.called
    assert mock_alert.call_args[1]["severity"] == "CRITICAL"
    assert "email" in mock_alert.call_args[1]["notify_via"]


@pytest.mark.asyncio
async def test_body_detection_stores_forensics(mocker, session):
    """Forensic data stored for investigation."""
    event = {
        "event_id": "abc123",
        "user": {"id": "user-456"},
        "exception": {"values": [{"value": "html_body=<html>"}]}
    }

    await check_body_content_violation(event)

    # Verify forensics stored
    result = await session.execute(
        select(SecurityViolation).where(
            SecurityViolation.violation_type == "body_content_logged"
        )
    )

    violation = result.scalar_one()
    assert violation.event_metadata["event_id"] == "abc123"
    assert violation.severity == "CRITICAL"
```

**Acceptance Criteria:**
- [ ] All tests pass
- [ ] Alert tested
- [ ] Forensics storage tested

---

## 4.0 Add monitoring to Gmail watch failures (4 hours)

### 4.1 Implement inactive mailbox notifications (2 hours)
**Files:** `app/modules/ingest/gmail_watch.py`

**Changes:**
Replace line 73 with comprehensive handling:

```python
async def handle_inactive_mailbox(mailbox_id: str, user_id: str, user_email: str):
    """
    Handle inactive mailbox during watch registration.

    Actions:
    - Send email to user
    - Alert admin if >10 mailboxes inactive
    - Schedule retry in 6 hours
    """
    logger.warning(
        f"Mailbox inactive - watch registration skipped",
        extra={"mailbox_id": mailbox_id, "user_id": user_id}
    )

    # Send email to user
    await send_email(
        to=user_email,
        subject="Inbox Janitor: Gmail connection needs attention",
        template="mailbox_inactive",
        data={
            "mailbox_id": mailbox_id,
            "reconnect_url": f"{settings.APP_URL}/auth/gmail",
            "support_email": "support@inboxjanitor.app"
        }
    )

    # Check if mass issue
    inactive_count = await count_inactive_mailboxes(session)
    if inactive_count > 10:
        await send_admin_alert(
            title="⚠️ Mass Mailbox Inactivity",
            message=f"{inactive_count} mailboxes inactive.\n"
                    f"Possible OAuth token issue or Gmail API outage.",
            severity="HIGH"
        )

    # Schedule retry in 6 hours
    from app.tasks.ingest import retry_watch_registration
    retry_watch_registration.apply_async(
        args=[mailbox_id],
        countdown=21600  # 6 hours
    )
```

**Acceptance Criteria:**
- [ ] User email sent
- [ ] Admin alerted on mass issues
- [ ] Retry scheduled

---

### 4.2 Create mailbox inactive email template (1 hour)
**Files:** `app/templates/emails/mailbox_inactive.html` (new file)

**Template:**
```html
<!DOCTYPE html>
<html>
<body>
    <h2>Gmail Connection Needs Attention</h2>

    <p>We're having trouble connecting to your Gmail account.</p>

    <p>This usually happens when:</p>
    <ul>
        <li>You changed your Google password</li>
        <li>You revoked access to Inbox Janitor</li>
        <li>Gmail's authentication needs to be refreshed</li>
    </ul>

    <p>
        <a href="{{ reconnect_url }}" style="background: #4285f4; color: white; padding: 12px 24px; text-decoration: none; border-radius: 4px;">
            Reconnect Gmail
        </a>
    </p>

    <p>If you need help, reply to this email or contact {{ support_email }}.</p>
</body>
</html>
```

**Acceptance Criteria:**
- [ ] Template created
- [ ] Test email sent successfully

---

### 4.3 Write tests for inactive mailbox monitoring (1 hour)
**Files:** `tests/ingest/test_gmail_watch.py`

**Tests:**
```python
@pytest.mark.asyncio
async def test_inactive_mailbox_sends_user_email(mocker):
    """User notified when mailbox becomes inactive."""
    mock_email = mocker.patch("app.modules.digest.email_service.send_email")

    await handle_inactive_mailbox("mailbox-123", "user-456", "user@example.com")

    # Verify email sent
    assert mock_email.called
    assert "connection needs attention" in mock_email.call_args[1]["subject"].lower()


@pytest.mark.asyncio
async def test_inactive_mailbox_mass_alert(mocker, session):
    """Admin alerted if >10 mailboxes inactive."""
    mock_alert = mocker.patch("app.core.alerting.send_admin_alert")

    # Create 11 inactive mailboxes
    for i in range(11):
        mailbox = Mailbox(is_active=False)
        session.add(mailbox)
    await session.commit()

    await handle_inactive_mailbox("mailbox-123", "user-456", "user@example.com")

    # Verify alert sent
    assert mock_alert.called
    assert "Mass Mailbox Inactivity" in mock_alert.call_args[1]["title"]
```

**Acceptance Criteria:**
- [ ] All tests pass
- [ ] User email tested
- [ ] Mass alert tested

---

## 5.0 Create dashboard health indicators (4 hours)

### 5.1 Add health check endpoint (2 hours)
**Files:** `app/api/health.py` (new file)

**Endpoint:**
```python
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from app.core.database import get_db
from app.models.mailbox import Mailbox
from app.models.email_action import EmailAction
import os

router = APIRouter()


@router.get("/api/health")
async def health_check(session: AsyncSession = Depends(get_db)):
    """
    System health check endpoint.

    Returns:
        {
            "status": "healthy" | "degraded" | "unhealthy",
            "worker_paused": bool,
            "active_mailboxes": int,
            "inactive_mailboxes": int,
            "rate_limit_status": "ok" | "throttled",
            "last_classification": ISO timestamp
        }
    """
    # Check worker status
    worker_paused = os.getenv('WORKER_PAUSED', 'false').lower() == 'true'

    # Count mailboxes
    result = await session.execute(
        select(
            func.count(Mailbox.id).filter(Mailbox.is_active == True).label("active"),
            func.count(Mailbox.id).filter(Mailbox.is_active == False).label("inactive")
        )
    )
    counts = result.one()

    # Check last classification
    last_action = await session.execute(
        select(EmailAction.created_at)
        .order_by(EmailAction.created_at.desc())
        .limit(1)
    )
    last_classification = last_action.scalar_one_or_none()

    # Determine status
    if worker_paused or (last_classification and (datetime.utcnow() - last_classification).seconds > 600):
        status = "unhealthy"
    elif counts.inactive > counts.active * 0.2:
        status = "degraded"
    else:
        status = "healthy"

    return {
        "status": status,
        "worker_paused": worker_paused,
        "active_mailboxes": counts.active,
        "inactive_mailboxes": counts.inactive,
        "rate_limit_status": "ok",
        "last_classification": last_classification.isoformat() if last_classification else None
    }
```

**Acceptance Criteria:**
- [ ] Endpoint created
- [ ] Returns correct status
- [ ] Test with curl

---

### 5.2 Add health indicators to dashboard template (1 hour)
**Files:** `app/templates/dashboard.html`

**Changes:**
Add health indicators at top of dashboard:

```html
<!-- Health Indicators -->
<div class="health-indicators mb-4">
    {% if not mailbox.is_active %}
    <div class="alert alert-danger">
        <h4>🔴 Gmail Connection Lost</h4>
        <p>We couldn't connect to <strong>{{ mailbox.email_address }}</strong>.</p>
        <a href="/auth/gmail" class="btn btn-primary">Reconnect Gmail</a>
    </div>
    {% endif %}

    {% if worker_paused %}
    <div class="alert alert-info">
        ⏸️ Classification paused for maintenance. Will resume shortly.
    </div>
    {% endif %}

    <div class="health-status">
        <span class="badge badge-{{ health_status_color }}">
            {{ health_status_text }}
        </span>
        Last classified: {{ last_classification_time | humanize }}
    </div>
</div>
```

**Acceptance Criteria:**
- [ ] Indicators added
- [ ] Renders correctly
- [ ] Test with inactive mailbox

---

### 5.3 Write tests for health endpoint (1 hour)
**Files:** `tests/api/test_health.py` (new file)

**Tests:**
```python
@pytest.mark.asyncio
async def test_health_check_healthy(client, session):
    """Health check returns healthy status."""
    # Create active mailboxes
    for i in range(5):
        mailbox = Mailbox(is_active=True)
        session.add(mailbox)

    # Create recent classification
    action = EmailAction(created_at=datetime.utcnow())
    session.add(action)
    await session.commit()

    response = await client.get("/api/health")

    assert response.status_code == 200
    assert response.json()["status"] == "healthy"


@pytest.mark.asyncio
async def test_health_check_degraded(client, session):
    """Health check returns degraded if >20% mailboxes inactive."""
    # 2 active, 1 inactive (33% inactive)
    for i in range(2):
        session.add(Mailbox(is_active=True))
    session.add(Mailbox(is_active=False))
    await session.commit()

    response = await client.get("/api/health")

    assert response.json()["status"] == "degraded"
```

**Acceptance Criteria:**
- [ ] All tests pass
- [ ] Health statuses tested

---

## 6.0 Deploy and verify (2 hours)

### 6.1 Run migration and tests (30 minutes)
**Commands:**
```bash
# Run migration
alembic upgrade head

# Run tests
pytest tests/core/test_alerting.py tests/tasks/test_classify.py tests/core/test_sentry.py -v
```

**Acceptance Criteria:**
- [ ] Migration succeeds
- [ ] All tests pass

---

### 6.2 Create PR and deploy (30 minutes)
**Commands:**
```bash
git checkout -b feature/security-monitoring-alerting
git add .
git commit -m "Add security monitoring and admin alerting"
git push -u origin feature/security-monitoring-alerting
gh pr create --title "Add security monitoring and admin alerting" --body "..."
```

**Acceptance Criteria:**
- [ ] PR created
- [ ] CI passes
- [ ] Merged
- [ ] Deployed

---

### 6.3 Test alerting in production (1 hour)
**Actions:**
1. Trigger test alert:
   ```python
   # In Railway console
   from app.core.alerting import send_admin_alert
   await send_admin_alert(title="Test Alert", message="Testing", severity="LOW")
   ```

2. Verify email received
3. Check Sentry for log
4. Test health endpoint

**Acceptance Criteria:**
- [ ] Test alert received
- [ ] Sentry log created
- [ ] Health endpoint working

---

## Definition of Done

- [ ] All tasks completed
- [ ] Alerting infrastructure created
- [ ] WORKER_PAUSED monitoring added
- [ ] Sentry body detection monitoring added
- [ ] Gmail watch failure monitoring added
- [ ] Dashboard health indicators added
- [ ] All tests passing
- [ ] Deployed to production
- [ ] Test alert verified working

---

## Success Metrics

**Before Fix:**
- Worker pause: No alerts (silent)
- Body detection: Event dropped silently
- Inactive mailbox: No notification
- Incident response: Hours (manual log checking)

**After Fix:**
- Worker pause: Alert within 5 min ✅
- Body detection: Alert within 60 sec ✅
- Inactive mailbox: User email within 5 min ✅
- Incident response: <60 seconds ✅

---

**Time: 24 hours (3 days)**
