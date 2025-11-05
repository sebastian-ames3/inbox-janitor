# E2E Testing with Playwright

This directory contains end-to-end (E2E) tests for Inbox Janitor using [Playwright](https://playwright.dev/).

## Architecture Overview

**Test Structure:**
```
tests/e2e/
├── auth.setup.js           # Creates authenticated session (runs first)
├── landing.spec.js         # Landing page tests (unauthenticated)
├── dashboard.spec.js       # Dashboard tests (authenticated)
├── account.spec.js         # Account page tests (authenticated)
├── audit.spec.js           # Audit log tests (authenticated)
├── accessibility.spec.js   # Accessibility tests (WCAG AA)
└── README.md              # This file
```

**Test Types:**
- **Unauthenticated tests:** Landing page, OAuth flow, public pages
- **Authenticated tests:** Dashboard, account, audit log (require login)
- **Accessibility tests:** WCAG AA compliance using axe-core
- **Multi-browser tests:** Chrome, Firefox, Safari (CI only)
- **Mobile tests:** iPhone/Android viewports

## Authentication System

### How It Works

E2E tests use Playwright's **setup project pattern** for authentication:

1. **Setup Project** (`auth.setup.js`) runs FIRST before all other tests:
   - Calls `/api/test/create-session` (test-only endpoint, blocked in production)
   - Creates session for test user (UUID: `00000000-0000-0000-0000-000000000001`)
   - Saves authenticated state to `playwright/.auth/user.json`

2. **Authenticated Tests** opt-in to use the saved session:
   - Add `test.use({ storageState: 'playwright/.auth/user.json' })` to test.describe blocks
   - Session is loaded automatically, tests run as logged-in user
   - No need to manually log in for each test

3. **Unauthenticated Tests** run without session (default):
   - No storageState configured
   - Tests run as anonymous users
   - Used for landing page, OAuth flow, etc.

### Authentication is Opt-In, Not Default

**IMPORTANT:** Tests do NOT automatically run with authentication. Each test.describe block must explicitly opt-in:

```javascript
test.describe('Dashboard Settings', () => {
  // REQUIRED: Opt-in to authentication
  test.use({ storageState: 'playwright/.auth/user.json' });

  test.beforeEach(async ({ page }) => {
    await page.goto('/dashboard');
  });

  test('should save settings', async ({ page }) => {
    // Test runs with authenticated session
  });
});
```

**Why opt-in?** Tests designed for unauthenticated users (landing page, OAuth flow) would break if they ran with authentication by default.

## Test User Details

**Email:** `test-user-e2e@inboxjanitor.com`
**User ID:** `00000000-0000-0000-0000-000000000001` (deterministic UUID)
**Mailbox:** One Gmail mailbox (mocked, no real OAuth tokens)
**Settings:** Default settings (sandbox mode, confidence thresholds 0.85/0.55)

**Database Setup:**
- Created via Alembic migration `004_create_test_user.py`
- Persists across test runs (not created/destroyed per test)
- Minimal data: no email actions, no sender stats (tests create their own)

## Running Tests

### Run All Tests (CI mode)
```bash
npm test
```

### Run with Browser Visible (debugging)
```bash
npm run test:headed
```

### Run Specific Test File
```bash
npx playwright test landing.spec.js
```

### Run in Debug Mode (step through tests)
```bash
npm run test:debug
```

### View HTML Report (after tests)
```bash
npm run test:report
```

### Run Single Test in UI Mode (interactive)
```bash
npx playwright test --ui
```

## Writing New Tests

### Unauthenticated Test Example

```javascript
const { test, expect } = require('@playwright/test');

test.describe('Landing Page', () => {
  // No authentication - runs as anonymous user

  test('should display hero section', async ({ page }) => {
    await page.goto('/');
    await expect(page.locator('h1')).toContainText('Inbox Janitor');
  });
});
```

### Authenticated Test Example

```javascript
const { test, expect } = require('@playwright/test');

test.describe('Dashboard Page', () => {
  // Opt-in to authentication
  test.use({ storageState: 'playwright/.auth/user.json' });

  test.beforeEach(async ({ page }) => {
    await page.goto('/dashboard');
  });

  test('should load settings', async ({ page }) => {
    await expect(page.locator('h1')).toContainText(/settings|dashboard/i);
  });
});
```

### Accessibility Test Example

```javascript
const { test, expect } = require('@playwright/test');
const AxeBuilder = require('@axe-core/playwright').default;

test('dashboard meets WCAG AA', async ({ page }) => {
  test.use({ storageState: 'playwright/.auth/user.json' });

  await page.goto('/dashboard');

  const accessibilityScanResults = await new AxeBuilder({ page }).analyze();

  expect(accessibilityScanResults.violations).toEqual([]);
});
```

## Troubleshooting

### Authentication Fails: "Session not found"

**Cause:** `playwright/.auth/user.json` doesn't exist or is invalid.

**Fix:**
```bash
# Regenerate authenticated session
npx playwright test auth.setup.js

# Verify file was created
ls -la playwright/.auth/user.json
```

### Test Fails: "401 Unauthorized" on Protected Page

**Cause:** Test is trying to access protected page without authentication.

**Fix:** Add authentication opt-in to test.describe block:
```javascript
test.use({ storageState: 'playwright/.auth/user.json' });
```

### Test Fails: "ERR_TOO_MANY_REDIRECTS"

**Cause:** Authenticated user redirected in a loop (e.g., homepage → dashboard → homepage).

**Fix:** Navigate directly to protected page, skip homepage:
```javascript
await page.goto('/dashboard'); // Good
await page.goto('/'); // Bad - may cause redirect loop
```

### Tests Pass Locally but Fail in CI

**Common causes:**
1. **Missing environment variables** - Check GitHub Actions secrets
2. **Database migration not applied** - Ensure test user exists in CI database
3. **Redis not running** - Session storage requires Redis
4. **Test endpoint blocked** - Verify `ENVIRONMENT=test` in CI (not `production`)

**Debug in CI:**
```bash
# View CI logs
gh run view --log-failed

# Check if test endpoint is accessible
curl https://your-ci-url.com/api/test/create-session
```

### Session Expires During Tests

**Cause:** Tests run longer than session max age (rare, sessions last 24 hours).

**Fix:** Sessions are created fresh before each test run via setup project. If tests run >24 hours (unlikely), re-run to regenerate session.

### Playwright Version Mismatch

**Cause:** `package.json` specifies different Playwright version than installed.

**Fix:**
```bash
# Reinstall Playwright
npm install
npx playwright install --with-deps
```

## CI/CD Integration

**GitHub Actions Workflow:**
- Setup project runs first (creates `playwright/.auth/user.json`)
- All test projects depend on setup completing
- Tests run in parallel (Chromium in CI, all browsers locally)
- Screenshots/videos captured on failure
- HTML report uploaded as artifact

**Configuration:** See `playwright.config.js` for full setup.

**CI Environment Variables Required:**
- `DATABASE_URL` - PostgreSQL connection (test user must exist)
- `REDIS_URL` - Session storage
- `SECRET_KEY` - JWT signing for sessions
- `ENVIRONMENT=test` - Enables test-only endpoints

## Security Notes

**Test Endpoint Protection:**
- `/api/test/create-session` is ONLY available when `ENVIRONMENT != "production"`
- Returns 403 Forbidden in production
- No authentication required (for testing only)
- Creates session with deterministic test user ID

**Test User Isolation:**
- Test user has no real OAuth tokens (dummy encrypted values)
- Cannot access real Gmail accounts
- Isolated from production users (deterministic UUID)
- No PII stored (email is test address)

**Session Storage:**
- `playwright/.auth/user.json` is gitignored (contains session cookies)
- Regenerated on each test run (not committed to repo)
- Only valid for test user (cannot access other accounts)

## Next Steps

**After Writing New Tests:**
1. Run tests locally: `npm test`
2. Verify accessibility: Check axe-core scans pass
3. Test on mobile: Use `playwright.config.js` mobile devices
4. Create PR: CI will run all tests automatically
5. Wait for CI to pass before merging

**Useful Resources:**
- [Playwright Docs](https://playwright.dev/)
- [Playwright Best Practices](https://playwright.dev/docs/best-practices)
- [Accessibility Testing](https://playwright.dev/docs/accessibility-testing)
- [Test Authentication](https://playwright.dev/docs/auth)
