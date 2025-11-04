# Testing Requirements Skill

## Purpose
Enforce comprehensive testing for security-critical and safety-critical features in Inbox Janitor.

## Overview

Testing is **mandatory** for Inbox Janitor because:
- OAuth token theft = CATASTROPHIC
- Accidental email deletion = SEVERE
- Privacy violation (body storage) = CATASTROPHIC
- AI misclassification = HIGH PROBABILITY

**Pre-Commit Rule**: Run all security tests before EVERY commit.

## Testing Strategy

### Test Categories

1. **Security Tests** (CRITICAL) - Prevent token leaks, SQL injection, body storage
2. **Safety Tests** (CRITICAL) - Prevent data loss, email deletion
3. **Unit Tests** - Test individual functions and classes
4. **Integration Tests** - Test API endpoints and workflows
5. **Manual Tests** - Test on real Gmail before any user

## Security Tests (Run Before Every Commit)

### Required Security Tests

```bash
# Run all security tests
pytest tests/security/

# Individual tests
pytest tests/security/test_token_encryption.py
pytest tests/security/test_sql_injection.py
pytest tests/security/test_no_body_storage.py
pytest tests/security/test_key_not_in_codebase.py
```

### Test 1: Token Encryption

**File**: `tests/security/test_token_encryption.py`

**Purpose**: Verify OAuth tokens are encrypted before database storage

```python
import pytest
from app.core.security import encrypt_token, decrypt_token


def test_token_encryption():
    """Tokens must be encrypted before storage."""
    token = "ya29.a0AfB_sample_google_token"

    # Encrypt token
    encrypted = encrypt_token(token)

    # Verify encrypted != plaintext
    assert encrypted != token
    assert len(encrypted) > 0

    # Verify decryption works
    decrypted = decrypt_token(encrypted)
    assert decrypted == token


def test_token_not_in_logs(caplog):
    """Tokens must never appear in logs."""
    token = "ya29.a0AfB_sample_google_token"
    encrypted = encrypt_token(token)

    # Check logs don't contain plaintext token
    assert token not in caplog.text
    assert "ya29" not in caplog.text


def test_fernet_key_format():
    """Encryption key must be valid Fernet format."""
    from app.core.config import settings
    from cryptography.fernet import Fernet

    # Should not raise exception
    Fernet(settings.ENCRYPTION_KEY.encode())
```

### Test 2: No Body Storage

**File**: `tests/security/test_no_body_storage.py`

**Purpose**: Verify email bodies never stored in database

```python
import pytest
from app.models import EmailAction


def test_no_body_column_in_schema():
    """EmailAction model must not have body/html_body columns."""
    # Get all column names
    columns = [c.name for c in EmailAction.__table__.columns]

    # Verify no body-related columns
    forbidden_columns = ['body', 'html_body', 'content', 'full_text']
    for col in forbidden_columns:
        assert col not in columns, f"Column '{col}' found in EmailAction schema - SECURITY VIOLATION"


def test_snippet_truncation():
    """Snippets must be truncated to 200 chars max."""
    long_text = "x" * 500

    # Your truncation function
    from app.modules.classifier.service import truncate_snippet
    snippet = truncate_snippet(long_text)

    assert len(snippet) <= 200
```

### Test 3: SQL Injection Protection

**File**: `tests/security/test_sql_injection.py`

**Purpose**: Verify all queries use parameterized statements

```python
import pytest
from sqlalchemy import text
from app.core.database import get_db


@pytest.mark.asyncio
async def test_no_raw_sql_with_user_input(db_session):
    """Verify no raw SQL string concatenation."""
    malicious_email = "'; DROP TABLE users; --"

    # Good pattern (parameterized)
    from sqlalchemy import select
    from app.models import User

    result = await db_session.execute(
        select(User).where(User.email == malicious_email)
    )
    user = result.scalar_one_or_none()

    # Should return None, not execute injection
    assert user is None

    # Verify users table still exists
    result = await db_session.execute(text("SELECT COUNT(*) FROM users"))
    assert result.scalar() >= 0  # Table exists


def test_no_text_queries_in_codebase():
    """Scan codebase for dangerous text() queries."""
    import os
    from pathlib import Path

    dangerous_patterns = [
        'text(f"',  # f-string in text()
        'text("INSERT',  # Direct INSERT
        'text("DELETE',  # Direct DELETE
        'text("UPDATE',  # Direct UPDATE
    ]

    violations = []
    for py_file in Path('app').rglob('*.py'):
        content = py_file.read_text()
        for pattern in dangerous_patterns:
            if pattern in content:
                violations.append(f"{py_file}: {pattern}")

    assert len(violations) == 0, f"SQL injection risks found: {violations}"
```

### Test 4: Secrets Not in Codebase

**File**: `tests/security/test_key_not_in_codebase.py`

**Purpose**: Verify no secrets committed to git

```python
import pytest
import re
from pathlib import Path


def test_no_api_keys_in_code():
    """Scan for API keys in codebase."""
    patterns = [
        r'sk-proj-[a-zA-Z0-9]{20,}',  # OpenAI
        r'GOOGLE_CLIENT_SECRET\s*=\s*["\'][^"\']+["\']',  # Hardcoded secrets
        r'ya29\.[a-zA-Z0-9_-]+',  # Google OAuth tokens
        r'ENCRYPTION_KEY\s*=\s*["\'][^"\']+["\']',  # Hardcoded encryption key
    ]

    violations = []
    for py_file in Path('app').rglob('*.py'):
        content = py_file.read_text()
        for pattern in patterns:
            if re.search(pattern, content):
                violations.append(f"{py_file}: matches {pattern}")

    assert len(violations) == 0, f"Potential secrets found: {violations}"
```

## Safety Tests (Prevent Data Loss)

### Test 5: No Permanent Delete

**File**: `tests/safety/test_archive_not_delete.py`

**Purpose**: Verify `.delete()` method never called on emails

```python
import pytest
from pathlib import Path


def test_no_delete_method_in_codebase():
    """Gmail .delete() method is BANNED."""
    banned_patterns = [
        '.delete(',  # Gmail API delete
        '.trash(',   # Acceptable (30-day recovery)
        'permanently_delete',  # Any permanent delete
    ]

    violations = []
    for py_file in Path('app').rglob('*.py'):
        content = py_file.read_text()
        for pattern in banned_patterns:
            if pattern in content and 'delete' in pattern:
                violations.append(f"{py_file}: contains {pattern}")

    # .trash() is OK, .delete() is NOT
    assert all('.trash' in v for v in violations), f"Permanent delete found: {violations}"
```

### Test 6: Undo Flow Works

**File**: `tests/safety/test_undo_flow.py`

**Purpose**: Verify undo restores emails correctly

```python
import pytest
from datetime import datetime, timedelta
from app.models import EmailAction


@pytest.mark.asyncio
async def test_undo_within_30_days(db_session):
    """Undo should work for actions <30 days old."""
    from app.modules.executor.service import undo_action

    # Create action (simulated)
    action = EmailAction(
        mailbox_id="test-mailbox-uuid",
        message_id="msg123",
        from_address="test@example.com",
        subject="Test",
        action="archive",
        can_undo_until=datetime.utcnow() + timedelta(days=30)
    )
    db_session.add(action)
    await db_session.commit()

    # Undo should succeed
    result = await undo_action(action.id, db_session)
    assert result is True

    # Action should be marked as undone
    await db_session.refresh(action)
    assert action.undone_at is not None


@pytest.mark.asyncio
async def test_undo_expired_fails(db_session):
    """Undo should fail for actions >30 days old."""
    from app.modules.executor.service import undo_action

    action = EmailAction(
        mailbox_id="test-mailbox-uuid",
        message_id="msg456",
        from_address="test@example.com",
        subject="Old Email",
        action="archive",
        can_undo_until=datetime.utcnow() - timedelta(days=1)  # Expired
    )
    db_session.add(action)
    await db_session.commit()

    # Undo should fail
    with pytest.raises(Exception):
        await undo_action(action.id, db_session)
```

### Test 7: Exception Keywords Protect Emails

**File**: `tests/safety/test_job_offer_safety.py`

**Purpose**: Verify critical emails never trashed

```python
import pytest


def test_job_offer_never_trashed():
    """Emails with 'job' or 'offer' keywords must be kept."""
    from app.modules.classifier.service import classify_email

    email = {
        'subject': 'Job Offer - Software Engineer',
        'from': 'hr@company.com',
        'snippet': 'We are pleased to offer you...',
        'category': 'CATEGORY_PROMOTIONS',  # Even if promo category
        'has_unsubscribe': True  # Even if marketing
    }

    result = classify_email(email)

    # Must be KEEP, never TRASH
    assert result['action'] == 'keep'
    assert 'job' in result['reason'].lower() or 'offer' in result['reason'].lower()


def test_medical_email_safety():
    """Medical emails must never be trashed."""
    from app.modules.classifier.service import classify_email

    email = {
        'subject': 'Appointment Reminder - Dr. Smith',
        'from': 'noreply@healthcenter.com',
        'snippet': 'Your appointment is scheduled...',
        'category': 'CATEGORY_UPDATES'
    }

    result = classify_email(email)
    assert result['action'] in ['keep', 'archive']  # Never trash
```

## Unit Tests

### Testing Individual Functions

```python
# tests/unit/test_security.py
import pytest
from app.core.security import encrypt_token, decrypt_token, sanitize_for_logging


def test_encrypt_decrypt_roundtrip():
    """Encryption and decryption should be reversible."""
    original = "test_token_12345"
    encrypted = encrypt_token(original)
    decrypted = decrypt_token(encrypted)
    assert decrypted == original


def test_sanitize_removes_tokens():
    """Sanitize should remove sensitive data."""
    data = {
        'access_token': 'ya29.secret',
        'email': 'user@example.com',
        'subject': 'Test Email'
    }

    sanitized = sanitize_for_logging(data)

    assert 'access_token' not in sanitized
    assert sanitized['email'] == 'user@example.com'  # Non-sensitive OK
```

## Integration Tests

### Testing API Endpoints

```python
# tests/integration/test_auth_api.py
import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_oauth_callback_stores_encrypted_token(client: AsyncClient, db_session):
    """OAuth callback should store encrypted tokens."""
    # Simulate OAuth callback
    response = await client.get(
        "/auth/google/callback?code=test_code&state=test_state"
    )

    # Check token stored in database
    from app.models import Mailbox
    mailbox = await db_session.execute(
        select(Mailbox).where(Mailbox.email_address == "test@gmail.com")
    )
    mailbox = mailbox.scalar_one_or_none()

    # Verify token is encrypted (not plaintext)
    assert mailbox.encrypted_access_token != "test_code"
    assert len(mailbox.encrypted_access_token) > 50  # Fernet encrypted length
```

## Test Coverage Requirements

### Minimum Coverage Targets

- **Security-critical code**: 100% coverage
- **OAuth flows**: 100% coverage
- **Email actions (archive/trash)**: 100% coverage
- **Classification logic**: 95% coverage
- **API endpoints**: 90% coverage
- **Overall project**: 80% coverage

### Measuring Coverage

```bash
# Run tests with coverage
pytest --cov=app --cov-report=html

# View coverage report
open htmlcov/index.html

# Fail if coverage <80%
pytest --cov=app --cov-fail-under=80
```

## Test-Driven Development Workflow

When implementing new features:

### Pattern: Write Tests First

```python
# 1. Write failing test
def test_new_feature():
    from app.modules.new_module import new_function
    result = new_function("input")
    assert result == "expected_output"

# 2. Run test (should fail)
pytest tests/unit/test_new_module.py

# 3. Implement feature
def new_function(input):
    return "expected_output"

# 4. Run test (should pass)
pytest tests/unit/test_new_module.py

# 5. Refactor if needed, tests should still pass
```

## Running Tests

### Run All Tests

```bash
pytest
```

### Run Specific Test Categories

```bash
# Security tests only
pytest tests/security/

# Safety tests only
pytest tests/safety/

# Unit tests only
pytest tests/unit/

# Integration tests only
pytest tests/integration/
```

### Run Tests with Verbose Output

```bash
pytest -v
pytest -vv  # Extra verbose
```

### Run Tests Matching Pattern

```bash
# Run all tests with "token" in name
pytest -k token

# Run all tests with "OAuth" in name
pytest -k oauth
```

## Manual Testing Phases

Before ANY real users (even mom/sister):

### Phase 1: Developer Testing (Week 1-2)
- Test on YOUR OWN Gmail for 7 days
- Dry-run mode only (log actions, don't execute)
- Review every decision daily
- Log false positives
- Tune thresholds

### Phase 2: Internal Testing (Week 3)
- 5 tech-savvy friends
- Sandbox mode only
- Written consent required
- Daily feedback calls

### Phase 3: Closed Beta (Week 4-5)
- Mom, sister, 3 non-tech friends
- Monitor accounts daily
- Watch for missing email complaints

### Launch Criteria

Must pass before ANY user:
- [ ] 0 reports of lost emails
- [ ] 0 reports of privacy violations
- [ ] <1% undo rate (quality metric)
- [ ] 0 OAuth token leaks
- [ ] All security tests passing
- [ ] All safety tests passing

## Pre-Commit Hook

Set up automatic test running:

```bash
# .git/hooks/pre-commit
#!/bin/bash
pytest tests/security/ || exit 1
pytest tests/safety/ || exit 1
```

## CI/CD Integration

### GitHub Actions (Future)

```yaml
# .github/workflows/test.yml
name: Tests
on: [push, pull_request]
jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v2
      - name: Run security tests
        run: pytest tests/security/
      - name: Run safety tests
        run: pytest tests/safety/
      - name: Run all tests
        run: pytest --cov=app --cov-fail-under=80
```

## Related Skills

- **security-first.md** - Security patterns to test
- **fastapi-module-builder.md** - Module patterns to test
- **email-classification.md** - Classification logic to test
- **git-workflow.md** - Pre-commit test requirements
