# Task List: PRD-0007 Token Refresh Resilience

**PRD:** [PRD-0007: Token Refresh Resilience](./PRD-0007-token-refresh-resilience.md)
**Total Estimated Time:** 24 hours (3 days)
**Priority:** P1 (HIGH - Fix before 100+ users)

---

## Task Overview

- [ ] **1.0 Add database columns for tracking** (2 hours)
- [ ] **2.0 Implement retry logic with tenacity** (8 hours)
- [ ] **3.0 Create user notification emails** (4 hours)
- [ ] **4.0 Add dashboard indicators** (3 hours)
- [ ] **5.0 Write comprehensive tests** (5 hours)
- [ ] **6.0 Deploy and monitor** (2 hours)

---

## 1.0 Add database columns for tracking (2 hours)

### 1.1 Create migration for token refresh tracking
**Files:** `alembic/versions/XXX_add_token_refresh_tracking.py`

**Migration:**
```sql
ALTER TABLE mailboxes
ADD COLUMN token_refresh_failed_at TIMESTAMPTZ,
ADD COLUMN token_refresh_error TEXT,
ADD COLUMN token_refresh_attempt_count INT DEFAULT 0;

CREATE INDEX idx_mailboxes_token_refresh_failed
ON mailboxes(token_refresh_failed_at)
WHERE token_refresh_failed_at IS NOT NULL;
```

**Acceptance Criteria:**
- [ ] Migration created
- [ ] Run `alembic upgrade head`
- [ ] Columns added successfully

---

### 1.2 Update Mailbox model
**Files:** `app/models/mailbox.py`

Add columns to model:
```python
token_refresh_failed_at = Column(TIMESTAMP(timezone=True), nullable=True)
token_refresh_error = Column(Text, nullable=True)
token_refresh_attempt_count = Column(Integer, default=0)
```

**Acceptance Criteria:**
- [ ] Model updated
- [ ] Tests still pass

---

## 2.0 Implement retry logic with tenacity (8 hours)

### 2.1 Add tenacity dependency
**Files:** `requirements.txt`

Add: `tenacity==8.2.3`

Run: `pip install -r requirements.txt`

**Acceptance Criteria:**
- [ ] Dependency added
- [ ] Installed successfully

---

### 2.2 Create custom exception classes
**Files:** `app/modules/auth/gmail_oauth.py`

```python
class OAuthPermanentError(Exception):
    """Permanent OAuth failure - user must reconnect."""
    def __init__(self, message: str, error_code: str = None):
        super().__init__(message)
        self.error_code = error_code


class OAuthTransientError(Exception):
    """Transient OAuth failure - retry possible."""
    pass
```

**Acceptance Criteria:**
- [ ] Exceptions defined
- [ ] Docstrings clear

---

### 2.3 Implement refresh_access_token_with_retry()
**Files:** `app/modules/auth/gmail_oauth.py`

See PRD-0007 for full implementation with:
- `@retry` decorator from tenacity
- 3 attempts with exponential backoff (2s, 4s, 8s)
- Distinguish permanent vs transient failures
- Handle invalid_grant, token_revoked, etc.

**Acceptance Criteria:**
- [ ] Function implemented
- [ ] Retry logic works
- [ ] Permanent failures don't retry
- [ ] Transient failures retry 3x

---

### 2.4 Implement handle_token_refresh_failure()
**Files:** `app/modules/auth/gmail_oauth.py`

Actions based on attempt number:
- Attempt 1: Log warning
- Attempt 2: Send gentle email to user
- Attempt 3: Disable mailbox, send urgent email

**Acceptance Criteria:**
- [ ] Function implemented
- [ ] Escalating notifications
- [ ] Database updated correctly

---

### 2.5 Replace existing token refresh code
**Files:** `app/modules/auth/gmail_oauth.py` (lines 336-348)

Replace broad `except Exception` with:
```python
try:
    tokens = await refresh_access_token_with_retry(mailbox_id, refresh_token, session)
    # Update tokens...
except OAuthPermanentError as e:
    await handle_token_refresh_failure(mailbox_id, e, attempt=1, session)
except OAuthTransientError as e:
    await handle_token_refresh_failure(mailbox_id, e, attempt=3, session)
```

**Acceptance Criteria:**
- [ ] Old code replaced
- [ ] Retry logic used
- [ ] Proper exception handling

---

## 3.0 Create user notification emails (4 hours)

### 3.1 Create "having trouble" email template
**Files:** `app/templates/emails/token_refresh_retry.html`

**Template:**
```html
<h2>Having trouble connecting to Gmail</h2>
<p>We're experiencing a temporary issue connecting to your Gmail account ({{ mailbox_email }}).</p>
<p>We'll retry automatically. No action needed right now.</p>
```

**Acceptance Criteria:**
- [ ] Template created
- [ ] Test email sent

---

### 3.2 Create "connection lost" email template
**Files:** `app/templates/emails/token_refresh_final_failure.html`

**Template:**
```html
<h2>Gmail Connection Lost</h2>
<p>We couldn't connect to {{ mailbox_email }} after multiple attempts.</p>
<a href="{{ reconnect_url }}">Reconnect Gmail</a>
```

**Acceptance Criteria:**
- [ ] Template created
- [ ] Test email sent

---

### 3.3 Create "reconnect immediately" email template
**Files:** `app/templates/emails/token_refresh_permanent_failure.html`

**Template:**
```html
<h2>Please Reconnect Your Gmail Account</h2>
<p>Your Gmail authentication needs to be refreshed.</p>
<p>Reason: {{ error_reason }}</p>
<a href="{{ reconnect_url }}">Reconnect Now</a>
```

**Acceptance Criteria:**
- [ ] Template created
- [ ] Test email sent

---

##4.0 Add dashboard indicators (3 hours)

### 4.1 Add reconnection banner to dashboard
**Files:** `app/templates/dashboard.html`

```html
{% if mailbox.is_active == False and mailbox.token_refresh_failed_at %}
<div class="alert alert-danger">
    <h4>🔴 Gmail Connection Lost</h4>
    <p>Reason: {{ mailbox.token_refresh_error }}</p>
    <a href="/auth/gmail">Reconnect Gmail</a>
</div>
{% endif %}
```

**Acceptance Criteria:**
- [ ] Banner added
- [ ] Shows error reason
- [ ] Reconnect link works

---

### 4.2 Add retry status indicator
**Files:** `app/templates/dashboard.html`

```html
{% if mailbox.token_refresh_attempt_count > 0 and mailbox.is_active %}
<div class="alert alert-warning">
    ⚠️ Having trouble connecting. Retrying automatically.
</div>
{% endif %}
```

**Acceptance Criteria:**
- [ ] Indicator added
- [ ] Shows during retry period

---

## 5.0 Write comprehensive tests (5 hours)

### 5.1 Test transient failure retries
**Files:** `tests/auth/test_token_refresh.py`

```python
@pytest.mark.asyncio
async def test_token_refresh_retries_on_timeout():
    """Retries 3 times on network timeout."""
    mock_post = mocker.patch("requests.post")
    mock_post.side_effect = [
        requests.Timeout(),
        requests.Timeout(),
        requests.Timeout(),
    ]

    with pytest.raises(requests.Timeout):
        await refresh_access_token_with_retry(mailbox_id, refresh_token, session)

    assert mock_post.call_count == 3
```

**Acceptance Criteria:**
- [ ] Test passes
- [ ] Verifies 3 attempts

---

### 5.2 Test permanent failure doesn't retry
**Files:** `tests/auth/test_token_refresh.py`

```python
@pytest.mark.asyncio
async def test_permanent_failure_no_retry():
    """invalid_grant doesn't retry."""
    mock_post.return_value = Mock(
        status_code=400,
        json=lambda: {"error": "invalid_grant"}
    )

    with pytest.raises(OAuthPermanentError):
        await refresh_access_token_with_retry(...)

    assert mock_post.call_count == 1  # Only 1 attempt
```

**Acceptance Criteria:**
- [ ] Test passes
- [ ] Verifies no retry

---

### 5.3 Test user notifications
**Files:** `tests/auth/test_token_refresh.py`

Test emails sent at correct attempt numbers.

**Acceptance Criteria:**
- [ ] All notification tests pass
- [ ] Emails sent at correct times

---

### 5.4 Test mailbox disabled after 3 failures
**Files:** `tests/auth/test_token_refresh.py`

```python
@pytest.mark.asyncio
async def test_mailbox_disabled_after_3_failures():
    """Mailbox disabled after 3 transient failures."""
    mailbox = await session.get(Mailbox, mailbox_id)
    assert mailbox.is_active == True

    for attempt in range(1, 4):
        await handle_token_refresh_failure(mailbox_id, error, attempt, session)

    await session.refresh(mailbox)
    assert mailbox.is_active == False
```

**Acceptance Criteria:**
- [ ] Test passes
- [ ] Mailbox disabled correctly

---

## 6.0 Deploy and monitor (2 hours)

### 6.1 Create PR
**Commands:**
```bash
git checkout -b feature/token-refresh-resilience
git add .
git commit -m "Add token refresh retry logic and user notifications"
git push -u origin feature/token-refresh-resilience
gh pr create --title "Add token refresh resilience (retry + notifications)" --body "..."
```

**Acceptance Criteria:**
- [ ] PR created
- [ ] CI passes

---

### 6.2 Deploy and monitor
**Actions:**
1. Merge PR
2. Monitor Railway logs for token refresh events
3. Simulate failure (change refresh token to invalid)
4. Verify retry logic executes
5. Verify user email sent
6. Monitor for 48 hours

**Acceptance Criteria:**
- [ ] Deployed successfully
- [ ] Retry logic works in production
- [ ] User notifications sent
- [ ] No regressions

---

## Definition of Done

- [ ] All tasks completed
- [ ] Database columns added
- [ ] Retry logic with tenacity implemented
- [ ] User notification emails created
- [ ] Dashboard indicators added
- [ ] All tests passing
- [ ] Deployed to production
- [ ] Monitored for 48 hours
- [ ] Token refresh success rate >95%

---

## Success Metrics

**Before Fix:**
- Immediate disable: 100%
- User notification delay: 7 days
- Automatic recovery: 0%

**After Fix:**
- Immediate disable: 5% (95% retry succeeds) ✅
- User notification: 5 minutes ✅
- Automatic recovery: 95% ✅

---

**Time: 24 hours (3 days)**
