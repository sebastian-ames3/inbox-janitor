# Task List: PRD-0004 Rate Limiting Architecture Fix

**PRD:** [PRD-0004: Rate Limiting Architecture Fix](./PRD-0004-rate-limiting-architecture-fix.md)
**Total Estimated Time:** 16 hours (2 days)
**Priority:** P0 (CRITICAL - Block all other work)

---

## Task Overview

- [ ] **1.0 Refactor GmailClient to async** (6 hours)
- [ ] **2.0 Update calling code to use async** (4 hours)
- [ ] **3.0 Update tests to async** (2 hours)
- [ ] **4.0 Deploy and verify** (4 hours)

---

## 1.0 Refactor GmailClient to async (6 hours)

### 1.1 Convert list_messages() to async (1 hour)
**Files:** `app/modules/ingest/gmail_client.py`

**Changes:**
- Change `def list_messages(...)` to `async def list_messages(...)`
- Change `self._check_rate_limit_sync(quota_units)` to `await self._check_rate_limit_async(quota_units)`
- Update docstring to indicate async usage
- Keep synchronous `_rate_limit()` call (uses time.sleep, not async)

**Acceptance Criteria:**
- [ ] Method signature is `async def`
- [ ] Rate limiter called with `await`
- [ ] Docstring updated with async example
- [ ] Code runs without errors (manual test)

**Code Example:**
```python
async def list_messages(
    self,
    query: str = "",
    max_results: int = 100,
    page_token: Optional[str] = None,
    label_ids: Optional[List[str]] = None
) -> Dict:
    """
    List messages matching query.

    Usage:
        client = GmailClient(mailbox)
        response = await client.list_messages(query='in:inbox')  # <-- NOTE: await
    """
    # Build request parameters...

    # Define operation function
    def operation():
        service = self._get_service()
        return service.users().messages().list(**params).execute()

    # Execute with retry and rate limiting
    response = await self._execute_with_retry_async(operation, "list_messages", quota_units=5)
    return response
```

---

### 1.2 Convert get_message() to async (1 hour)
**Files:** `app/modules/ingest/gmail_client.py`

**Changes:**
- Change `def get_message(...)` to `async def get_message(...)`
- Change `self._execute_with_retry(...)` to `await self._execute_with_retry_async(...)`
- Update docstring

**Acceptance Criteria:**
- [ ] Method signature is `async def`
- [ ] Execution uses async retry wrapper
- [ ] Docstring updated
- [ ] Security check remains (format != 'full')

---

### 1.3 Convert modify_message() to async (30 minutes)
**Files:** `app/modules/ingest/gmail_client.py`

**Changes:**
- Change `def modify_message(...)` to `async def modify_message(...)`
- Add `await self._check_rate_limit_async(quota_units=5)` at start
- Update error handling to async pattern

**Acceptance Criteria:**
- [ ] Method signature is `async def`
- [ ] Rate limiting enforced
- [ ] Error handling unchanged

---

### 1.4 Convert trash_message() to async (30 minutes)
**Files:** `app/modules/ingest/gmail_client.py`

**Changes:**
- Change `def trash_message(...)` to `async def trash_message(...)`
- Add `await self._check_rate_limit_async(quota_units=5)`
- Update docstring

**Acceptance Criteria:**
- [ ] Method signature is `async def`
- [ ] Rate limiting enforced
- [ ] Docstring emphasizes reversibility (uses trash, not delete)

---

### 1.5 Convert untrash_message() to async (30 minutes)
**Files:** `app/modules/ingest/gmail_client.py`

**Changes:**
- Change `def untrash_message(...)` to `async def untrash_message(...)`
- Add rate limiting
- Update docstring

**Acceptance Criteria:**
- [ ] Method signature is `async def`
- [ ] Rate limiting enforced

---

### 1.6 Create async execute wrapper (1 hour)
**Files:** `app/modules/ingest/gmail_client.py`

**Changes:**
- Rename `_execute_with_retry` to `_execute_with_retry_async`
- Make method async: `async def _execute_with_retry_async(...)`
- Change `self._check_rate_limit_sync(...)` to `await self._check_rate_limit_async(...)`
- Keep synchronous `time.sleep()` for backoff (acceptable for now)

**Acceptance Criteria:**
- [ ] Method is async
- [ ] Rate limiter called with await
- [ ] Retry logic unchanged
- [ ] Error handling unchanged

---

### 1.7 Delete _check_rate_limit_sync() entirely (30 minutes)
**Files:** `app/modules/ingest/gmail_client.py`

**Changes:**
- Delete lines 154-194 (`_check_rate_limit_sync` method)
- Verify no remaining calls to this method (grep codebase)
- Remove any imports only used by this method

**Acceptance Criteria:**
- [ ] Method deleted
- [ ] No callers remaining in codebase
- [ ] Grep for `_check_rate_limit_sync` returns 0 results

**Verification:**
```bash
grep -r "_check_rate_limit_sync" app/
# Should return: (empty)
```

---

### 1.8 Update get_labels() and create_label() to async (30 minutes)
**Files:** `app/modules/ingest/gmail_client.py`

**Changes:**
- Convert `get_labels()` to async
- Convert `create_label()` to async
- Add rate limiting

**Acceptance Criteria:**
- [ ] Both methods are async
- [ ] Rate limiting enforced
- [ ] Docstrings updated

---

### 1.9 Run type checking (30 minutes)
**Files:** All modified files

**Commands:**
```bash
mypy app/modules/ingest/gmail_client.py
```

**Changes:**
- Fix any type errors revealed by mypy
- Add type hints if missing
- Ensure async methods return `Coroutine` types

**Acceptance Criteria:**
- [ ] `mypy` returns 0 errors
- [ ] All async methods have proper type hints
- [ ] No `Any` types added (use specific types)

---

### 1.10 Update module docstring (15 minutes)
**Files:** `app/modules/ingest/gmail_client.py`

**Changes:**
- Update module-level docstring with async usage
- Add migration note for callers
- Update usage examples

**Acceptance Criteria:**
- [ ] Docstring shows async usage
- [ ] Breaking change documented
- [ ] Examples use `await`

**Example:**
```python
"""
Gmail API client for fetching and modifying emails.

IMPORTANT: All methods are async and must be awaited.

Usage:
    client = GmailClient(mailbox)
    messages = await client.list_messages(query='in:inbox')  # <-- NOTE: await

Breaking Change (2025-11-13):
    GmailClient methods are now fully async. All callers must use await.
    This ensures rate limiting is properly enforced in all contexts.
"""
```

---

## 2.0 Update calling code to use async (4 hours)

### 2.1 Update classify_email_task() to async (1.5 hours)
**Files:** `app/tasks/classify.py`

**Changes:**
- Change `@app.task` to `@app.task(bind=True)` (allow async)
- Change `def classify_email_task(...)` to `async def classify_email_task(...)`
- Add `await` to all `GmailClient` method calls
- Verify Celery supports async tasks (it does in modern versions)

**Acceptance Criteria:**
- [ ] Task is async
- [ ] All `GmailClient` calls use `await`
- [ ] Test locally with Celery worker
- [ ] Task completes successfully

**Test Command:**
```bash
# Start Celery worker
celery -A app.core.celery_app worker --loglevel=info

# In another terminal, trigger task
python -c "from app.tasks.classify import classify_email_task; classify_email_task.delay('mailbox-id', 'message-id')"
```

---

### 2.2 Update sample_and_classify webhook to async (1 hour)
**Files:** `app/api/webhooks.py` (or wherever sample-and-classify lives)

**Changes:**
- Ensure endpoint is async: `@router.post(...)` with `async def`
- Add `await` to any `GmailClient` calls
- Verify no synchronous `GmailClient` usage remains

**Acceptance Criteria:**
- [ ] Endpoint is async
- [ ] All Gmail calls use await
- [ ] Test with curl command:
  ```bash
  curl -X POST "https://inbox-janitor-production-03fc.up.railway.app/webhooks/sample-and-classify?batch_size=10"
  ```

---

### 2.3 Update ingest tasks to async (1 hour)
**Files:** `app/tasks/ingest.py` (if exists)

**Changes:**
- Update any polling tasks that use `GmailClient`
- Convert to async
- Add `await` to all Gmail calls

**Acceptance Criteria:**
- [ ] All tasks using GmailClient are async
- [ ] Test tasks complete successfully

---

### 2.4 Update gmail_watch.py if needed (30 minutes)
**Files:** `app/modules/ingest/gmail_watch.py`

**Changes:**
- Check if this file uses `GmailClient` directly
- If yes, ensure it's using async/await
- If no, mark task as N/A

**Acceptance Criteria:**
- [ ] All `GmailClient` usage is async
- [ ] OR: File doesn't use `GmailClient` (mark N/A)

---

## 3.0 Update tests to async (2 hours)

### 3.1 Update test_gmail_client.py to async (1 hour)
**Files:** `tests/ingest/test_gmail_client.py`

**Changes:**
- Add `@pytest.mark.asyncio` to all test functions
- Change `def test_...` to `async def test_...`
- Add `await` to all `GmailClient` method calls
- Update fixtures if needed

**Acceptance Criteria:**
- [ ] All tests are async
- [ ] All tests pass: `pytest tests/ingest/test_gmail_client.py -v`
- [ ] No skipped tests added

**Example:**
```python
@pytest.mark.asyncio
async def test_list_messages(mailbox):
    """Test listing messages from Gmail."""
    client = GmailClient(mailbox)

    # Mock Gmail API response
    with patch.object(client, '_get_service') as mock_service:
        mock_service.return_value.users().messages().list().execute.return_value = {
            "messages": [{"id": "msg1"}]
        }

        response = await client.list_messages(query="in:inbox")  # <-- await

        assert len(response["messages"]) == 1
```

---

### 3.2 Add rate limit bypass detection test (30 minutes)
**Files:** `tests/ingest/test_gmail_client.py`

**Changes:**
- Add new test: `test_rate_limit_enforced_in_all_contexts()`
- Verify rate limiter is called in async context
- Use mock to track rate limiter calls

**Acceptance Criteria:**
- [ ] Test verifies rate limiter called
- [ ] Test passes

**Test Code:**
```python
@pytest.mark.asyncio
async def test_rate_limit_enforced_in_all_contexts(mailbox, mocker):
    """Verify rate limiter is called in all contexts (no bypass)."""
    # Mock rate limiter
    mock_limiter = AsyncMock()
    mock_limiter.check_and_increment = AsyncMock()

    client = GmailClient(mailbox, rate_limiter=mock_limiter)

    # Mock Gmail API
    with patch.object(client, '_get_service'):
        await client.list_messages(query="in:inbox")

    # Verify rate limiter was called
    assert mock_limiter.check_and_increment.called
    assert mock_limiter.check_and_increment.call_count == 1
```

---

### 3.3 Add test for async enforcement (30 minutes)
**Files:** `tests/ingest/test_gmail_client.py`

**Changes:**
- Add test that verifies calling without `await` raises TypeError
- Ensures callers can't accidentally use sync

**Acceptance Criteria:**
- [ ] Test fails if method called without await
- [ ] Test passes

**Test Code:**
```python
def test_gmail_client_requires_await(mailbox):
    """GmailClient methods must be awaited (not called synchronously)."""
    client = GmailClient(mailbox)

    # Calling without await should fail
    with pytest.raises(TypeError, match="coroutine"):
        client.list_messages()  # Missing await - should raise TypeError
```

---

### 3.4 Update classify task tests (if exist) (30 minutes)
**Files:** `tests/tasks/test_classify.py`

**Changes:**
- Update to async if needed
- Ensure tests pass with async task

**Acceptance Criteria:**
- [ ] All tests pass
- [ ] Tests verify async behavior

---

## 4.0 Deploy and verify (4 hours)

### 4.1 Run full test suite locally (30 minutes)
**Files:** All tests

**Commands:**
```bash
pytest tests/ -v --tb=short
```

**Acceptance Criteria:**
- [ ] All tests pass
- [ ] No new skipped tests
- [ ] No test failures related to async changes

---

### 4.2 Test with local Celery worker (30 minutes)
**Files:** N/A (manual testing)

**Commands:**
```bash
# Terminal 1: Start Redis
redis-server

# Terminal 2: Start Celery worker
celery -A app.core.celery_app worker --loglevel=info

# Terminal 3: Start FastAPI
uvicorn app.main:app --reload

# Terminal 4: Trigger classification
curl -X POST "http://localhost:8000/webhooks/sample-and-classify?batch_size=10"
```

**Acceptance Criteria:**
- [ ] Celery worker processes tasks
- [ ] No rate limit bypass warnings in logs
- [ ] Tasks complete successfully
- [ ] Rate limit Redis keys created (check with `redis-cli keys rate_limit:*`)

---

### 4.3 Create pull request (30 minutes)
**Files:** All modified files

**Commands:**
```bash
git checkout -b fix/rate-limiting-architecture
git add .
git commit -m "$(cat <<'EOF'
Fix rate limiting bypass in async contexts

CRITICAL: Rate limiter was completely bypassed when GmailClient sync
methods were called from async contexts (e.g., Celery workers with
event loops). This allowed unlimited Gmail API calls.

Changes:
- Refactored GmailClient to fully async (all methods now async def)
- Removed _check_rate_limit_sync() wrapper that bypassed rate limiting
- Updated all calling code (tasks, webhooks) to use async/await
- Updated tests to async
- Added test to detect future rate limit bypasses

Impact:
- Rate limiting now enforced in ALL contexts (100% enforcement)
- No more "rate limit bypassed" warnings in logs
- Gmail API quota protected

Breaking Change:
- All GmailClient methods must now be awaited
- Calling code must be async

🤖 Generated with [Claude Code](https://claude.com/claude-code)

Co-Authored-By: Claude <noreply@anthropic.com>
EOF
)"

git push -u origin fix/rate-limiting-architecture

gh pr create --title "🚨 CRITICAL: Fix rate limiting bypass in async contexts" --body "$(cat <<'EOF'
## Summary

Fixed critical rate limiting bypass that allowed unlimited Gmail API calls.

## Problem

Rate limiter was completely bypassed when `GmailClient` sync methods were called from async contexts (Celery workers with event loops). The code logged a warning but allowed execution to continue without enforcing limits.

**Before:**
```python
try:
    loop = asyncio.get_running_loop()
    logger.warning("Rate limit bypassed...")
    return  # <-- NO RATE LIMITING
except RuntimeError:
    # Actually enforce rate limit
```

## Solution

Refactored `GmailClient` to fully async:
- All methods now `async def`
- Removed `_check_rate_limit_sync()` wrapper entirely
- Updated all calling code to use `async`/`await`
- Added test to prevent future bypasses

**After:**
```python
async def list_messages(...):
    await self._check_rate_limit_async(quota_units=5)  # Always enforced
    ...
```

## Testing

- ✅ All unit tests pass
- ✅ Rate limit enforcement test added
- ✅ Tested with local Celery worker
- ✅ Verified rate limit Redis keys created
- ✅ Zero "rate limit bypassed" warnings in logs

## Breaking Changes

⚠️ All `GmailClient` methods must now be awaited:

**Before:**
```python
client = GmailClient(mailbox)
messages = client.list_messages(query="in:inbox")  # Sync
```

**After:**
```python
client = GmailClient(mailbox)
messages = await client.list_messages(query="in:inbox")  # Async
```

## Deployment Plan

1. Merge PR (after CI passes)
2. Deploy to Railway
3. Monitor logs for 2 hours (zero bypass warnings expected)
4. Verify rate limiting working (check Redis keys)

## Success Criteria

- [ ] CI tests pass
- [ ] No rate limit bypass warnings in production logs
- [ ] Classification tasks complete successfully
- [ ] Rate limit Redis keys created for all users

🤖 Generated with [Claude Code](https://claude.com/claude-code)
EOF
)"
```

**Acceptance Criteria:**
- [ ] PR created
- [ ] PR title indicates critical fix
- [ ] PR body explains problem, solution, breaking changes
- [ ] PR linked to security audit document

---

### 4.4 Wait for CI checks (30 minutes)
**Files:** N/A (automated)

**Actions:**
- Monitor GitHub Actions workflow
- Fix any test failures
- Ensure all checks pass

**Acceptance Criteria:**
- [ ] All CI checks pass (green)
- [ ] No test failures
- [ ] No linting errors

---

### 4.5 Merge PR and deploy (30 minutes)
**Files:** N/A

**Commands:**
```bash
# After CI passes and user approves
gh pr merge --squash
```

**Acceptance Criteria:**
- [ ] PR merged to main
- [ ] Railway deployment triggered
- [ ] Deployment succeeds

---

### 4.6 Verify Railway deployment (1 hour)
**Files:** N/A (production monitoring)

**Actions:**
1. Check Railway deployment logs
2. Verify health endpoint:
   ```bash
   curl https://inbox-janitor-production-03fc.up.railway.app/health
   ```
3. Monitor logs for errors:
   - Look for "rate limit bypassed" warnings (should be 0)
   - Check for async-related errors
   - Verify classification tasks running

4. Check rate limit Redis keys:
   ```bash
   # Connect to Railway Redis
   redis-cli -h <railway-redis-host>
   keys rate_limit:*
   # Should see keys like: rate_limit:user-123:2025-11-13T14:30:00
   ```

5. Test classification endpoint:
   ```bash
   curl -X POST "https://inbox-janitor-production-03fc.up.railway.app/webhooks/sample-and-classify?batch_size=10"
   ```

**Acceptance Criteria:**
- [ ] Health endpoint returns 200 OK
- [ ] Zero "rate limit bypassed" warnings in logs (30 min sample)
- [ ] Classification tasks complete successfully
- [ ] Rate limit Redis keys created
- [ ] No async-related errors in Sentry

---

### 4.7 Monitor for 2 hours (2 hours)
**Files:** N/A (production monitoring)

**Actions:**
- Monitor Railway logs continuously
- Check Sentry for new errors
- Verify classification throughput normal
- Watch for user reports of issues

**Monitoring Commands:**
```bash
# Stream Railway logs
railway logs --follow

# Check Sentry dashboard
# (Open https://sentry.io/organizations/.../issues/)

# Monitor rate limit Redis usage
redis-cli keys rate_limit:* | wc -l
# Should increase as emails classified
```

**Acceptance Criteria:**
- [ ] No critical errors in logs (2 hour sample)
- [ ] No new Sentry errors related to async
- [ ] Zero "rate limit bypassed" warnings
- [ ] Classification throughput normal
- [ ] Rate limit working as expected

---

## Rollback Plan

If deployment causes issues:

1. **Immediate rollback:**
   ```bash
   # Revert the merge commit
   git revert HEAD
   git push origin main

   # Railway will auto-deploy previous version
   ```

2. **Investigate:**
   - Export Railway logs for analysis
   - Check Sentry for error patterns
   - Identify root cause

3. **Fix and retry:**
   - Create new branch with fix
   - Test locally
   - Create new PR
   - Follow deployment process again

---

## Definition of Done

- [ ] All tasks completed
- [ ] All tests passing
- [ ] PR merged
- [ ] Deployed to production
- [ ] Monitored for 2 hours
- [ ] Zero rate limit bypass warnings
- [ ] Rate limiting enforced 100%
- [ ] No regressions or new errors
- [ ] Documentation updated (CHANGELOG.md)

---

## Notes

**Why 16 hours?**
- Refactor: 6h (10 methods, type checking, docs)
- Update callers: 4h (tasks, webhooks, testing)
- Tests: 2h (async conversion, new tests)
- Deploy: 4h (PR, CI, deploy, monitor)

**Risk Mitigation:**
- Extensive local testing before deploy
- Gradual rollout with monitoring
- Rollback plan ready
- 2-hour monitoring period

**Success Metrics:**
- Rate limit bypass warnings: 0/day (was ~50/day)
- Rate limit enforcement: 100% (was 0% in async contexts)
- Classification throughput: Same or better
- Gmail API quota usage: Within expected limits
