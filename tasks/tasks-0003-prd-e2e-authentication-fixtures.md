# Task List: PRD 0003 - E2E Authentication Fixtures

**PRD Reference:** `0003-prd-e2e-authentication-fixtures.md`
**Created:** 2025-11-05

---

## Relevant Files

### New Files to Create
- `alembic/versions/004_create_test_user.py` - Alembic migration to create test user and mailbox
- `app/api/test_routes.py` - Test-only API endpoint for session creation (enabled in test env only)
- `tests/e2e/auth.setup.js` - Playwright setup script that generates authenticated session
- `tests/e2e/fixtures/auth.js` - Custom authentication fixtures for Playwright (if needed)
- `tests/e2e/README.md` - Documentation for E2E authentication fixtures
- `playwright/.auth/user.json` - Saved authentication state (gitignored)

### Files to Modify
- `playwright.config.js` - Add setup project and storageState configuration
- `app/main.py` - Register test routes (conditionally, test env only)
- `tests/e2e/dashboard.spec.js` - Un-skip 4 tests
- `tests/e2e/account.spec.js` - Un-skip 4 tests
- `CLAUDE.md` - Add guidance for writing authenticated E2E tests
- `CHANGELOG.md` - Document completion of authentication fixtures
- `.gitignore` - Ensure `playwright/.auth/` is ignored

### Existing Files Referenced
- `app/core/session.py` - Session utilities (user_id, created_at format)
- `app/core/config.py` - Settings (SESSION_SECRET_KEY, environment detection)
- `app/models/user.py` - User model (for test user creation)
- `app/models/mailbox.py` - Mailbox model (for test mailbox creation)

### Notes
- Test user email: `test-user-e2e@inboxjanitor.com`
- Test user ID: `00000000-0000-0000-0000-000000000001` (deterministic UUID)
- Session format: `{"user_id": "...", "created_at": "2025-11-05T..."}`
- Auth state stored in `playwright/.auth/user.json`

---

## Tasks

- [ ] **1.0 Create Test User Infrastructure**
  - [ ] 1.1 Create Alembic migration `004_create_test_user.py` that:
    - Creates test user with email `test-user-e2e@inboxjanitor.com`
    - Uses deterministic UUID `00000000-0000-0000-0000-000000000001`
    - Creates one minimal mailbox entry (provider='gmail', is_active=false)
    - Uses `if not exists` check to avoid duplicates
    - Sets encrypted tokens to dummy values (not real OAuth)
  - [ ] 1.2 Run migration locally to verify test user is created: `alembic upgrade head`
  - [ ] 1.3 Create `app/api/test_routes.py` with `/api/test/create-session` endpoint that:
    - Only enabled when `ENVIRONMENT != "production"`
    - Accepts POST request with optional `user_id` parameter (defaults to test user ID)
    - Creates session in request.session with `user_id` and `created_at`
    - Returns session cookie in response
    - Returns 403 error if called in production environment
  - [ ] 1.4 Register test routes in `app/main.py`:
    - Import test_routes conditionally based on environment
    - Include router only if `settings.ENVIRONMENT in ["development", "test"]`
    - Add comment explaining test-only routes
  - [ ] 1.5 Test the endpoint manually:
    - Run app locally: `uvicorn app.main:app --reload`
    - Call `/api/test/create-session` and verify session cookie is set
    - Verify `/dashboard` returns 200 with session cookie

- [ ] **2.0 Implement Playwright Authentication Setup**
  - [ ] 2.1 Create `tests/e2e/auth.setup.js`:
    - Import `test` and `expect` from `@playwright/test`
    - Define setup test that navigates to `/api/test/create-session`
    - Wait for session cookie to be set
    - Verify session by navigating to `/dashboard` and checking for 200 status
    - Save authenticated state: `await page.context().storageState({ path: 'playwright/.auth/user.json' })`
    - Add error handling for production environment (should fail gracefully)
  - [ ] 2.2 Update `playwright.config.js`:
    - Add `setup` project at top of projects array with `testMatch: /.*\.setup\.js/`
    - Add `storageState: 'playwright/.auth/user.json'` to all test projects
    - Add `dependencies: ['setup']` to all test projects (except setup itself)
    - Verify setup project runs first in CI
  - [ ] 2.3 Update `.gitignore` to exclude `playwright/.auth/`:
    - Add `playwright/.auth/` to gitignore
    - Add comment explaining this stores test authentication state
  - [ ] 2.4 Test authentication setup locally:
    - Run `npm test` and verify setup project creates `playwright/.auth/user.json`
    - Verify file contains valid session cookie
    - Verify subsequent tests can access protected pages

- [ ] **3.0 Un-skip Dashboard Tests (Phase 1)**
  - [ ] 3.1 Create feature branch: `git checkout -b feature/unskip-dashboard-auth-tests`
  - [ ] 3.2 Un-skip tests in `tests/e2e/dashboard.spec.js`:
    - Change `test.skip` to `test` for "should toggle between sandbox and action mode"
    - Change `test.skip` to `test` for "should show different visual states for selected mode"
    - Change `test.skip` to `test` for "should close tooltip on click away"
    - Change `test.skip` to `test` for "should have close button in tooltip"
    - Remove `// SKIPPED: Requires authentication` comments
  - [ ] 3.3 Run dashboard tests locally to verify they pass: `npx playwright test dashboard.spec.js`
  - [ ] 3.4 Fix any failures:
    - If tests fail due to missing UI elements, update selectors
    - If tests timeout, increase timeout or investigate page load issues
    - Document any issues discovered
  - [ ] 3.5 Commit changes: `git add . && git commit -m "Un-skip dashboard authentication tests"`
  - [ ] 3.6 Push and create PR: `gh pr create --title "Un-skip dashboard E2E tests with authentication"`
  - [ ] 3.7 Wait for CI to pass (all 4 dashboard tests should pass)
  - [ ] 3.8 Merge PR after CI passes

- [ ] **4.0 Un-skip Account Tests (Phase 2)**
  - [ ] 4.1 Create feature branch: `git checkout -b feature/unskip-account-auth-tests`
  - [ ] 4.2 Un-skip tests in `tests/e2e/account.spec.js`:
    - Change `test.skip` to `test` for "should show loading state during export"
    - Change `test.skip` to `test` for "should show success message after export"
    - Change `test.skip` to `test` for "should show beta program notice"
    - Change `test.skip` to `test` for "should have CSRF token for delete action"
    - Remove `// SKIPPED: Requires authentication` comments
  - [ ] 4.3 Run account tests locally to verify they pass: `npx playwright test account.spec.js`
  - [ ] 4.4 Fix any failures:
    - If tests fail due to missing UI elements, update selectors
    - If tests fail due to missing data, create minimal test data in test
    - Document any issues discovered
  - [ ] 4.5 Commit changes: `git add . && git commit -m "Un-skip account authentication tests"`
  - [ ] 4.6 Push and create PR: `gh pr create --title "Un-skip account E2E tests with authentication"`
  - [ ] 4.7 Wait for CI to pass (all 4 account tests should pass)
  - [ ] 4.8 Merge PR after CI passes

- [ ] **5.0 Documentation and Cleanup**
  - [ ] 5.1 Create `tests/e2e/README.md` documenting:
    - Overview of E2E test architecture
    - How authentication works (setup project → storageState → all tests authenticated)
    - How to write new authenticated E2E tests (just use authenticated page fixture)
    - How to run tests locally
    - Test user details (email, ID, credentials)
    - Troubleshooting guide (common issues, how to regenerate auth state)
  - [ ] 5.2 Update `CLAUDE.md` section on E2E tests:
    - Add note that all E2E tests run with authentication by default
    - Reference `tests/e2e/README.md` for details
    - Add example of writing authenticated E2E test
  - [ ] 5.3 Update `CHANGELOG.md`:
    - Add new section for authentication fixtures completion
    - Document all 3 PRs (infrastructure, dashboard, account)
    - Note that all 8 skipped tests are now running
    - Include success metrics (0 flaky tests, no performance regression)
  - [ ] 5.4 Create final PR for documentation: `gh pr create --title "Document E2E authentication fixtures"`
  - [ ] 5.5 Verify all changes are merged and deployed to production

---

## Implementation Order

**Phase 1: Foundation (Tasks 1.0, 2.0)**
- Estimated time: 2-3 hours
- Creates infrastructure for authentication
- No tests un-skipped yet (validation PR)

**Phase 2: Dashboard Tests (Task 3.0)**
- Estimated time: 1-2 hours
- Un-skips 4 dashboard tests
- Validates authentication fixtures work in CI

**Phase 3: Account Tests (Task 4.0)**
- Estimated time: 1-2 hours
- Un-skips 4 account tests
- Completes E2E authentication coverage

**Phase 4: Documentation (Task 5.0)**
- Estimated time: 1 hour
- Documents solution for future developers
- Updates CHANGELOG

**Total Estimated Time:** 5-8 hours over 2-3 days (accounting for CI wait times)

---

## Success Criteria

- [ ] Test user exists in database (migration applied)
- [ ] `/api/test/create-session` endpoint works in test environment
- [ ] `auth.setup.js` successfully creates `playwright/.auth/user.json`
- [ ] All 4 dashboard tests pass when un-skipped
- [ ] All 4 account tests pass when un-skipped
- [ ] Documentation exists in `tests/e2e/README.md`
- [ ] CI pipeline passes with all authenticated tests
- [ ] No flaky tests introduced
- [ ] No performance regression in test suite

---

## Notes

- Follow PR workflow: feature branch → commit → push → create PR → wait for CI → merge
- Test locally before creating PR to catch issues early
- If tests fail in CI, investigate logs and fix before merging
- Keep PRs small and focused (one phase per PR)
- Use incremental rollout strategy proven successful in PRs #39-43
