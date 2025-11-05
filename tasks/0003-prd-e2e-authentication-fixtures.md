# PRD 0003: E2E Authentication Fixtures

**Status:** Draft
**Created:** 2025-11-05
**Author:** Claude (AI Assistant)

---

## 1. Introduction/Overview

Currently, 8 E2E tests are skipped because they require authentication to access protected pages (`/dashboard`, `/account`, `/audit`). These tests cannot run in CI without a valid user session. This creates blind spots in our test coverage for critical user-facing features.

This PRD defines the implementation of Playwright authentication fixtures that will enable E2E testing of protected pages by creating a test user and reusable authenticated session state.

**Problem:** Cannot E2E test protected pages without authentication, resulting in 8 skipped tests and reduced confidence in UI functionality.

**Goal:** Enable all E2E tests to run with proper authentication, following Playwright best practices for fixture-based authentication.

---

## 2. Goals

1. **Un-skip 8 authentication-dependent E2E tests** across dashboard and account pages
2. **Create reusable authentication fixtures** following Playwright 2025 best practices
3. **Maintain fast test execution** by authenticating once per worker, not per test
4. **Enable future authenticated E2E tests** with minimal setup required
5. **Document fixture usage** for other developers

---

## 3. User Stories

**As a developer:**
- I want to write E2E tests for protected pages without manually handling authentication
- I want tests to run quickly by reusing authenticated state
- I want clear documentation on how to use auth fixtures for new tests

**As a CI/CD pipeline:**
- I need all E2E tests to pass without manual intervention
- I need tests to run in parallel without authentication conflicts

**As a QA engineer:**
- I want confidence that protected pages render correctly
- I want to catch regressions in authenticated user experiences

---

## 4. Functional Requirements

### 4.1 Test User Setup

**FR-1:** Create a dedicated test user in the database with the following properties:
- Email: `test-user-e2e@inboxjanitor.com`
- User ID: Deterministic UUID (e.g., `00000000-0000-0000-0000-000000000001`)
- Created via Alembic migration or test seed script
- Persists across test runs (not created/destroyed per test)

**FR-2:** Test user must have minimal required data:
- One mailbox entry (mocked Gmail connection, no real OAuth tokens)
- Session stored in Redis (or mocked session middleware)
- No email actions or other test data (tests create their own)

### 4.2 Playwright Setup Project

**FR-3:** Create `tests/e2e/auth.setup.ts` (or `.js`) that:
- Programmatically creates a valid session for test user
- Saves session state to `playwright/.auth/user.json`
- Runs once before all other E2E tests

**FR-4:** Update `playwright.config.js` to:
- Define a `setup` project that runs `auth.setup.ts`
- Configure all E2E test projects to depend on `setup`
- Use `storageState: 'playwright/.auth/user.json'` for all tests

### 4.3 Reusable Authentication Fixtures

**FR-5:** Create custom Playwright fixture in `tests/e2e/fixtures/auth.js`:
- Export `authenticatedPage` fixture that provides a page with authenticated session
- Use worker-scoped fixture (`{ scope: 'worker' }`) to authenticate once per parallel worker
- Handle session expiration and re-authentication if needed

**FR-6:** Session generation must:
- Create valid session cookie matching FastAPI's session middleware format
- Store user_id in Redis with correct key format
- Set cookie with proper domain, path, httpOnly, secure flags

### 4.4 Un-skip Tests (Incremental Rollout)

**FR-7:** Un-skip tests in this order (one PR per file):
1. **Phase 1:** Dashboard tests (4 tests in `dashboard.spec.js`)
   - `should toggle between sandbox and action mode`
   - `should show different visual states for selected mode`
   - `should close tooltip on click away`
   - `should have close button in tooltip`
2. **Phase 2:** Account tests (4 tests in `account.spec.js`)
   - `should show loading state during export`
   - `should show success message after export`
   - `should show beta program notice`
   - `should have CSRF token for delete action`

**FR-8:** Each un-skipped test must:
- Import and use `authenticatedPage` fixture (or rely on global storageState)
- Pass in CI without manual intervention
- Verify page renders correctly with authentication

### 4.5 Documentation

**FR-9:** Create `tests/e2e/README.md` documenting:
- How authentication fixtures work
- How to use `authenticatedPage` in new tests
- How to run authenticated tests locally
- How test user is created and managed

**FR-10:** Update `CLAUDE.md` to reference auth fixtures when writing new E2E tests

---

## 5. Non-Goals (Out of Scope)

1. **OAuth mocking for real Google login flow** - Not needed for this phase; we're testing UI, not OAuth flow
2. **Multiple test users or roles** - Single test user is sufficient for current needs
3. **Testing with real OAuth tokens** - Test user uses mocked session, not real OAuth
4. **Performance testing of authenticated endpoints** - This is UI/UX testing only
5. **Testing logout flow in authenticated tests** - Logout already tested in `oauth.spec.js`

---

## 6. Design Considerations

### 6.1 Test User Creation

**Option A (Recommended):** Alembic migration creates test user
- Pros: Persistent, version-controlled, runs on all environments
- Cons: Test data in production database (mitigated by email suffix)

**Option B:** Python seed script run before tests
- Pros: Keeps test data separate from migrations
- Cons: Must be run manually/in CI setup

**Decision:** Use Alembic migration with `if not exists` check

### 6.2 Session Generation

**Approach:** Programmatically create session in `auth.setup.ts`:
```javascript
// Pseudo-code
const sessionId = 'test-session-uuid';
const userId = '00000000-0000-0000-0000-000000000001';

// Store in Redis (via API call or direct Redis connection)
await redis.set(`session:${sessionId}`, JSON.stringify({ user_id: userId }));

// Set cookie in Playwright
await context.addCookies([{
  name: 'session',
  value: sessionId,
  domain: 'localhost',
  path: '/',
  httpOnly: true,
  secure: false, // true in production
  sameSite: 'Lax'
}]);

// Save state
await context.storageState({ path: 'playwright/.auth/user.json' });
```

### 6.3 Playwright Config Structure

```javascript
// playwright.config.js
projects: [
  {
    name: 'setup',
    testMatch: /.*\.setup\.(ts|js)/,
  },
  {
    name: 'chromium',
    use: {
      ...devices['Desktop Chrome'],
      storageState: 'playwright/.auth/user.json', // Use authenticated state
    },
    dependencies: ['setup'], // Run setup first
  },
  // ... other projects
]
```

---

## 7. Technical Considerations

### 7.1 Session Middleware Compatibility

- Must match FastAPI's session middleware format exactly
- Verify session cookie name matches `app/core/security.py`
- Ensure Redis key format matches existing session storage

### 7.2 Redis Connection in Tests

**Option A:** Make API call to custom test endpoint that creates session
- Pros: Uses existing backend code, no direct Redis connection needed
- Cons: Requires new test-only endpoint

**Option B:** Direct Redis connection from Node.js
- Pros: No backend changes needed
- Cons: Requires `ioredis` npm package, duplicates session logic

**Decision:** Option A (custom endpoint) is cleaner and safer

### 7.3 CI Environment Variables

- `REDIS_URL` must be available in GitHub Actions
- Test user credentials should NOT be in environment (hardcoded test user is fine)

### 7.4 Parallel Test Execution

- Shared test user works because tests don't modify user state
- If future tests modify state, implement worker-scoped fixtures with multiple test users

---

## 8. Success Metrics

1. **All 8 skipped tests pass** in CI with authentication fixtures
2. **No performance regression** - Test suite should not be significantly slower
3. **Zero flaky tests** - Authentication must be reliable across runs
4. **Developer adoption** - New E2E tests for protected pages are written without issues

**Acceptance Criteria:**
- [ ] Test user created in database (migration applied)
- [ ] `auth.setup.ts` successfully creates authenticated session
- [ ] `playwright/.auth/user.json` contains valid session state
- [ ] All 4 dashboard tests pass when un-skipped
- [ ] All 4 account tests pass when un-skipped
- [ ] Documentation exists in `tests/e2e/README.md`
- [ ] CI pipeline passes with all authenticated tests

---

## 9. Open Questions

1. **Should test user have mailbox data?**
   - Proposed: Yes, one minimal mailbox entry to prevent 401s on mailbox-dependent pages

2. **How to handle session expiration in long test runs?**
   - Proposed: Set session max age to 24 hours, tests complete in <10 minutes

3. **Should we add a custom test endpoint for session creation?**
   - Proposed: Yes - `/api/test/create-session` (only enabled in test environment)

4. **How to clean up test user data between test runs?**
   - Proposed: Not needed - test user is persistent, tests create their own data in isolated state

---

## 10. Implementation Plan (High-Level)

### Phase 1: Foundation (PR #1)
- Create Alembic migration for test user
- Create `/api/test/create-session` endpoint (test env only)
- Create `auth.setup.ts` that generates authenticated session
- Update `playwright.config.js` with setup project
- Document in `tests/e2e/README.md`

### Phase 2: Un-skip Dashboard Tests (PR #2)
- Un-skip 4 dashboard tests
- Verify tests pass in CI
- Fix any issues with auth fixtures

### Phase 3: Un-skip Account Tests (PR #3)
- Un-skip 4 account tests
- Verify tests pass in CI
- Update CHANGELOG with completion

**Estimated Timeline:** 3 PRs over 2-3 days

---

**Next Steps:** Create task list from this PRD using `generate-tasks.md` skill
