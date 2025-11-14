# PRD-0006: Security Monitoring & Alerting

**Status:** CRITICAL - SILENT FAILURES IN PRODUCTION
**Created:** 2025-11-13
**Priority:** P0 (Deploy before billing launch)
**Risk Level:** HIGH

---

## Problem Statement

Three critical security events happen **silently** without admin notification:

1. **WORKER_PAUSED bypass** (classify.py:56-61)
   - Environment variable allows pausing entire classification pipeline
   - Emails silently skip classification (no database record)
   - User expects classification but nothing happens
   - No alert if worker paused >5 minutes

2. **Sentry body content detection** (sentry.py:124-127)
   - If email body accidentally logged, event dropped silently
   - Only logs to application logs (which might also contain body)
   - No admin notification of privacy violation
   - No forensic record for investigation

3. **Gmail watch registration failures** (gmail_watch.py:73)
   - Inactive mailboxes skip watch setup (only logs warning)
   - User connected Gmail but gets no real-time updates
   - No email notification to user
   - No dashboard indicator of inactive state

**Impact:**
- Security violations happen without investigation
- User expectations not met (emails not classified)
- No operational visibility into system health
- Incident response delayed (admin doesn't know there's a problem)

---

## Success Criteria

1. ✅ **Admin notified within 60 seconds** of any security event
2. ✅ **User notified within 5 minutes** of service degradation
3. ✅ **Forensic logs preserved** for all security violations
4. ✅ **Dashboard indicators** show system health status
5. ✅ **Automated recovery** where possible (e.g., retry watch registration)

---

## Proposed Solutions

### Solution 1: Worker Pause Monitoring

**Current (Silent):**
```python
if os.getenv('WORKER_PAUSED', 'false').lower() == 'true':
    logger.info(f"Worker paused - skipping classification...")
    return {"status": "paused"}  # No notification, no database record
```

**Fixed (Monitored):**
```python
async def check_worker_paused(mailbox_id: str, message_id: str):
    """
    Check if worker is paused and handle appropriately.

    If paused:
    - Log to database (audit trail)
    - Send admin alert if paused >5 minutes
    - Return status for retry later
    """
    if os.getenv('WORKER_PAUSED', 'false').lower() == 'true':
        # Record pause event in database
        await record_pause_event(mailbox_id, message_id)

        # Check how long worker has been paused
        pause_duration = await get_pause_duration()

        # Alert admin if paused >5 minutes
        if pause_duration > 300:  # 5 minutes
            await send_admin_alert(
                title="🚨 Worker Paused >5 Minutes",
                message=f"Classification worker paused for {pause_duration}s. "
                        f"Set WORKER_PAUSED=false to resume.",
                severity="HIGH"
            )

        # Log for monitoring
        logger.warning(
            f"Worker paused - classification skipped",
            extra={
                "mailbox_id": mailbox_id,
                "message_id": message_id,
                "pause_duration_seconds": pause_duration
            }
        )

        return {"status": "paused", "message": "Worker paused - will retry when resumed"}

    return None  # Not paused, continue
```

**New Database Table:**
```sql
CREATE TABLE worker_pause_events (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    mailbox_id UUID REFERENCES mailboxes(id),
    message_id TEXT,
    paused_at TIMESTAMPTZ DEFAULT NOW(),
    resumed_at TIMESTAMPTZ,
    skipped_count INT DEFAULT 0
);
```

---

### Solution 2: Sentry Body Detection Alerting

**Current (Silent Drop):**
```python
if "html_body" in event_str or "raw_content" in event_str:
    logger.critical("SECURITY VIOLATION: Body content detected - event dropped")
    return None  # Drop silently
```

**Fixed (Alert & Preserve):**
```python
async def check_body_content_violation(event: dict) -> dict:
    """
    Detect and handle email body content in Sentry events.

    If detected:
    - Send immediate admin alert (email + SMS)
    - Preserve event metadata for forensics
    - Redact body content from event
    - Send redacted event to Sentry
    """
    event_str = str(event)

    if "html_body" in event_str or "raw_content" in event_str:
        # Extract forensic metadata
        forensics = {
            "timestamp": datetime.utcnow().isoformat(),
            "event_id": event.get("event_id"),
            "user_id": event.get("user", {}).get("id"),
            "request_path": event.get("request", {}).get("url"),
            "function_name": event.get("exception", {}).get("values", [{}])[0].get("stacktrace", {}).get("frames", [{}])[-1].get("function"),
            "line_number": event.get("exception", {}).get("values", [{}])[0].get("stacktrace", {}).get("frames", [{}])[-1].get("lineno")
        }

        # Store forensics in database (separate table, encrypted)
        await store_security_violation(forensics)

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
            notify_via=["email", "sms"]  # Both channels for critical
        )

        # Redact body content from event
        event_redacted = redact_body_content(event)

        # Send redacted event to Sentry with tag
        event_redacted["tags"] = event_redacted.get("tags", {})
        event_redacted["tags"]["security_violation"] = "body_content_detected"

        return event_redacted  # Send redacted version, not None

    return event  # No violation, send as-is
```

**New Database Table:**
```sql
CREATE TABLE security_violations (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    violation_type TEXT NOT NULL,  -- 'body_content_logged', 'token_exposed', etc.
    severity TEXT NOT NULL,  -- 'CRITICAL', 'HIGH', 'MEDIUM'
    event_metadata JSONB,  -- Forensic data (encrypted)
    detected_at TIMESTAMPTZ DEFAULT NOW(),
    resolved_at TIMESTAMPTZ,
    resolution_notes TEXT
);
```

---

### Solution 3: Gmail Watch Failure Notifications

**Current (Silent):**
```python
logger.warning(f"Skipping watch registration for inactive mailbox {mailbox_id}")
```

**Fixed (User + Admin Notified):**
```python
async def handle_inactive_mailbox(mailbox_id: str, user_id: str):
    """
    Handle inactive mailbox during watch registration.

    Actions:
    - Send email to user: "Gmail connection inactive - please reconnect"
    - Show banner in dashboard: "Real-time updates paused"
    - Alert admin if >10 mailboxes inactive (mass issue)
    - Schedule retry in 6 hours
    """
    # Log for monitoring
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

    # Update dashboard state (user will see banner)
    await set_mailbox_dashboard_state(
        mailbox_id=mailbox_id,
        state="inactive",
        message="Real-time updates paused. Please reconnect your Gmail account."
    )

    # Check if this is a mass issue
    inactive_count = await count_inactive_mailboxes()
    if inactive_count > 10:
        await send_admin_alert(
            title="⚠️ Mass Mailbox Inactivity",
            message=f"{inactive_count} mailboxes inactive. "
                    f"Possible OAuth token issue or Gmail API outage.",
            severity="HIGH"
        )

    # Schedule retry in 6 hours
    await schedule_watch_retry(mailbox_id, delay_hours=6)
```

---

## Alert Channels & Configuration

### Admin Alert System

**Implementation:**
```python
# app/core/alerting.py
from postmark import PostmarkClient
import os

async def send_admin_alert(
    title: str,
    message: str,
    severity: str = "MEDIUM",
    notify_via: list = ["email"]
):
    """
    Send alert to admin via multiple channels.

    Args:
        title: Alert title (e.g., "Worker Paused >5 Minutes")
        message: Alert message with details
        severity: "CRITICAL", "HIGH", "MEDIUM", "LOW"
        notify_via: ["email", "sms", "slack"]  (future: add SMS/Slack)
    """
    # Format alert
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
        level=severity.lower(),
        extras=alert
    )

    # Send email
    if "email" in notify_via:
        await send_email(
            to=os.getenv("ADMIN_EMAIL", "admin@inboxjanitor.app"),
            subject=f"[{severity}] {title}",
            template="admin_alert",
            data=alert
        )

    # Future: Add SMS via Twilio
    if "sms" in notify_via and severity == "CRITICAL":
        # await send_sms(os.getenv("ADMIN_PHONE"), message)
        pass  # TODO: Implement Twilio integration

    # Future: Add Slack via webhook
    if "slack" in notify_via:
        # await send_slack_message(os.getenv("SLACK_WEBHOOK"), alert)
        pass  # TODO: Implement Slack integration
```

**Environment Variables:**
```bash
# Railway secrets
ADMIN_EMAIL=admin@inboxjanitor.app
ADMIN_PHONE=+1234567890  # Future: SMS alerts
SLACK_WEBHOOK_URL=...    # Future: Slack alerts
```

---

## Dashboard Health Indicators

Add system health indicators to dashboard:

**New Dashboard Section:**
```html
<!-- app/templates/dashboard.html -->
<div class="health-indicators">
    {% if mailbox.is_active == False %}
    <div class="alert alert-warning">
        ⚠️ Gmail connection inactive. <a href="/auth/gmail">Reconnect now</a>
    </div>
    {% endif %}

    {% if worker_paused %}
    <div class="alert alert-info">
        ⏸️ Classification paused for maintenance. Will resume shortly.
    </div>
    {% endif %}

    {% if rate_limit_exceeded %}
    <div class="alert alert-warning">
        🐌 Processing slower than usual due to high volume. Your emails will be classified soon.
    </div>
    {% endif %}

    <div class="health-status">
        <span class="badge badge-{{ health_status_color }}">
            {{ health_status_text }}
        </span>
        Last classified: {{ last_classification_time }}
    </div>
</div>
```

**Health Check Endpoint:**
```python
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

    # Count active/inactive mailboxes
    result = await session.execute(
        select(
            func.count(Mailbox.id).filter(Mailbox.is_active == True).label("active"),
            func.count(Mailbox.id).filter(Mailbox.is_active == False).label("inactive")
        )
    )
    counts = result.one()

    # Check last classification time
    last_action = await session.execute(
        select(EmailAction.created_at)
        .order_by(EmailAction.created_at.desc())
        .limit(1)
    )
    last_classification = last_action.scalar_one_or_none()

    # Determine overall health
    if worker_paused or (last_classification and (datetime.utcnow() - last_classification).seconds > 600):
        status = "unhealthy"
    elif counts.inactive > counts.active * 0.2:  # >20% inactive
        status = "degraded"
    else:
        status = "healthy"

    return {
        "status": status,
        "worker_paused": worker_paused,
        "active_mailboxes": counts.active,
        "inactive_mailboxes": counts.inactive,
        "rate_limit_status": "ok",  # TODO: Check Redis rate limit usage
        "last_classification": last_classification.isoformat() if last_classification else None
    }
```

---

## Monitoring Dashboards

### Railway Metrics

**Add monitoring for:**
1. Worker pause duration (alert if >5 min)
2. Inactive mailbox count (alert if >20% of total)
3. Security violation count (alert on any)
4. Rate limit bypass count (alert on any)
5. Classification throughput (alert if drops >50%)

**Railway Dashboard Queries:**
```
# Worker pause duration
sum(rate(worker_pause_events_total[5m])) by (mailbox_id)

# Inactive mailbox percentage
(count(mailboxes{is_active="false"}) / count(mailboxes)) * 100

# Security violations (should be 0)
sum(security_violations_total)

# Rate limit bypasses (should be 0)
sum(rate_limit_bypass_total[1m])
```

---

## Testing Strategy

### Unit Tests
```python
# Test: Worker pause sends alert after 5 minutes
@pytest.mark.asyncio
async def test_worker_pause_alert_after_5_minutes(mocker):
    """Admin alerted if worker paused >5 minutes."""
    mock_alert = mocker.patch("app.core.alerting.send_admin_alert")

    # Simulate 6-minute pause
    with freeze_time("2025-01-01 12:00:00"):
        await set_worker_paused(True)

    with freeze_time("2025-01-01 12:06:00"):
        await check_worker_paused("mailbox-123", "msg-456")

    # Verify alert sent
    assert mock_alert.called
    assert "Worker Paused >5 Minutes" in mock_alert.call_args[1]["title"]

# Test: Sentry body detection sends alert
@pytest.mark.asyncio
async def test_sentry_body_detection_sends_alert(mocker):
    """Admin alerted immediately on body content detection."""
    mock_alert = mocker.patch("app.core.alerting.send_admin_alert")

    event = {"exception": {"values": [{"value": "Error: html_body=<html>..."}]}}
    await check_body_content_violation(event)

    # Verify immediate alert
    assert mock_alert.called
    assert mock_alert.call_args[1]["severity"] == "CRITICAL"
    assert "email" in mock_alert.call_args[1]["notify_via"]

# Test: Inactive mailbox sends user email
@pytest.mark.asyncio
async def test_inactive_mailbox_sends_user_email(mocker):
    """User notified when mailbox becomes inactive."""
    mock_email = mocker.patch("app.modules.digest.email_service.send_email")

    await handle_inactive_mailbox("mailbox-123", "user-456")

    # Verify email sent to user
    assert mock_email.called
    assert "connection needs attention" in mock_email.call_args[1]["subject"].lower()
```

---

## Rollout Plan

### Phase 1: Alerting Infrastructure (Day 1)
- Implement `send_admin_alert()` function
- Add environment variables (ADMIN_EMAIL)
- Create `security_violations` database table
- Create `worker_pause_events` database table
- Test alert delivery locally

### Phase 2: Monitoring Integration (Day 2)
- Add alerts to WORKER_PAUSED check
- Add alerts to Sentry body detection
- Add alerts to inactive mailbox handling
- Create health check endpoint
- Test all alert paths

### Phase 3: Dashboard Indicators (Day 3)
- Add health indicators to dashboard template
- Add mailbox inactive banner
- Add worker paused banner
- Test UI on staging

### Phase 4: Production Deployment (Day 4)
- Create PR with full test coverage
- Deploy to Railway
- Verify alerts working (trigger test alert)
- Monitor for 48 hours

---

## Success Metrics

**Before Fix:**
- Worker pause: No alerts (silent)
- Body content detection: Event dropped silently
- Inactive mailbox: No user notification
- Incident response time: Hours (admin must check logs)

**After Fix:**
- Worker pause: Alert within 5 minutes ✅
- Body content detection: Admin alert within 60 seconds ✅
- Inactive mailbox: User email within 5 minutes ✅
- Incident response time: <60 seconds ✅

---

## Files to Modify

**Core Changes:**
- `app/core/alerting.py` - New file for admin alerts
- `app/tasks/classify.py:56-61` - Add monitoring to WORKER_PAUSED
- `app/core/sentry.py:124-127` - Add alerting to body detection
- `app/modules/ingest/gmail_watch.py:73` - Add user notification

**Database:**
- `alembic/versions/XXX_add_security_monitoring.py` - New migration
- Add `security_violations` table
- Add `worker_pause_events` table

**Dashboard:**
- `app/templates/dashboard.html` - Add health indicators
- `app/modules/portal/routes.py` - Add health check endpoint

**Tests:**
- `tests/core/test_alerting.py` - New test file
- `tests/tasks/test_classify.py` - Add pause monitoring tests
- `tests/security/test_sentry.py` - Add alert tests

---

## Risks & Mitigations

| Risk | Impact | Mitigation |
|------|--------|-----------|
| Alert fatigue (too many emails) | MEDIUM - Admin ignores alerts | Rate limit alerts (1 per 5 min per type) |
| Email delivery failure | HIGH - Admin not notified | Add Sentry fallback, log all alerts |
| Database table adds latency | LOW - Slower classification | Use async inserts, index properly |
| False positive alerts | MEDIUM - Wasted admin time | Test thoroughly before deployment |

---

## Dependencies

**Blocks:**
- Billing launch (must have incident detection)
- Scaling to 100+ users (need operational visibility)

**Blocked By:**
- None (can implement immediately)

---

## Estimated Effort

- Alerting infrastructure: 6 hours
- Monitoring integration: 8 hours
- Dashboard indicators: 4 hours
- Testing: 4 hours
- Deployment: 2 hours
- **Total: 24 hours (3 days)**

---

## Accountability

**Why This Happened:**
- "Log and continue" pattern used for operational issues
- No distinction between logging and alerting
- Assumed admin would monitor logs proactively (unrealistic)
- Focus on fixing bugs, not detecting when bugs happen

**Lessons Learned:**
1. Logging is for debugging, alerting is for operations
2. Critical events need immediate admin notification
3. Users must know when service is degraded
4. Forensic data must be preserved for security violations

**Prevention:**
- Code review checklist: "Does this need an alert?"
- Document alert policy: What events require notification?
- Test alert delivery in CI/CD
- Monthly: Review alert frequency, tune thresholds

---

**This PRD addresses silent failures identified in the comprehensive security audit (2025-11-13).**
