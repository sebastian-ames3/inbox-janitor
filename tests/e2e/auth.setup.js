/**
 * E2E Authentication Setup
 *
 * This setup project runs BEFORE all other E2E tests to create an authenticated
 * session and save it to playwright/.auth/user.json.
 *
 * All test projects depend on this setup and will reuse the authenticated state,
 * avoiding the need to authenticate in every test file.
 *
 * How it works:
 * 1. Makes POST request to /api/test/create-session (test-only endpoint)
 * 2. Endpoint creates session with test user ID
 * 3. Session cookie is automatically set by the endpoint
 * 4. We verify authentication by visiting /dashboard (protected page)
 * 5. Save the entire browser context (including cookies) to file
 * 6. All subsequent tests load this saved state
 *
 * Security:
 * - /api/test/create-session is ONLY available in development/test environments
 * - Returns 403 Forbidden in production
 * - Uses deterministic test user UUID: 00000000-0000-0000-0000-000000000001
 */

const { test, expect } = require('@playwright/test');

test('authenticate as test user', async ({ page }) => {
  console.log('Starting E2E authentication setup...');

  // Step 1: Create authenticated session via test endpoint
  console.log('Creating session via /api/test/create-session...');

  const response = await page.request.post('/api/test/create-session', {
    data: {
      user_id: '00000000-0000-0000-0000-000000000001' // Test user UUID
    }
  });

  // Verify endpoint succeeded
  expect(response.ok()).toBeTruthy();
  const data = await response.json();
  expect(data.success).toBe(true);
  expect(data.user_id).toBe('00000000-0000-0000-0000-000000000001');

  console.log('✓ Session created successfully');

  // Step 2: Verify authentication works by visiting protected page
  // We skip the homepage (/) and go directly to /dashboard to avoid
  // any redirect loops that might occur with authenticated users on landing page
  console.log('Verifying authentication by visiting /dashboard...');

  const dashboardResponse = await page.goto('/dashboard');

  // Should return 200 (not 401 or redirect to login)
  expect(dashboardResponse.status()).toBe(200);

  // Should see dashboard content (not login page)
  await expect(page.locator('h1')).toContainText(/dashboard|settings/i);

  console.log('✓ Authentication verified - /dashboard accessible');

  // Step 4: Save authenticated state to file
  // This includes cookies, localStorage, sessionStorage, etc.
  console.log('Saving authenticated state to playwright/.auth/user.json...');

  await page.context().storageState({ path: 'playwright/.auth/user.json' });

  console.log('✓ Authenticated state saved');
  console.log('✅ E2E authentication setup complete!\n');
});
