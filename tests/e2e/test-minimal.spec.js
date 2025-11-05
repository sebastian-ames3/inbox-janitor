// @ts-check
const { test, expect } = require('@playwright/test');

/**
 * Minimal E2E test to verify Playwright setup works
 */

test('landing page loads', async ({ page }) => {
  await page.goto('/');

  // Just verify the page loads and has some content
  await expect(page).toHaveTitle(/Inbox Janitor/);
});
