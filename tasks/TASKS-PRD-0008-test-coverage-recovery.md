# Task List: PRD-0008 Test Coverage Recovery

**PRD:** [PRD-0008: Test Coverage Recovery](./PRD-0008-test-coverage-recovery.md)
**Total Estimated Time:** 70 hours (9 days, spread over 4-5 weeks)
**Priority:** P1 (HIGH - Fix before 100+ users)

---

## Task Overview

- [ ] **1.0 Triage and inventory all skipped tests** (4 hours) - Week 1
- [ ] **2.0 Fix security tests (CRITICAL)** (22 hours) - Week 2
- [ ] **3.0 Fix safety rail tests** (24 hours) - Week 3 (part of PRD-0005)
- [ ] **4.0 Fix classification tests** (4 hours) - Week 4
- [ ] **5.0 Stabilize flaky tests** (12 hours) - Week 5
- [ ] **6.0 Add pre-commit hook and documentation** (4 hours) - Week 6

---

## 1.0 Triage and inventory all skipped tests (4 hours) - Week 1

### 1.1 Generate skipped test inventory
**Commands:**
```bash
# Find all skipped tests
pytest --collect-only -q | grep "SKIPPED" > /tmp/skipped_tests.txt

# Get detailed skip reasons
pytest --collect-only -v | grep -A 3 "@pytest.mark.skip" > /tmp/skip_reasons.txt

# Count by directory
grep -r "@pytest.mark.skip" tests/ | cut -d':' -f1 | sort | uniq -c
```

**Deliverable:** Create `/tmp/skipped_tests_inventory.csv`:
```csv
File,Test Name,Skip Reason,Category,Priority,Estimated Effort
tests/security/test_csrf.py,test_csrf_protection_on_forms,CSRF middleware broken,Security,P0,2h
...
```

**Acceptance Criteria:**
- [ ] All 55 skipped tests cataloged
- [ ] Categorized by reason
- [ ] Priority assigned (P0-P3)
- [ ] Effort estimated

---

### 1.2 Create fix roadmap
**Deliverable:** `/tmp/test_fix_roadmap.md`

```markdown
# Test Fix Roadmap

## Week 2: Security Tests (P0)
- CSRF tests (5 tests, 8h)
- Session tests (2 tests, 4-12h)
- Rate limiting tests (7 tests, 6h)
- Body storage tests (2 tests, 2h)

## Week 3: Safety Rails (P0)
- Part of PRD-0005 implementation
- Exception keywords (5 tests)

## Week 4: Classification Tests (P1)
- Signal thresholds (4 tests, 2h)

## Week 5: Flaky Tests (P1)
- Integration tests (15 tests, 12h)

## Week 6: Prevention
- Pre-commit hook (2h)
- Documentation (2h)

## Deferred: Dashboard Tests
- Keep skipped (covered by E2E tests)
- Document reasoning
```

**Acceptance Criteria:**
- [ ] Roadmap created
- [ ] Weekly plan outlined
- [ ] Dependencies identified

---

## 2.0 Fix security tests (CRITICAL) - Week 2 (22 hours)

### 2.1 Fix CSRF tests (8 hours)

#### 2.1.1 Investigate CSRF middleware
**Files:** `app/core/middleware.py`, `tests/security/test_csrf.py`

**Actions:**
1. Review CSRF middleware registration in `app/main.py`
2. Test CSRF token generation
3. Test CSRF token validation
4. Verify exempt URLs correct

**Acceptance Criteria:**
- [ ] Understand why tests failing
- [ ] Root cause documented

---

#### 2.1.2 Fix middleware or tests
**Based on findings:**

**Option A:** Middleware broken
- Fix middleware registration
- Fix token generation/validation
- Update tests to match

**Option B:** Tests wrong
- Update test expectations
- Fix test setup/teardown

**Acceptance Criteria:**
- [ ] All 5 CSRF tests passing
- [ ] `pytest tests/security/test_csrf.py -v` green

---

### 2.2 Fix session tests (4-12 hours)

#### 2.2.1 Determine if session middleware needed
**Decision Point:**

**If NOT needed** (using JWT instead):
- Delete `tests/security/test_session.py`
- Document in architecture why no session middleware
- Update CLAUDE.md
- **Effort: 4 hours**

**If needed:**
- Implement session middleware
- Configure Redis session store
- Un-skip tests
- **Effort: 12 hours**

**Acceptance Criteria:**
- [ ] Decision documented
- [ ] Tests passing or deleted

---

### 2.3 Fix rate limiting tests (6 hours)

#### 2.3.1 Use freezegun for time-based tests
**Files:** `tests/security/test_rate_limiting.py`

**Changes:**
```python
from freezegun import freeze_time

@freeze_time("2025-01-01 12:00:00")
async def test_rate_limit_sliding_window():
    """Rate limit uses sliding window algorithm."""
    limiter = RateLimiter()

    await limiter.check_and_increment(user_id, quota_units=5)

    with freeze_time("2025-01-01 12:00:30"):
        assert await limiter.check_rate_limit(user_id, 5) is True

    with freeze_time("2025-01-01 12:01:01"):
        assert await limiter.check_rate_limit(user_id, 50) is True
```

**Acceptance Criteria:**
- [ ] Add `pytest-freezegun` to requirements-dev.txt
- [ ] All 7 tests updated
- [ ] All tests pass
- [ ] No timing dependencies

---

### 2.4 Fix body storage tests (2 hours)

#### 2.4.1 Update to Pydantic v2 API
**Files:** `tests/security/test_no_body_storage.py`

**Changes:**
```python
# Old (Pydantic v1)
model.__fields__

# New (Pydantic v2)
model.model_fields
```

**Acceptance Criteria:**
- [ ] Tests updated to Pydantic v2
- [ ] Both tests passing
- [ ] No deprecation warnings

---

## 3.0 Fix safety rail tests - Week 3 (24 hours)

**Note:** This is covered by PRD-0005 (Safety Rails Restoration)

Tasks:
- [ ] Un-skip exception keyword tests (covered in PRD-0005, Task 3.2)
- [ ] Un-skip short subject tests (covered in PRD-0005, Task 2.3)

**See: TASKS-PRD-0005-safety-rails-restoration.md**

---

## 4.0 Fix classification tests - Week 4 (4 hours)

### 4.1 Update signal threshold tests (2 hours)
**Files:** `tests/classification/test_signals.py`

**Problem:** Signal weights changed but tests not updated

**Actions:**
1. Review current signal weights in `app/modules/classifier/signals.py`
2. Update test expectations to match
3. Create `tests/fixtures/signal_weights.json` (single source of truth)

**Example:**
```python
# Load expected weights from fixture
with open("tests/fixtures/signal_weights.json") as f:
    EXPECTED_WEIGHTS = json.load(f)

def test_unsubscribe_header_signal_weight():
    """Unsubscribe header has correct weight."""
    weight = get_signal_weight("unsubscribe_header")
    assert weight == EXPECTED_WEIGHTS["unsubscribe_header"]  # 0.55
```

**Acceptance Criteria:**
- [ ] All 4 tests updated
- [ ] Tests pass
- [ ] Fixture file created

---

### 4.2 Verify accuracy tests (2 hours)
**Files:** `tests/classification/test_accuracy.py`

**Actions:**
1. Run accuracy tests
2. If failing, update expectations based on recent tuning
3. Document expected accuracy thresholds

**Acceptance Criteria:**
- [ ] Accuracy tests pass
- [ ] Thresholds documented

---

## 5.0 Stabilize flaky tests - Week 5 (12 hours)

### 5.1 Add fixtures for cleanup (4 hours)
**Files:** `tests/conftest.py`, various test files

**Problem:** Tests leave state behind causing flakiness

**Solution:**
```python
@pytest.fixture
async def cleanup_redis():
    """Clean up Redis after test."""
    yield
    redis = await get_redis()
    await redis.flushdb()


@pytest.fixture
async def cleanup_database(session):
    """Rollback database after test."""
    yield
    await session.rollback()
```

**Acceptance Criteria:**
- [ ] Cleanup fixtures added
- [ ] Applied to flaky tests
- [ ] Tests now stable (run 10x, 0 failures)

---

### 5.2 Add retries for network calls (4 hours)
**Files:** Integration test files

**Solution:**
```python
from pytest_retry import retry

@retry(times=3, delay=1)
@pytest.mark.integration
async def test_gmail_api_fetch():
    """Fetch emails from Gmail API (with retry)."""
    # May fail due to network - retry up to 3 times
    pass
```

**Acceptance Criteria:**
- [ ] Add `pytest-retry` to requirements-dev.txt
- [ ] Applied to network-dependent tests
- [ ] Flakiness reduced

---

### 5.3 Mock external dependencies (4 hours)
**Files:** Various integration tests

**Problem:** Tests call real APIs (slow, flaky)

**Solution:**
```python
@pytest.mark.asyncio
async def test_classification_flow(mocker):
    """Test classification without real OpenAI call."""
    mock_openai = mocker.patch("openai.ChatCompletion.create")
    mock_openai.return_value = {
        "choices": [{"message": {"content": "TRASH"}}]
    }

    result = await classify_email(metadata)
    assert result["action"] == "TRASH"
```

**Acceptance Criteria:**
- [ ] External API calls mocked
- [ ] Tests faster (<1s per test)
- [ ] Tests reliable (100% pass rate)

---

## 6.0 Add pre-commit hook and documentation - Week 6 (4 hours)

### 6.1 Create pre-commit hook (2 hours)
**Files:** `.git/hooks/pre-commit`

**Hook:**
```bash
#!/bin/bash
# Block new skipped tests

NEW_SKIPS=$(git diff --cached --name-only | grep "test_.*\.py$" | xargs grep -l "@pytest.mark.skip" 2>/dev/null || true)

if [ -n "$NEW_SKIPS" ]; then
    # Check whitelist
    while IFS= read -r file; do
        if ! grep -q "$file" .skip-whitelist 2>/dev/null; then
            echo "❌ Error: New skipped test in $file"
            echo "Skipped tests not allowed. Fix the test or add to .skip-whitelist with justification."
            exit 1
        fi
    done <<< "$NEW_SKIPS"
fi

echo "✅ No new skipped tests"
exit 0
```

**Acceptance Criteria:**
- [ ] Hook created
- [ ] Made executable (`chmod +x`)
- [ ] Test by adding skip decorator (should fail)
- [ ] Document in README.md

---

### 6.2 Create skip whitelist (1 hour)
**Files:** `.skip-whitelist`

**Content:**
```
# Acceptable skipped tests (with justification)

tests/portal/test_dashboard.py
# Reason: All 17 tests covered by Playwright E2E tests
# Coverage: tests/e2e/dashboard/*.spec.js
# Review date: 2025-11-13
# Owner: Sebastian

tests/integration/test_e2e_flow.py
# Reason: Requires production environment
# Review date: 2025-11-13
```

**Acceptance Criteria:**
- [ ] Whitelist created
- [ ] Documented with justifications
- [ ] Reviewed by team

---

### 6.3 Update CI/CD to fail on skips (30 minutes)
**Files:** `.github/workflows/ci.yml`

**Changes:**
```yaml
- name: Run tests
  run: |
    pytest --strict-markers --maxfail=1 -v
    # Strict markers fails on unexpected skips
```

**Acceptance Criteria:**
- [ ] CI updated
- [ ] Test by adding skip (CI should fail)
- [ ] Whitelist mechanism works

---

### 6.4 Document skip policy (30 minutes)
**Files:** `tests/README.md`

**Content:**
```markdown
# Testing Policy

## Skipped Tests

**Policy:** Skipped tests are NOT allowed except for documented reasons.

**Acceptable reasons:**
1. Test covered by E2E tests (Playwright)
2. Test requires production environment
3. Test requires external service (document workaround plan)

**Process:**
1. Try to fix the test first
2. If skip necessary, add to `.skip-whitelist` with justification
3. Add review date (re-evaluate quarterly)
4. Pre-commit hook enforces policy

**Current skipped tests:** See `.skip-whitelist`
```

**Acceptance Criteria:**
- [ ] Policy documented
- [ ] Examples provided
- [ ] Linked from main README.md

---

## Weekly Progress Tracking

### Week 1: Triage
- [ ] Inventory complete
- [ ] Roadmap created
- [ ] Priorities assigned

### Week 2: Security Tests (22h)
- [ ] CSRF tests fixed (5 tests)
- [ ] Session tests fixed or deleted (2 tests)
- [ ] Rate limiting tests fixed (7 tests)
- [ ] Body storage tests fixed (2 tests)
- [ ] **Total: 16 tests un-skipped**

### Week 3: Safety Rails (24h)
- [ ] Covered by PRD-0005
- [ ] Exception keyword tests fixed (5 tests)
- [ ] **Total: 5 tests un-skipped**

### Week 4: Classification (4h)
- [ ] Signal threshold tests fixed (4 tests)
- [ ] **Total: 4 tests un-skipped**

### Week 5: Flaky Tests (12h)
- [ ] Cleanup fixtures added
- [ ] Retries added for network calls
- [ ] External dependencies mocked
- [ ] **Total: 15 tests stabilized**

### Week 6: Prevention (4h)
- [ ] Pre-commit hook installed
- [ ] Skip whitelist created
- [ ] CI/CD updated
- [ ] Documentation complete

---

## Definition of Done

- [ ] All tasks completed over 6 weeks
- [ ] Skipped tests reduced from 55 to <5
- [ ] All security tests passing (16 tests)
- [ ] All safety rail tests passing (5 tests)
- [ ] All classification tests passing (4 tests)
- [ ] Flaky tests stabilized (15 tests)
- [ ] Pre-commit hook blocking new skips
- [ ] CI/CD enforcing no skips
- [ ] Documentation updated
- [ ] Test coverage >90% (real, not inflated)

---

## Success Metrics

**Before Fix:**
- Skipped tests: 55 (27.5%)
- Security test coverage: 14 tests skipped
- CI/CD confidence: LOW
- False positives: Common

**After Fix:**
- Skipped tests: <5 (2.5%) ✅
- Security test coverage: 100% ✅
- CI/CD confidence: HIGH ✅
- False positives: Rare ✅

---

**Time: 70 hours (9 days, over 4-5 weeks)**

**Note:** This work overlaps with other PRDs:
- Week 3 overlaps with PRD-0005 (Safety Rails)
- Can parallelize some work (security tests independent)
