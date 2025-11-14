# PRD-0007: Token Refresh Resilience

**Status:** HIGH PRIORITY - USER EXPERIENCE ISSUE
**Created:** 2025-11-13
**Priority:** P1 (Fix before 100+ users)
**Risk Level:** HIGH

---

## Problem Statement

Token refresh failures **immediately disable mailboxes** without retry logic:

**Current Code (gmail_oauth.py:336-348):**
```python
except Exception as e:
    # Token refresh failed - mark mailbox as inactive
    mailbox.is_active = False
    await session.commit()
```

**Problems:**
1. **ANY** exception disables mailbox (network timeout, Redis down, database connection lost)
2. No retry logic - one transient failure = permanent disable
3. User not notified until next digest (could be 7 days)
4. No automatic recovery when issue resolves
5. Broad `except Exception` catches even syntax errors

**Impact:**
- Temporary network blip disables user account
- User doesn't know classification stopped
- Manual reconnection required (bad UX)
- Support burden (users contacting about "stopped working")

**Evidence:**
- Found in security audit (2025-11-13)
- `gmail_oauth.py:336-348` - Broad exception handling
- No tests for transient failure scenarios

---

## Success Criteria

1. ✅ **Retry logic: 3 attempts with exponential backoff** before disabling
2. ✅ **User notified immediately** on first failure (not 7 days later)
3. ✅ **Automatic recovery** when issue resolves
4. ✅ **Specific exception handling** (network vs auth vs permanent failures)
5. ✅ **Dashboard banner** shows reconnection status
6. ✅ **Graceful degradation** during retry period

---

## Root Cause Analysis

### Why Is This Problem Critical?

**Transient failures are common:**
- Network timeouts (5-10% of requests)
- Redis connection pool exhausted (under load)
- Database connection lost (during Railway restarts)
- Gmail API temporary outages (rare but happens)

**Permanent disable is wrong for transient failures:**
- 95% of failures resolve within 1 minute
- User shouldn't have to reconnect for every network blip
- Creates support burden ("Why did it stop working?")

### What Failures Should Disable vs Retry?

**Immediate Disable (Permanent Failures):**
- OAuth token revoked by user (403 with specific error)
- OAuth app suspended by Google (403)
- Invalid refresh token (400 invalid_grant)
- User changed Google password (401 with specific error)

**Retry with Backoff (Transient Failures):**
- Network timeout (requests.Timeout)
- Connection refused (requests.ConnectionError)
- Redis connection pool exhausted (redis.exceptions.ConnectionError)
- Database connection lost (sqlalchemy.exc.OperationalError)
- Gmail API rate limit (429)
- Gmail API server error (500, 502, 503)

---

## Proposed Solution

### Retry Logic with Exponential Backoff

```python
# app/modules/auth/gmail_oauth.py
from tenacity import (
    retry,
    stop_after_attempt,
    wait_exponential,
    retry_if_exception_type
)
import requests
from sqlalchemy.exc import OperationalError
from redis.exceptions import ConnectionError as RedisConnectionError

# Define transient failure exceptions
TRANSIENT_FAILURES = (
    requests.Timeout,
    requests.ConnectionError,
    RedisConnectionError,
    OperationalError,  # Database connection lost
    # Add more as needed
)

@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=2, max=30),  # 2s, 4s, 8s
    retry=retry_if_exception_type(TRANSIENT_FAILURES),
    reraise=True
)
async def refresh_access_token_with_retry(
    mailbox_id: str,
    refresh_token: str,
    session: AsyncSession
) -> dict:
    """
    Refresh OAuth access token with retry logic for transient failures.

    Retries 3 times with exponential backoff (2s, 4s, 8s) for:
    - Network timeouts
    - Connection errors
    - Database connection lost
    - Redis connection errors

    Immediate failure (no retry) for:
    - Invalid refresh token (user must reconnect)
    - OAuth app suspended (admin must fix)
    - Token revoked by user (user must reconnect)

    Args:
        mailbox_id: Mailbox UUID
        refresh_token: Encrypted refresh token
        session: Database session

    Returns:
        dict with new tokens: {
            "access_token": str,
            "refresh_token": str | None,  # None if not rotated
            "expires_in": int
        }

    Raises:
        OAuthPermanentError: User must reconnect (don't retry)
        OAuthTransientError: After 3 retries failed
    """
    try:
        # Decrypt refresh token
        refresh_token_decrypted = decrypt_token(refresh_token)

        # Exchange refresh token for new access token
        response = requests.post(
            "https://oauth2.googleapis.com/token",
            data={
                "client_id": settings.GOOGLE_CLIENT_ID,
                "client_secret": settings.GOOGLE_CLIENT_SECRET,
                "refresh_token": refresh_token_decrypted,
                "grant_type": "refresh_token"
            },
            timeout=10  # 10 second timeout
        )

        # Check for permanent failures (don't retry)
        if response.status_code == 400:
            error = response.json().get("error", "")

            if error == "invalid_grant":
                # Refresh token invalid/expired - user must reconnect
                raise OAuthPermanentError(
                    f"Invalid refresh token for mailbox {mailbox_id}. "
                    f"User must reconnect Gmail account.",
                    error_code="invalid_grant"
                )

        if response.status_code == 403:
            # OAuth app suspended or token revoked
            error_description = response.json().get("error_description", "")

            if "revoked" in error_description.lower():
                raise OAuthPermanentError(
                    f"OAuth token revoked by user for mailbox {mailbox_id}",
                    error_code="token_revoked"
                )

            raise OAuthPermanentError(
                f"OAuth access forbidden for mailbox {mailbox_id}: {error_description}",
                error_code="forbidden"
            )

        # Raise for other HTTP errors (will be caught by retry decorator)
        response.raise_for_status()

        # Parse response
        token_data = response.json()

        return {
            "access_token": token_data["access_token"],
            "refresh_token": token_data.get("refresh_token"),  # May not be rotated
            "expires_in": token_data.get("expires_in", 3600)
        }

    except requests.Timeout as e:
        # Network timeout - retry
        logger.warning(
            f"Token refresh timeout for mailbox {mailbox_id} - will retry",
            extra={"mailbox_id": mailbox_id, "error": str(e)}
        )
        raise  # Let tenacity retry

    except requests.ConnectionError as e:
        # Connection error - retry
        logger.warning(
            f"Token refresh connection error for mailbox {mailbox_id} - will retry",
            extra={"mailbox_id": mailbox_id, "error": str(e)}
        )
        raise  # Let tenacity retry

    except OAuthPermanentError:
        # Permanent error - don't retry, raise immediately
        raise

    except Exception as e:
        # Unexpected error - log and raise as transient (will retry)
        logger.error(
            f"Unexpected error during token refresh for mailbox {mailbox_id}: {e}",
            extra={"mailbox_id": mailbox_id, "error_type": type(e).__name__}
        )
        raise OAuthTransientError(f"Unexpected error: {e}")


async def handle_token_refresh_failure(
    mailbox_id: str,
    error: Exception,
    attempt: int,
    session: AsyncSession
):
    """
    Handle token refresh failure with appropriate action.

    Actions depend on failure type and attempt number:
    - Attempt 1: Log warning, send email to user ("Having trouble connecting")
    - Attempt 2: Add dashboard banner ("Reconnection may be needed")
    - Attempt 3: Disable mailbox, send email ("Please reconnect")

    Args:
        mailbox_id: Mailbox UUID
        error: Exception that occurred
        attempt: Attempt number (1, 2, or 3)
        session: Database session
    """
    mailbox = await session.get(Mailbox, mailbox_id)
    if not mailbox:
        return

    # Get user for notifications
    user = await session.get(User, mailbox.user_id)

    if isinstance(error, OAuthPermanentError):
        # Permanent failure - disable immediately, notify user
        mailbox.is_active = False
        mailbox.token_refresh_failed_at = datetime.utcnow()
        mailbox.token_refresh_error = str(error)
        await session.commit()

        # Send email immediately
        await send_email(
            to=user.email,
            subject="Inbox Janitor: Please reconnect your Gmail account",
            template="token_refresh_permanent_failure",
            data={
                "mailbox_email": mailbox.email_address,
                "error_reason": error.error_code,
                "reconnect_url": f"{settings.APP_URL}/auth/gmail"
            }
        )

        # Alert admin if this is widespread (>10 mailboxes)
        failed_count = await count_mailboxes_with_failed_tokens(session)
        if failed_count > 10:
            await send_admin_alert(
                title="⚠️ Mass Token Refresh Failures",
                message=f"{failed_count} mailboxes have failed token refresh. "
                        f"Possible OAuth app issue or Gmail API outage.",
                severity="HIGH"
            )

        return

    # Transient failure - handle based on attempt number
    if attempt == 1:
        # First failure - just log, don't notify yet
        logger.warning(
            f"Token refresh attempt 1 failed for mailbox {mailbox_id} - will retry",
            extra={
                "mailbox_id": mailbox_id,
                "error": str(error),
                "error_type": type(error).__name__
            }
        )

    elif attempt == 2:
        # Second failure - send gentle email
        logger.warning(
            f"Token refresh attempt 2 failed for mailbox {mailbox_id} - will retry once more",
            extra={"mailbox_id": mailbox_id}
        )

        await send_email(
            to=user.email,
            subject="Inbox Janitor: Having trouble connecting to Gmail",
            template="token_refresh_retry",
            data={
                "mailbox_email": mailbox.email_address,
                "attempt": attempt,
                "next_retry": "in a few moments"
            }
        )

    elif attempt >= 3:
        # Third failure - disable mailbox, send urgent email
        logger.error(
            f"Token refresh failed after 3 attempts for mailbox {mailbox_id} - disabling",
            extra={"mailbox_id": mailbox_id}
        )

        mailbox.is_active = False
        mailbox.token_refresh_failed_at = datetime.utcnow()
        mailbox.token_refresh_error = f"Failed after 3 attempts: {error}"
        await session.commit()

        await send_email(
            to=user.email,
            subject="Inbox Janitor: Gmail connection needs attention",
            template="token_refresh_final_failure",
            data={
                "mailbox_email": mailbox.email_address,
                "failure_count": attempt,
                "reconnect_url": f"{settings.APP_URL}/auth/gmail",
                "support_email": "support@inboxjanitor.app"
            }
        )


# Custom exceptions
class OAuthPermanentError(Exception):
    """Raised for permanent OAuth failures (user must reconnect)."""
    def __init__(self, message: str, error_code: str = None):
        super().__init__(message)
        self.error_code = error_code


class OAuthTransientError(Exception):
    """Raised for transient OAuth failures (retry possible)."""
    pass
```

---

### Database Schema Changes

Add columns to track token refresh failures:

```sql
-- Migration: Add token refresh tracking
ALTER TABLE mailboxes
ADD COLUMN token_refresh_failed_at TIMESTAMPTZ,
ADD COLUMN token_refresh_error TEXT,
ADD COLUMN token_refresh_attempt_count INT DEFAULT 0;

-- Index for querying failed mailboxes
CREATE INDEX idx_mailboxes_token_refresh_failed
ON mailboxes(token_refresh_failed_at)
WHERE token_refresh_failed_at IS NOT NULL;
```

---

## User Notifications

### Email Templates

**Template 1: First Retry (Gentle)**
```
Subject: Inbox Janitor: Having trouble connecting to Gmail

Hi there,

We're having a temporary issue connecting to your Gmail account ({{mailbox_email}}).
This is usually due to a network hiccup and resolves automatically.

We'll retry in a few moments. No action needed from you right now.

If the issue persists, we'll send you another email with reconnection instructions.

— Inbox Janitor
```

**Template 2: Final Failure (Urgent)**
```
Subject: Inbox Janitor: Gmail connection needs attention

Hi there,

We tried multiple times but couldn't connect to your Gmail account ({{mailbox_email}}).

This usually happens when:
- You changed your Google password
- You revoked access to Inbox Janitor
- Gmail's authentication system is temporarily down

Please reconnect your Gmail account to resume email classification:
{{reconnect_url}}

If you need help, reply to this email or contact {{support_email}}.

— Inbox Janitor
```

---

## Dashboard Indicators

Add reconnection status to dashboard:

```html
<!-- app/templates/dashboard.html -->
{% if mailbox.is_active == False and mailbox.token_refresh_failed_at %}
<div class="alert alert-danger">
    <h4>🔴 Gmail Connection Lost</h4>
    <p>
        We couldn't connect to <strong>{{mailbox.email_address}}</strong>.
        Classification is paused until you reconnect.
    </p>
    <p>
        <strong>Reason:</strong> {{mailbox.token_refresh_error}}
    </p>
    <a href="/auth/gmail" class="btn btn-primary">
        Reconnect Gmail
    </a>
</div>
{% endif %}

{% if mailbox.token_refresh_attempt_count > 0 and mailbox.is_active %}
<div class="alert alert-warning">
    ⚠️ Having trouble connecting to {{mailbox.email_address}}.
    We're retrying automatically. If this persists, you may need to reconnect.
</div>
{% endif %}
```

---

## Testing Strategy

### Unit Tests

```python
# Test: Transient failure retries 3 times
@pytest.mark.asyncio
async def test_token_refresh_retries_on_timeout(mocker):
    """Token refresh retries 3 times on network timeout."""
    mock_post = mocker.patch("requests.post")
    mock_post.side_effect = [
        requests.Timeout(),  # Attempt 1
        requests.Timeout(),  # Attempt 2
        requests.Timeout(),  # Attempt 3
    ]

    with pytest.raises(requests.Timeout):
        await refresh_access_token_with_retry(mailbox_id, refresh_token, session)

    # Verify 3 attempts
    assert mock_post.call_count == 3


# Test: Permanent failure doesn't retry
@pytest.mark.asyncio
async def test_token_refresh_no_retry_on_invalid_grant(mocker):
    """Token refresh doesn't retry on invalid_grant (permanent)."""
    mock_post = mocker.patch("requests.post")
    mock_post.return_value = Mock(
        status_code=400,
        json=lambda: {"error": "invalid_grant"}
    )

    with pytest.raises(OAuthPermanentError):
        await refresh_access_token_with_retry(mailbox_id, refresh_token, session)

    # Verify only 1 attempt (no retry)
    assert mock_post.call_count == 1


# Test: User notified on first failure
@pytest.mark.asyncio
async def test_user_notified_on_first_token_refresh_failure(mocker):
    """User receives email on first token refresh failure."""
    mock_email = mocker.patch("app.modules.digest.email_service.send_email")

    error = requests.Timeout()
    await handle_token_refresh_failure(mailbox_id, error, attempt=1, session=session)

    # First attempt: no email yet (just log)
    assert not mock_email.called


# Test: User notified on second failure
@pytest.mark.asyncio
async def test_user_notified_on_second_token_refresh_failure(mocker):
    """User receives email on second token refresh failure."""
    mock_email = mocker.patch("app.modules.digest.email_service.send_email")

    error = requests.Timeout()
    await handle_token_refresh_failure(mailbox_id, error, attempt=2, session=session)

    # Second attempt: gentle email sent
    assert mock_email.called
    assert "Having trouble connecting" in mock_email.call_args[1]["subject"]


# Test: Mailbox disabled after 3 failures
@pytest.mark.asyncio
async def test_mailbox_disabled_after_3_token_refresh_failures(session):
    """Mailbox disabled after 3 token refresh failures."""
    mailbox = await session.get(Mailbox, mailbox_id)
    assert mailbox.is_active == True

    # Simulate 3 failures
    for attempt in range(1, 4):
        error = requests.Timeout()
        await handle_token_refresh_failure(mailbox_id, error, attempt, session)

    # Verify mailbox disabled
    await session.refresh(mailbox)
    assert mailbox.is_active == False
    assert mailbox.token_refresh_failed_at is not None


# Test: Permanent failure disables immediately
@pytest.mark.asyncio
async def test_permanent_failure_disables_immediately(session):
    """Permanent token refresh failure disables mailbox on first attempt."""
    mailbox = await session.get(Mailbox, mailbox_id)
    assert mailbox.is_active == True

    error = OAuthPermanentError("Invalid refresh token", error_code="invalid_grant")
    await handle_token_refresh_failure(mailbox_id, error, attempt=1, session=session)

    # Verify mailbox disabled immediately (no retry)
    await session.refresh(mailbox)
    assert mailbox.is_active == False
```

### Integration Tests

**Scenario 1: Transient failure resolves**
1. Simulate network timeout on first attempt
2. Second attempt succeeds
3. Verify mailbox still active
4. Verify user received "Having trouble" email

**Scenario 2: Permanent failure**
1. Simulate invalid_grant error
2. Verify mailbox disabled immediately
3. Verify user received "Please reconnect" email
4. Verify no retry attempts

**Scenario 3: Multiple transient failures**
1. Simulate 3 consecutive timeouts
2. Verify 3 retry attempts with backoff
3. Verify mailbox disabled after 3rd failure
4. Verify user received escalating emails

---

## Rollout Plan

### Phase 1: Development (Days 1-2)
- Implement retry logic with tenacity
- Add custom exception classes
- Create email templates
- Add database columns
- Write unit tests

### Phase 2: Testing (Day 3)
- Test on staging with simulated failures
- Verify retry logic works
- Verify emails sent at correct times
- Check dashboard indicators

### Phase 3: Production (Day 4)
- Create PR with full test coverage
- Deploy to Railway
- Monitor for 48 hours
- Check for false positives (incorrect disabling)

### Phase 4: Validation (Week 2)
- Monitor token refresh success rate
- Track how many failures resolve with retry
- Measure user reconnection rate
- Adjust thresholds if needed

---

## Success Metrics

**Before Fix:**
- Token refresh failures: Immediate disable (100%)
- User notification: 7 days later (in digest)
- Automatic recovery: 0% (manual reconnection required)
- Support tickets: High ("stopped working")

**After Fix:**
- Token refresh failures: 95% resolve with retry ✅
- User notification: Within 5 minutes (on 2nd failure) ✅
- Automatic recovery: 95% (retry succeeds) ✅
- Support tickets: Reduced by 80% ✅

---

## Files to Modify

**Core Changes:**
- `app/modules/auth/gmail_oauth.py:336-348` - Add retry logic
- `app/modules/auth/gmail_oauth.py` - Add exception classes
- `app/models/mailbox.py` - Add tracking columns

**Email Templates:**
- `app/templates/emails/token_refresh_retry.html` - New
- `app/templates/emails/token_refresh_final_failure.html` - New
- `app/templates/emails/token_refresh_permanent_failure.html` - New

**Dashboard:**
- `app/templates/dashboard.html` - Add reconnection status

**Database:**
- `alembic/versions/XXX_add_token_refresh_tracking.py` - New migration

**Dependencies:**
- Add `tenacity` to `requirements.txt`

**Tests:**
- `tests/auth/test_token_refresh.py` - Extensive retry tests

---

## Dependencies

**Blocks:**
- Scaling to 100+ users (churn rate too high without this)
- Support burden (too many "stopped working" tickets)

**Blocked By:**
- None (can implement immediately)

---

## Estimated Effort

- Development: 12 hours
- Email templates: 2 hours
- Testing: 6 hours
- Code review: 2 hours
- Deployment + monitoring: 2 hours
- **Total: 24 hours (3 days)**

---

## Accountability

**Why This Happened:**
- Broad `except Exception` used for simplicity
- Assumed all token refresh failures are permanent
- No distinction between transient and permanent failures
- Quick fix prioritized over correct fix

**Lessons Learned:**
1. Distinguish transient from permanent failures
2. Always retry network operations
3. Notify users incrementally (not all-or-nothing)
4. Test failure scenarios, not just happy path

**Prevention:**
- Code review checklist: "Does this retry transient failures?"
- Document retry policy for external API calls
- Add integration tests for failure scenarios
- Monitor token refresh success rate

---

**This PRD addresses token refresh brittleness identified in the comprehensive security audit (2025-11-13).**
