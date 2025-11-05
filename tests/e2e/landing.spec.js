// @ts-check
const { test, expect } = require('@playwright/test');

/**
 * Landing Page Tests
 *
 * Verifies that the landing page loads correctly and has all expected elements.
 * This is a basic smoke test to verify Playwright setup.
 */

test.describe('Landing Page', () => {
  test('should load the landing page', async ({ page }) => {
    await page.goto('/');

    // Check page title
    await expect(page).toHaveTitle(/Inbox Janitor/);

    // Check main heading
    const heading = page.locator('h1').first();
    await expect(heading).toBeVisible();
    await expect(heading).toContainText('Keep Your Inbox Clean');

    // Check CTA button exists
    const ctaButton = page.locator('text=Connect Gmail').first();
    await expect(ctaButton).toBeVisible();
  });

  test('should have accessible navigation', async ({ page }) => {
    await page.goto('/');

    // Navigation should have proper ARIA label
    const nav = page.locator('nav[aria-label="Main navigation"]');
    await expect(nav).toBeVisible();

    // Logo should be clickable
    const logo = page.locator('a[aria-label*="home"]');
    await expect(logo).toBeVisible();
  });

  test('should be mobile responsive', async ({ page }) => {
    // Set viewport to mobile size (iPhone SE)
    await page.setViewportSize({ width: 375, height: 667 });
    await page.goto('/');

    // Hamburger menu should be visible on mobile
    const hamburger = page.locator('button[aria-label="Toggle menu"]');
    await expect(hamburger).toBeVisible();

    // Desktop navigation should be hidden
    const desktopNav = page.locator('.hidden.md\\:flex');
    await expect(desktopNav).not.toBeVisible();
  });

  test('should open and close mobile menu', async ({ page }) => {
    // Set viewport to mobile size
    await page.setViewportSize({ width: 375, height: 667 });
    await page.goto('/');

    // Mobile menu should be hidden initially
    const mobileMenu = page.locator('[role="menu"][aria-label="Mobile menu"]');
    await expect(mobileMenu).not.toBeVisible();

    // Click hamburger to open menu
    const hamburger = page.locator('button[aria-label="Toggle menu"]');
    await hamburger.click();

    // Mobile menu should now be visible
    await expect(mobileMenu).toBeVisible();

    // Click hamburger again to close
    await hamburger.click();

    // Mobile menu should be hidden again
    await expect(mobileMenu).not.toBeVisible();
  });

  test('should have keyboard accessible navigation', async ({ page }) => {
    await page.goto('/');

    // Focus on first interactive element (skip to main content link)
    await page.keyboard.press('Tab');

    // Verify focus is on skip link
    const skipLink = page.locator('a:has-text("Skip to main content")');
    await expect(skipLink).toBeFocused();

    // Tab to logo
    await page.keyboard.press('Tab');
    const logo = page.locator('a[aria-label*="home"]');
    await expect(logo).toBeFocused();
  });

  test('should have proper footer with links', async ({ page }) => {
    await page.goto('/');

    // Footer should exist
    const footer = page.locator('footer');
    await expect(footer).toBeVisible();

    // Check if footer has any content (not empty)
    const footerText = await footer.textContent();
    expect(footerText.length).toBeGreaterThan(0);
  });
});
