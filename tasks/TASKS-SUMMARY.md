# Task Lists Summary - Safety Mechanism Restoration

**Generated:** 2025-11-13
**Status:** All task lists complete
**Total Effort:** 158 hours (~20 days)

---

## Overview

Following the comprehensive security audit (SECURITY-AUDIT-2025-11-13.md), I've created **5 detailed PRDs** and **5 complete task lists** to restore all safety mechanisms that were bypassed or disabled.

All documents are in `/tasks/` directory and ready for implementation.

---

## Task Lists Generated

### 1. TASKS-PRD-0004-rate-limiting-architecture-fix.md
**Priority:** P0 (CRITICAL - Block all other work)
**Effort:** 16 hours (2 days)
**Tasks:** 4 parent tasks, 28 subtasks

**Overview:**
- Refactor GmailClient to fully async (10 subtasks)
- Update all calling code to async (4 subtasks)
- Update tests to async (4 subtasks)
- Deploy and verify (7 subtasks)

**Key Deliverables:**
- Async GmailClient with rate limiting enforced 100%
- Zero "rate limit bypassed" warnings
- All tests passing
- 2-hour production monitoring

**Start With:** Task 1.1 (Convert list_messages() to async)

---

### 2. TASKS-PRD-0005-safety-rails-restoration.md
**Priority:** P0 (CRITICAL - Block billing launch)
**Effort:** 24 hours (3 days)
**Tasks:** 5 parent tasks, 20 subtasks

**Overview:**
- Collect baseline metrics (4 subtasks)
- Implement smart short subject detection (4 subtasks)
- Implement phrase-based exception keywords (4 subtasks)
- Test on production dataset (3 subtasks)
- Deploy and monitor (2 subtasks)

**Key Deliverables:**
- Smart short subject detection (<0.1% false positives)
- Phrase-based exception keywords (95%+ accuracy)
- Tested on 1000+ real emails
- Distribution improves (KEEP 15%, ARCHIVE 30%)

**Start With:** Task 1.1 (Run classifier on 1000 test emails)

---

### 3. TASKS-PRD-0006-security-monitoring-alerting.md
**Priority:** P0 (CRITICAL - Deploy before billing launch)
**Effort:** 24 hours (3 days)
**Tasks:** 6 parent tasks, 26 subtasks

**Overview:**
- Create alerting infrastructure (5 subtasks)
- Add monitoring to WORKER_PAUSED (3 subtasks)
- Add monitoring to Sentry body detection (3 subtasks)
- Add monitoring to Gmail watch failures (3 subtasks)
- Create dashboard health indicators (3 subtasks)
- Deploy and verify (3 subtasks)

**Key Deliverables:**
- Admin alerts within 60 seconds
- User notifications within 5 minutes
- Forensic logging for security violations
- Dashboard health indicators

**Start With:** Task 1.1 (Create core alerting module)

---

### 4. TASKS-PRD-0007-token-refresh-resilience.md
**Priority:** P1 (HIGH - Fix before 100+ users)
**Effort:** 24 hours (3 days)
**Tasks:** 6 parent tasks, 21 subtasks

**Overview:**
- Add database columns for tracking (2 subtasks)
- Implement retry logic with tenacity (5 subtasks)
- Create user notification emails (3 subtasks)
- Add dashboard indicators (2 subtasks)
- Write comprehensive tests (4 subtasks)
- Deploy and monitor (2 subtasks)

**Key Deliverables:**
- Retry 3x with exponential backoff (2s, 4s, 8s)
- Distinguish transient vs permanent failures
- User notifications at attempts 2 and 3
- 95% automatic recovery rate

**Start With:** Task 1.1 (Create migration for token refresh tracking)

---

### 5. TASKS-PRD-0008-test-coverage-recovery.md
**Priority:** P1 (HIGH - Fix before 100+ users)
**Effort:** 70 hours (9 days, over 4-5 weeks)
**Tasks:** 6 parent tasks, 43 subtasks

**Overview:**
- Week 1: Triage and inventory (2 subtasks)
- Week 2: Fix security tests (11 subtasks)
- Week 3: Fix safety rail tests (covered by PRD-0005)
- Week 4: Fix classification tests (2 subtasks)
- Week 5: Stabilize flaky tests (3 subtasks)
- Week 6: Add pre-commit hook (4 subtasks)

**Key Deliverables:**
- 55 skipped tests reduced to <5
- All security tests passing
- Pre-commit hook blocks new skips
- CI/CD enforces no skips

**Start With:** Task 1.1 (Generate skipped test inventory)

---

## Implementation Order (Recommended)

### Phase 1: Critical Safety (Weeks 1-2)
**Priority:** P0 - Block all other work

1. **PRD-0004: Rate Limiting** (Days 1-2)
   - File: `TASKS-PRD-0004-rate-limiting-architecture-fix.md`
   - Start: Task 1.1
   - Impact: Prevents unlimited Gmail API calls

2. **PRD-0005: Safety Rails** (Days 3-5)
   - File: `TASKS-PRD-0005-safety-rails-restoration.md`
   - Start: Task 1.1
   - Impact: Prevents false positives/negatives in classification

3. **PRD-0006: Security Monitoring** (Days 6-8)
   - File: `TASKS-PRD-0006-security-monitoring-alerting.md`
   - Start: Task 1.1
   - Impact: Immediate detection of security violations

**Phase 1 Total:** 8 days

---

### Phase 2: Resilience & Quality (Weeks 3-5)
**Priority:** P1 - Before billing launch

4. **PRD-0007: Token Refresh** (Days 9-11, Week 3)
   - File: `TASKS-PRD-0007-token-refresh-resilience.md`
   - Start: Task 1.1
   - Impact: Reduces user churn from transient failures

5. **PRD-0008: Test Coverage** (Weeks 2-6, parallel work)
   - File: `TASKS-PRD-0008-test-coverage-recovery.md`
   - Start: Task 1.1 (Week 1)
   - Impact: Real test coverage, CI/CD confidence

**Phase 2 Total:** 3 weeks (overlapping with Phase 1)

---

## Task Structure

Each task list follows this format:

```
# Task List: PRD-XXXX

## Parent Task (X hours)
Estimated time for entire parent task

### Subtask X.X (Y minutes/hours)
**Files:** Files to modify

**Changes:**
- Specific change 1
- Specific change 2

**Code Example:**
```code
Example implementation
```

**Acceptance Criteria:**
- [ ] Criterion 1
- [ ] Criterion 2

**Commands/Tests:**
```bash
# Commands to run
```
```

---

## How to Use These Task Lists

### For PRD-0004 (Rate Limiting) - MOST CRITICAL

1. **Read the PRD first:**
   ```bash
   cat tasks/PRD-0004-rate-limiting-architecture-fix.md
   ```

2. **Open the task list:**
   ```bash
   cat tasks/TASKS-PRD-0004-rate-limiting-architecture-fix.md
   ```

3. **Start with Task 1.1:**
   - Read task description
   - Review code examples
   - Make the changes
   - Run acceptance tests
   - Check off task
   - Move to Task 1.2

4. **After each parent task (1.0, 2.0, etc):**
   - Run full test suite
   - Commit changes
   - Review before continuing

5. **When all tasks complete:**
   - Create PR (commands in Task 4.3)
   - Wait for CI
   - Deploy
   - Monitor (Task 4.6-4.7)

---

## Execution Guidelines

### Step-by-Step Execution
Each subtask is designed to be:
- **Atomic:** Can be completed independently
- **Testable:** Has clear acceptance criteria
- **Reviewable:** Small enough to review easily

**Workflow:**
1. Read subtask description
2. Review code examples
3. Make changes
4. Run tests (commands provided)
5. Verify acceptance criteria
6. Check off subtask
7. Move to next

### Review Checkpoints
**After each parent task:**
- [ ] Run full test suite
- [ ] Review code changes
- [ ] Verify acceptance criteria met
- [ ] Commit with descriptive message
- [ ] Take a break (avoid rushing)

**After each PRD:**
- [ ] Create pull request
- [ ] Wait for CI checks
- [ ] Review PR description
- [ ] Merge after approval
- [ ] Monitor production

---

## Key Metrics: Before vs After

| Metric | Before | After | Improvement |
|--------|--------|-------|-------------|
| **Rate Limiting** |
| Bypass warnings | ~50/day | 0/day | ✅ 100% |
| Enforcement rate | 0% (async contexts) | 100% | ✅ 100% |
| **Safety Rails** |
| Short subject enabled | No | Yes (<0.1% FP) | ✅ Fixed |
| Exception keyword accuracy | ~85% | 98%+ | ✅ +13% |
| **Monitoring** |
| Worker pause detection | Silent | Alert in 5 min | ✅ Fixed |
| Body content detection | Dropped | Alert in 60s | ✅ Fixed |
| **Token Refresh** |
| Immediate disable rate | 100% | 5% | ✅ 95% recovery |
| User notification delay | 7 days | 5 minutes | ✅ 2000x faster |
| **Test Coverage** |
| Skipped tests | 55 (27.5%) | <5 (2.5%) | ✅ 91% reduction |
| Security tests | 14 skipped | 0 skipped | ✅ 100% |

---

## Dependencies Between PRDs

**PRD-0004 (Rate Limiting):**
- ❌ No dependencies - can start immediately
- 🚫 Blocks: All other work (P0 critical)

**PRD-0005 (Safety Rails):**
- ✅ Should start after PRD-0004 (but not blocking)
- ↔️ Overlaps with PRD-0008 Week 3

**PRD-0006 (Security Monitoring):**
- ❌ No dependencies - can parallel with PRD-0005
- ✅ Uses alerting for PRD-0007

**PRD-0007 (Token Refresh):**
- ✅ Uses alerting from PRD-0006 (can parallel)

**PRD-0008 (Test Coverage):**
- ✅ Week 2 can parallel with PRD-0004
- ↔️ Week 3 covered by PRD-0005
- ✅ Weeks 4-6 independent

**Parallelization Possible:**
- PRD-0004 + PRD-0008 Week 2 (different areas)
- PRD-0005 + PRD-0006 (different areas)
- PRD-0007 + PRD-0008 Week 4-5 (different areas)

---

## Risk Management

### High-Risk Changes
**PRD-0004 (Rate Limiting):**
- Breaking change (all callers must use async)
- Mitigation: Extensive testing, staged rollout
- Rollback: Revert PR, deploy previous version

**PRD-0005 (Safety Rails):**
- False positives could trash important emails
- Mitigation: Test on 1000+ emails, manual review
- Rollback: Re-disable safety rails, investigate

### Lower-Risk Changes
**PRD-0006 (Monitoring):**
- Additive only (no behavior changes)
- Mitigation: Test alerts don't spam

**PRD-0007 (Token Refresh):**
- Improves existing behavior
- Mitigation: Monitor for unexpected disables

**PRD-0008 (Test Coverage):**
- No production code changes (tests only)
- Mitigation: Fix tests correctly, don't just skip

---

## Estimated Completion Timeline

### Aggressive Timeline (Single Developer, Full-Time)
- **Phase 1 (P0):** 8 days (Weeks 1-2)
- **Phase 2 (P1):** 12 days (Weeks 3-5)
- **Total:** 20 days (~4 weeks)

### Realistic Timeline (Part-Time, 4h/day)
- **Phase 1 (P0):** 16 days (Weeks 1-4)
- **Phase 2 (P1):** 24 days (Weeks 5-10)
- **Total:** 40 days (~8-10 weeks)

### Conservative Timeline (20h/week, careful review)
- **Phase 1 (P0):** 4 weeks
- **Phase 2 (P1):** 6 weeks
- **Total:** 10 weeks (~2.5 months)

---

## Next Steps

1. **Review all PRDs** - Understand the "why" before starting
2. **Start with PRD-0004** - Most critical, shortest timeline
3. **Execute Task 1.1** - First subtask in TASKS-PRD-0004
4. **Get user approval after each parent task** - Review progress
5. **Monitor metrics** - Verify improvements in production

---

## Files Generated

All files in `/tasks/` directory:

**PRDs (Planning Documents):**
- `PRD-0004-rate-limiting-architecture-fix.md`
- `PRD-0005-safety-rails-restoration.md`
- `PRD-0006-security-monitoring-alerting.md`
- `PRD-0007-token-refresh-resilience.md`
- `PRD-0008-test-coverage-recovery.md`

**Task Lists (Implementation Guides):**
- `TASKS-PRD-0004-rate-limiting-architecture-fix.md`
- `TASKS-PRD-0005-safety-rails-restoration.md`
- `TASKS-PRD-0006-security-monitoring-alerting.md`
- `TASKS-PRD-0007-token-refresh-resilience.md`
- `TASKS-PRD-0008-test-coverage-recovery.md`

**Summary Documents:**
- `SECURITY-AUDIT-2025-11-13.md` (Audit findings)
- `TASKS-SUMMARY.md` (This file)

**Total:** 11 documents, ~50,000 words, 158 hours of work planned

---

## Ready to Start

Everything is documented and ready for implementation. Each task has:
- ✅ Clear description
- ✅ Code examples
- ✅ Acceptance criteria
- ✅ Test commands
- ✅ Estimated time

**Recommendation:** Start with PRD-0004 Task 1.1 tomorrow morning.

**Question:** Would you like me to start implementing PRD-0004 now, or do you want to review the task lists first?
