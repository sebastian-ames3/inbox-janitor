# PRD-0008: Test Coverage Recovery

**Status:** HIGH PRIORITY - FALSE CONFIDENCE IN CODE QUALITY
**Created:** 2025-11-13
**Priority:** P1 (Fix before 100+ users)
**Risk Level:** MEDIUM

---

## Problem Statement

**55 tests are skipped** in the test suite, creating false confidence in code quality:

**Breakdown:**
- **Security tests:** 14 skipped (CSRF, session, rate limiting, body storage)
- **Safety rail tests:** 5 skipped (exception keywords, short subject)
- **Classification tests:** 4 skipped (signal thresholds, accuracy)
- **Dashboard tests:** 17 skipped (authentication required)
- **Integration tests:** 15 skipped (timing-dependent, flaky)

**Impact:**
- Unknown security vulnerabilities
- False confidence in test coverage metrics
- Technical debt accumulating
- Production bugs not caught by CI/CD

**Root Cause:**
- Tests skipped to make CI green (not because features work)
- Comments say "TODO: Fix..." but no roadmap to fix
- Some tests legitimately broken (middleware issues)
- Some tests flaky (timing-dependent, environment-specific)

---

## Success Criteria

1. ✅ **Zero skipped security tests** - All security tests passing
2. ✅ **Zero skipped safety rail tests** - All classification safety tests passing
3. ✅ **<5 skipped integration tests** - Only acceptable skips (E2E coverage exists)
4. ✅ **Pre-commit hook blocks new skips** - No new skipped tests allowed
5. ✅ **Documentation** - Acceptable skips documented with justification

---

## Root Cause Analysis

### Why Are Tests Skipped?

**Category 1: Legitimately Broken (Need Fixing)** ⚠️
- `test_csrf.py`: CSRF middleware not working correctly (5 tests)
- `test_session.py`: Session middleware missing (2 tests)
- `test_rate_limiting.py`: Timing-dependent, fails in CI (7 tests)
- `test_safety_rails.py`: Exception keyword logic broken (5 tests)

**Category 2: Environment-Specific (Need Refactoring)** ⚠️
- `test_no_body_storage.py`: Pydantic v2 schema issues (2 tests)
- `test_signals.py`: Signal thresholds wrong (4 tests)
- `test_gmail_client.py`: Requires real Gmail API (3 tests)

**Category 3: Acceptable Skips (E2E Coverage Exists)** ✅
- `test_dashboard.py`: All 17 tests skipped with reason "Requires authentication setup"
- **Justification:** CHANGELOG shows Playwright E2E tests cover these scenarios
- **Action:** Document that Python unit tests can remain skipped if E2E coverage maintained

**Category 4: Flaky Tests (Need Stabilization)** ⚠️
- Integration tests that occasionally fail due to timing
- Database tests that fail if connection pool exhausted
- Redis tests that fail if connection reset

---

## Proposed Solution

### Phase 1: Triage (Week 1)

Create detailed inventory of all skipped tests:

```bash
# Find all skipped tests
pytest --collect-only -q | grep "SKIPPED"

# Generate report
pytest --collect-only -v | grep -A 5 "@pytest.mark.skip"

# Export to CSV for tracking
pytest --collect-only --co -v > /tmp/all_tests.txt
grep -A 3 "skip" /tmp/all_tests.txt > /tmp/skipped_tests.txt
```

**Deliverable:** Spreadsheet with columns:
- Test file
- Test name
- Skip reason
- Category (broken, flaky, acceptable)
- Priority (P0, P1, P2, P3)
- Estimated effort
- Owner
- Target fix date

---

### Phase 2: Fix Security Tests (Week 2) - CRITICAL

**Priority 1: CSRF Tests (5 tests)**

**Problem:** CSRF middleware not enforcing protection

**Files:**
- `tests/security/test_csrf.py` - 5 skipped tests
- `app/core/middleware.py` - CSRF middleware implementation

**Investigation:**
```python
# Why are these tests skipped?
@pytest.mark.skip(reason="CSRF middleware not working - investigate FastAPI integration")
def test_csrf_protection_on_forms():
    """Forms should require CSRF token."""
    pass
```

**Root Cause:** CSRF middleware may not be registered correctly or exempt URLs too broad

**Fix Plan:**
1. Review middleware registration in `app/main.py`
2. Test CSRF token generation and validation
3. Verify exempt URLs list is correct
4. Update tests to match actual implementation
5. Un-skip tests

**Estimated Effort:** 8 hours

---

**Priority 2: Session Tests (2 tests)**

**Problem:** Session middleware missing or not working

**Files:**
- `tests/security/test_session.py` - 2 skipped tests
- `app/core/middleware.py` - Session middleware implementation

**Investigation:**
```python
@pytest.mark.skip(reason="Session middleware not implemented yet")
def test_session_cookie_httponly():
    """Session cookies should be HttpOnly."""
    pass
```

**Root Cause:** Session middleware may not be needed (using JWT for auth instead)

**Fix Plan:**
1. Determine if session middleware actually needed
2. If not needed: Delete tests, document why in architecture
3. If needed: Implement session middleware, un-skip tests

**Estimated Effort:** 4 hours (if deleting), 12 hours (if implementing)

---

**Priority 3: Rate Limiting Tests (7 tests)**

**Problem:** Tests are timing-dependent and flaky

**Files:**
- `tests/security/test_rate_limiting.py` - 7 skipped tests

**Investigation:**
```python
@pytest.mark.skip(reason="Timing-dependent test - fails in CI")
async def test_rate_limit_sliding_window():
    """Rate limit should use sliding window algorithm."""
    # Test sleeps for exact durations, fails if CI slow
    pass
```

**Root Cause:** Tests rely on `time.sleep()` and real time passing

**Fix Plan:**
1. Use `freezegun` or `pytest-freezegun` to freeze time
2. Mock Redis rate limit counters instead of waiting
3. Test rate limit logic separately from timing
4. Use `@pytest.mark.slow` for real-time tests (run in separate job)

**Example Fix:**
```python
from freezegun import freeze_time

@freeze_time("2025-01-01 12:00:00")
async def test_rate_limit_sliding_window():
    """Rate limit should use sliding window algorithm."""
    limiter = RateLimiter()

    # First request at 12:00:00 - should succeed
    await limiter.check_and_increment(user_id, quota_units=5)

    # Advance time by 30 seconds
    with freeze_time("2025-01-01 12:00:30"):
        # Within same minute window - should count toward limit
        assert await limiter.check_rate_limit(user_id, quota_units=5) == True

    # Advance time by 31 seconds (total 61 seconds - new window)
    with freeze_time("2025-01-01 12:01:01"):
        # New window - limit reset
        assert await limiter.check_rate_limit(user_id, quota_units=50) == True
```

**Estimated Effort:** 6 hours

---

**Priority 4: Body Storage Tests (2 tests)**

**Problem:** Pydantic v2 schema validation issues

**Files:**
- `tests/security/test_no_body_storage.py` - 2 skipped tests

**Investigation:**
```python
@pytest.mark.skip(reason="Pydantic v2 schema validation - need to fix")
def test_no_body_in_database_schema():
    """Database schema should not allow body columns."""
    pass
```

**Root Cause:** Test relies on Pydantic v1 API, project upgraded to v2

**Fix Plan:**
1. Update tests to use Pydantic v2 API
2. Replace `__fields__` with `model_fields`
3. Update validators to use `field_validator`
4. Un-skip tests

**Estimated Effort:** 2 hours

---

### Phase 3: Fix Safety Rail Tests (Week 3)

**Priority 5: Exception Keyword Tests (5 tests)**

**Covered by PRD-0005: Safety Rails Restoration**

**Files:**
- `tests/classification/test_safety_rails.py` - 5 skipped tests
- `app/modules/classifier/safety_rails.py` - Exception keywords

**Tests:**
```python
@pytest.mark.skip(reason="TODO: Fix 'offer' false positive in exception keywords")
def test_promotional_offer_not_protected():
    """Marketing 'offers' should not trigger exception keywords."""
    pass

@pytest.mark.skip(reason="TODO: Re-enable check_short_subject")
def test_short_subject_detection():
    """Short subjects from contacts should be flagged."""
    pass
```

**Fix Plan:** Implement PRD-0005 (phrase-based exception keywords, smart short subject)

**Estimated Effort:** Covered by PRD-0005 (24 hours)

---

### Phase 4: Fix Classification Tests (Week 4)

**Priority 6: Signal Threshold Tests (4 tests)**

**Problem:** Signal weights don't match tests

**Files:**
- `tests/classification/test_signals.py` - 4 skipped tests
- `app/modules/classifier/signals.py` - Signal weights

**Investigation:**
```python
@pytest.mark.skip(reason="Signal thresholds changed - update test expectations")
def test_unsubscribe_header_signal_weight():
    """Unsubscribe header should add 0.40 to trash score."""
    assert get_signal_weight("unsubscribe_header") == 0.40  # Fails: actual is 0.55
```

**Root Cause:** Tests written with old signal weights, weights tuned but tests not updated

**Fix Plan:**
1. Update test expectations to match current signal weights
2. Add test data file with current weights (single source of truth)
3. Un-skip tests

**Estimated Effort:** 2 hours

---

### Phase 5: Refactor Flaky Tests (Week 5)

**Priority 7: Integration Tests (15 tests)**

**Problem:** Tests occasionally fail due to timing, connection issues, environment

**Fix Strategies:**

**Strategy 1: Use Fixtures for Cleanup**
```python
@pytest.fixture
async def cleanup_redis():
    """Clean up Redis keys after test."""
    yield
    # Cleanup
    redis = await get_redis()
    await redis.flushdb()
```

**Strategy 2: Add Retries for Network Calls**
```python
from pytest_retry import retry

@retry(times=3, delay=1)
@pytest.mark.integration
async def test_gmail_api_fetch():
    """Fetch emails from Gmail API."""
    # May fail due to network - retry up to 3 times
    pass
```

**Strategy 3: Mock External Dependencies**
```python
@pytest.mark.asyncio
async def test_classification_flow(mocker):
    """Test classification without real OpenAI call."""
    mock_openai = mocker.patch("openai.ChatCompletion.create")
    mock_openai.return_value = {"choices": [{"message": {"content": "TRASH"}}]}

    # Test classification logic without external API
    result = await classify_email(metadata)
    assert result["action"] == "TRASH"
```

**Estimated Effort:** 12 hours (1.5 days)

---

### Phase 6: Dashboard Tests (Week 6) - OPTIONAL

**Decision:** Keep skipped if E2E coverage exists

**Current State:**
- 17 Python unit tests skipped (authentication required)
- Playwright E2E tests cover same scenarios
- E2E tests more comprehensive (multi-browser, mobile, accessibility)

**Recommendation:**
1. **Keep Python tests skipped** - Duplication with E2E tests
2. **Document in test file** - Explain why skipped (covered by E2E)
3. **Verify E2E coverage** - Ensure every skipped test has E2E equivalent

**Documentation:**
```python
# tests/portal/test_dashboard.py
"""
Dashboard tests (Python unit tests).

NOTE: All 17 tests in this file are skipped because they are covered by
Playwright E2E tests in tests/e2e/dashboard/*.spec.js.

E2E tests provide better coverage:
- Multi-browser (Chrome, Firefox, Safari)
- Mobile responsiveness
- Accessibility (WCAG AA)
- Real user interactions (HTMX, Alpine.js)

If E2E tests are removed, these tests MUST be un-skipped and updated.
"""

@pytest.mark.skip(reason="Covered by E2E tests: tests/e2e/dashboard/settings.spec.js")
def test_settings_form_submit():
    """Test settings form submission."""
    pass
```

**Estimated Effort:** 2 hours (documentation only)

---

## Pre-Commit Hook: Block New Skips

Prevent new skipped tests from being added:

```bash
# .git/hooks/pre-commit
#!/bin/bash

# Check for new skipped tests
NEW_SKIPS=$(git diff --cached --name-only | grep "test_.*\.py$" | xargs grep -l "@pytest.mark.skip" || true)

if [ -n "$NEW_SKIPS" ]; then
    echo "❌ Error: New skipped tests detected:"
    echo "$NEW_SKIPS"
    echo ""
    echo "Skipped tests are not allowed. Please fix the test or discuss with team."
    echo "If this is a legitimate skip (e.g., covered by E2E), add to .skip-whitelist"
    exit 1
fi

# Check for pytest.skip() calls in code
NEW_SKIP_CALLS=$(git diff --cached --name-only | grep "test_.*\.py$" | xargs grep -l "pytest.skip" || true)

if [ -n "$NEW_SKIP_CALLS" ]; then
    echo "❌ Error: New pytest.skip() calls detected:"
    echo "$NEW_SKIP_CALLS"
    echo ""
    echo "Skipping tests at runtime is not allowed. Fix the test or use @pytest.mark.skip with justification."
    exit 1
fi

echo "✅ No new skipped tests detected"
exit 0
```

**Installation:**
```bash
cp .git/hooks/pre-commit.sample .git/hooks/pre-commit
chmod +x .git/hooks/pre-commit
```

**Whitelist for Acceptable Skips:**
```
# .skip-whitelist
tests/portal/test_dashboard.py  # Covered by E2E tests
tests/integration/test_e2e_flow.py  # Requires production environment
```

---

## Testing Strategy

### Test the Tests

**Meta-test: Verify fixed tests actually work**

```python
# Run previously skipped tests individually
pytest tests/security/test_csrf.py::test_csrf_protection_on_forms -v

# Run all security tests (should pass after fixes)
pytest tests/security/ -v

# Verify no skipped tests in critical areas
pytest tests/security/ tests/classification/ --tb=short | grep "SKIPPED"
# Should output: (empty)
```

### Coverage Metrics

**Before Fix:**
- Total tests: 200
- Passing: 145 (72.5%)
- Skipped: 55 (27.5%)
- Coverage: 85% (inflated due to skipped tests)

**After Fix:**
- Total tests: 200
- Passing: 195 (97.5%)
- Skipped: 5 (2.5% - dashboard tests covered by E2E)
- Coverage: 90%+ (real coverage)

---

## Rollout Plan

### Week 1: Triage & Planning
- Inventory all skipped tests
- Categorize by reason and priority
- Estimate effort for each
- Create task list

### Week 2: Fix Security Tests (CRITICAL)
- Fix CSRF tests (8h)
- Fix session tests or delete (4-12h)
- Fix rate limiting tests (6h)
- Fix body storage tests (2h)
- **Deliverable:** All security tests passing

### Week 3: Fix Safety Rail Tests
- Implement PRD-0005 (safety rails restoration)
- Un-skip exception keyword tests
- Un-skip short subject tests
- **Deliverable:** All safety rail tests passing

### Week 4: Fix Classification Tests
- Update signal threshold tests (2h)
- Verify accuracy tests (2h)
- **Deliverable:** All classification tests passing

### Week 5: Stabilize Flaky Tests
- Add fixtures for cleanup (4h)
- Add retries for network calls (4h)
- Mock external dependencies (4h)
- **Deliverable:** <1% flaky test rate

### Week 6: Documentation & Prevention
- Document acceptable skips (2h)
- Install pre-commit hook (1h)
- Update CI/CD to fail on new skips (1h)
- **Deliverable:** No new skips allowed

---

## Success Metrics

**Before Fix:**
- Skipped tests: 55 (27.5%)
- Security test coverage: 14 tests skipped (critical gaps)
- CI/CD confidence: LOW (false positives common)

**After Fix:**
- Skipped tests: <5 (2.5%) ✅
- Security test coverage: 100% (all passing) ✅
- CI/CD confidence: HIGH (catches real bugs) ✅
- Pre-commit blocks new skips ✅

---

## Files to Modify

**Security Tests:**
- `tests/security/test_csrf.py` - Un-skip 5 tests
- `tests/security/test_session.py` - Un-skip or delete 2 tests
- `tests/security/test_rate_limiting.py` - Un-skip 7 tests
- `tests/security/test_no_body_storage.py` - Un-skip 2 tests

**Classification Tests:**
- `tests/classification/test_safety_rails.py` - Un-skip 5 tests
- `tests/classification/test_signals.py` - Un-skip 4 tests

**Dashboard Tests:**
- `tests/portal/test_dashboard.py` - Document why skipped (E2E coverage)

**Infrastructure:**
- `.git/hooks/pre-commit` - Add skip detection
- `.skip-whitelist` - New file for acceptable skips
- `.github/workflows/ci.yml` - Add `--strict-markers` flag

**Dependencies:**
- Add `pytest-freezegun` to `requirements-dev.txt`
- Add `pytest-retry` to `requirements-dev.txt`

---

## Risks & Mitigations

| Risk | Impact | Mitigation |
|------|--------|-----------|
| Fixing tests reveals real bugs | HIGH - Production issues | Good! Fix bugs before users find them |
| Tests still flaky after fixes | MEDIUM - CI unreliable | Add retries, improve mocking, isolate tests |
| Effort underestimated | LOW - Takes longer | Prioritize security tests, defer others |
| Pre-commit hook blocks legitimate skips | LOW - Developer friction | Maintain whitelist, document exceptions |

---

## Dependencies

**Blocks:**
- Billing launch (can't charge users with unknown security gaps)
- Scaling to 100+ users (unknown bugs will scale)

**Blocked By:**
- PRD-0005 (Safety Rails Restoration) - Must be completed first

---

## Estimated Effort

- Triage: 4 hours
- Security tests: 22 hours (Week 2)
- Safety rail tests: 24 hours (Week 3, part of PRD-0005)
- Classification tests: 4 hours (Week 4)
- Flaky tests: 12 hours (Week 5)
- Documentation + prevention: 4 hours (Week 6)
- **Total: 70 hours (9 days)**

**Parallelization:**
- Security tests can be fixed independently
- Safety rail tests depend on PRD-0005
- Classification tests can be done in parallel with Week 5

**Realistic Timeline:** 4-5 weeks (20-25 hours/week)

---

## Accountability

**Why This Happened:**
- Tests skipped to make CI green ("ship first, fix later")
- No policy against skipping tests
- Technical debt accumulated over time
- False confidence in test coverage metrics

**Lessons Learned:**
1. Skipped tests are technical debt
2. Test coverage metrics lie when tests are skipped
3. CI/CD only valuable if tests actually run
4. "TODO: Fix..." without plan = never gets fixed

**Prevention:**
- Pre-commit hook blocks new skips
- Code review checklist: "Why is this test skipped?"
- Monthly: Review all skipped tests, plan to un-skip
- Quarterly: Pay down skipped test debt (1-2 per month)

---

**This PRD addresses the 55 skipped tests identified in the comprehensive security audit (2025-11-13).**
