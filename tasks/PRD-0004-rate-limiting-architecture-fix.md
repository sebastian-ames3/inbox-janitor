# PRD-0004: Rate Limiting Architecture Fix

**Status:** CRITICAL - PRODUCTION SAFETY BYPASS
**Created:** 2025-11-13
**Priority:** P0 (Block all other work)
**Risk Level:** CATASTROPHIC

---

## Problem Statement

The rate limiter is **completely bypassed** when `GmailClient` sync methods are called from async contexts (e.g., Celery workers with event loops). This violates the core promise of "10 emails/minute per user" and risks:

1. **Gmail API quota exhaustion** - Unlimited API calls allowed
2. **Service degradation** - One user's runaway loop impacts all users
3. **Account suspension** - Google may throttle/suspend our OAuth app
4. **Cost explosion** - AI classification costs spike if rate limiting fails

**Current Code (gmail_client.py:170-178):**
```python
try:
    loop = asyncio.get_running_loop()
    logger.warning("Rate limit bypassed...")
    return  # <-- BYPASSES ALL RATE LIMITING
except RuntimeError:
    # Actually enforce rate limits here
```

**Evidence:**
- Found in production on `fix/critical-async-errors` branch
- CHANGELOG.md PR #84 attempted fix but only improved detection, not prevention
- Codex review identified this as "Major Issue"

---

## Success Criteria

1. ✅ **Zero rate limit bypasses** - All code paths enforce rate limiting
2. ✅ **No sync wrappers** - GmailClient is fully async
3. ✅ **All tests pass** - No regressions in classification pipeline
4. ✅ **Production verification** - Monitor rate limit enforcement for 48h
5. ✅ **Documentation** - All calling code updated with async patterns

---

## Proposed Solution

### Architecture Change: Make GmailClient Fully Async

**Current (Broken):**
```
Celery Task (async context)
  → GmailClient.list_messages() [SYNC]
    → _check_rate_limit_sync() [SYNC WRAPPER]
      → Detects event loop, BYPASSES rate limit ❌
```

**Fixed (Enforced):**
```
Celery Task (async context)
  → await GmailClient.list_messages() [ASYNC]
    → await _check_rate_limit() [ASYNC]
      → Enforces rate limit ✅
```

### Implementation Steps

1. **Refactor GmailClient to async** (gmail_client.py)
   - Convert all methods to `async def`
   - Remove `_check_rate_limit_sync()` entirely
   - Use `await` for all rate limiter calls
   - Keep `_rate_limit()` for basic request spacing

2. **Update all calling code to async** (Celery tasks, webhooks)
   - `app/tasks/classify.py` - make `classify_email_task()` async
   - `app/tasks/ingest.py` - make polling tasks async
   - `app/modules/ingest/gmail_watch.py` - already async, update calls

3. **Update Celery configuration**
   - Ensure Celery can run async tasks
   - Test with concurrent workers

4. **Add fail-fast validation**
   - Raise exception if rate limiter bypassed
   - Remove "log and continue" pattern

---

## Technical Details

### Files to Modify

**Core Changes:**
- `app/modules/ingest/gmail_client.py` - Make all methods async
- `app/tasks/classify.py` - Convert to async task
- `app/tasks/ingest.py` - Convert polling to async

**Testing:**
- `tests/ingest/test_gmail_client.py` - Update to async tests
- `tests/security/test_rate_limiting.py` - Add bypass detection test

**Documentation:**
- `skills/fastapi-module-builder.md` - Update Gmail client usage patterns
- `CHANGELOG.md` - Document breaking change

### Breaking Changes

**Before:**
```python
# Sync usage (broken rate limiting)
client = GmailClient(mailbox)
messages = client.list_messages(query="in:inbox")
```

**After:**
```python
# Async usage (enforced rate limiting)
client = GmailClient(mailbox)
messages = await client.list_messages(query="in:inbox")
```

**Migration Path:**
- All code using GmailClient must add `await`
- Celery tasks must be decorated with `@app.task(bind=True)` and be async
- No sync fallback - fail-fast if called incorrectly

---

## Testing Strategy

### Unit Tests
```python
# New test: Detect rate limit bypass attempts
@pytest.mark.asyncio
async def test_rate_limit_cannot_be_bypassed():
    """Verify rate limiter is called in all contexts."""
    limiter = Mock()
    client = GmailClient(mailbox, rate_limiter=limiter)

    await client.list_messages(query="in:inbox")

    # Verify rate limiter was called
    assert limiter.check_and_increment.called

# Test: Async context enforcement
@pytest.mark.asyncio
async def test_gmail_client_requires_async_context():
    """GmailClient methods must be awaited."""
    client = GmailClient(mailbox)

    # This should be async, not sync
    with pytest.raises(TypeError, match="object is not callable"):
        client.list_messages()  # Missing await
```

### Integration Tests
- Run classification on 100 emails with rate limiting enabled
- Verify rate limiter Redis keys created
- Check logs for zero "rate limit bypassed" warnings

### Production Verification
- Deploy to Railway
- Monitor logs for "rate limit bypassed" warnings (should be 0)
- Check Sentry for new async-related errors
- Verify classification tasks complete successfully
- Monitor rate limit Redis keys in Railway dashboard

---

## Rollout Plan

### Phase 1: Development (Day 1)
- Create feature branch: `fix/rate-limiting-architecture`
- Refactor GmailClient to async
- Update calling code (tasks, webhooks)
- Run full test suite locally

### Phase 2: Testing (Day 2)
- Push branch, create PR
- Wait for CI tests to pass
- Test on Railway preview environment
- Process 100 test emails
- Verify zero rate limit bypass warnings

### Phase 3: Production (Day 3)
- Merge PR to main
- Monitor Railway deployment
- Watch logs for 2 hours (no bypass warnings)
- Process real emails
- Check rate limit Redis keys

### Phase 4: Validation (Day 4-5)
- Monitor for 48 hours
- Verify rate limiting working correctly
- Check for any classification delays
- Measure API quota usage (should match expected)

### Rollback Plan
If async refactor causes issues:
1. Revert PR
2. Deploy previous version
3. Investigate errors in Sentry
4. Fix issues and re-attempt

---

## Risks & Mitigations

| Risk | Impact | Mitigation |
|------|--------|-----------|
| Async breaks Celery tasks | HIGH - Classification stops | Test with Celery locally before deployment |
| Event loop conflicts | HIGH - Worker crashes | Use Celery's built-in async support |
| Performance degradation | MEDIUM - Slower processing | Benchmark before/after with 100 emails |
| Missed async/await calls | HIGH - Tasks fail | Add type hints, use mypy for validation |

---

## Success Metrics

**Before Fix:**
- Rate limit bypass warnings: ~50/day (estimated)
- Rate limit enforcement: 0% (bypassed in async contexts)
- Gmail API quota usage: Uncontrolled

**After Fix:**
- Rate limit bypass warnings: 0/day ✅
- Rate limit enforcement: 100% ✅
- Gmail API quota usage: 10 emails/min/user (as designed) ✅

---

## Follow-up Work

After this fix is deployed:
1. Add monitoring dashboard for rate limit metrics
2. Create alert: "Rate limit bypass detected" → SMS to admin
3. Document async patterns in `skills/gmail-client-usage.md`
4. Add pre-commit hook: Detect sync calls to async-only methods

---

## Dependencies

**Blocks:**
- All other feature work (this is P0)
- Billing integration (can't launch with safety bypass)
- Scaling to 100+ users (rate limiting required)

**Blocked By:**
- None (can start immediately)

---

## Estimated Effort

- Development: 6 hours
- Testing: 4 hours
- Code review: 2 hours
- Deployment + monitoring: 4 hours
- **Total: 16 hours (2 days)**

---

## Accountability

**Why This Happened:**
- Async/await refactor (PR #84) fixed initialization bugs but didn't address architectural issue
- "Log and continue" pattern used instead of "fail-fast"
- Quick fix prioritized over correct fix
- Safety mechanism disabled to avoid blocking event loop

**Lessons Learned:**
1. Never bypass safety mechanisms - fail-fast instead
2. Log warnings are not an acceptable substitute for enforcement
3. Async refactors require updating entire call chain
4. Test that safety mechanisms are actually enforced, not just called

**Prevention:**
- Add test: "Rate limiter cannot be bypassed"
- Add pre-commit hook: Detect `return` in safety checks
- Code review checklist: "Does this disable any safety mechanism?"
- Document: "When to fail-fast vs when to log and continue"

---

**This PRD addresses the most critical safety bypass identified in the comprehensive security audit (2025-11-13).**
