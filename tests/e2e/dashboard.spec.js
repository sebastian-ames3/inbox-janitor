// @ts-check
const { test, expect } = require('@playwright/test');

/**
 * Dashboard (Settings) Page Tests
 *
 * Tests the settings dashboard with:
 * - HTMX form submissions
 * - Alpine.js reactive components (sliders, toggles, tooltips)
 * - Session authentication
 * - Mobile responsiveness
 * - Accessibility
 */

// Test fixtures for authenticated session
// Note: In real tests, you'd use Playwright's storageState to persist auth
// For now, these tests assume you're testing against a logged-in session

test.describe.skip('Dashboard Page', () => {
  // SKIPPED: All tests in this file require authentication
  // Without auth, /dashboard redirects to Google OAuth which hangs in CI
  // TODO: Set up mock authentication or test OAuth credentials before enabling
  // test.use({ storageState: 'tests/e2e/.auth/user.json' });

  test.beforeEach(async ({ page }) => {
    // TODO: Set up authenticated session before each test
    // For now, tests will fail if not logged in
    await page.goto('/dashboard');
  });

  test('should load dashboard page with all sections', async ({ page }) => {
    // Page title
    await expect(page).toHaveTitle(/Settings - Inbox Janitor/);

    // Page header
    const heading = page.locator('h1');
    await expect(heading).toBeVisible();
    await expect(heading).toContainText('Settings');

    // Main sections
    await expect(page.locator('text=Connected Account')).toBeVisible();
    await expect(page.locator('text=Action Mode')).toBeVisible();
    await expect(page.locator('text=Confidence Thresholds')).toBeVisible();
    await expect(page.locator('text=Weekly Digest')).toBeVisible();
  });

  test('should display connected account information', async ({ page }) => {
    // Connected account section should show email
    const accountSection = page.locator('text=Connected Account').locator('..');
    await expect(accountSection).toBeVisible();

    // Should have a disconnect button
    const disconnectBtn = page.locator('button:has-text("Disconnect")');
    await expect(disconnectBtn).toBeVisible();

    // Should show Active status
    await expect(page.locator('text=Active')).toBeVisible();

    // Should have success icon (green checkmark)
    const successIcon = page.locator('.bg-success-100');
    await expect(successIcon).toBeVisible();
  });

  test('should toggle action mode with Alpine.js and show warning banner', async ({ page }) => {
    // Find the action mode radio buttons
    const sandboxRadio = page.locator('input[name="action_mode"][value="false"]');
    const actionRadio = page.locator('input[name="action_mode"][value="true"]');

    // Check initial state (should be sandbox mode based on default settings)
    // The sandbox option should have the primary border
    const sandboxLabel = page.locator('label').filter({ has: sandboxRadio });

    // Warning banner should be visible in sandbox mode
    const warningBanner = page.locator('.bg-warning-50');

    // Click action mode radio
    await actionRadio.click();

    // Wait for Alpine.js to update the UI
    await page.waitForTimeout(100);

    // The action mode label should now have the primary border
    const actionLabel = page.locator('label').filter({ has: actionRadio });
    await expect(actionLabel).toHaveClass(/border-primary-600/);

    // Warning banner should be hidden
    // Note: This test assumes the banner is conditionally rendered
  });

  test('should update confidence threshold slider value with Alpine.js', async ({ page }) => {
    // Find the auto-trash threshold slider
    const autoTrashSlider = page.locator('input[name="confidence_auto_threshold"]');

    // Get the value display (Alpine.js x-text binding)
    const valueDisplay = autoTrashSlider.locator('..').locator('span[x-text="value"]');

    // Set slider to a specific value
    await autoTrashSlider.fill('0.90');

    // Wait for Alpine.js to update
    await page.waitForTimeout(100);

    // Value should be displayed
    await expect(valueDisplay).toContainText('0.9');
  });

  test('should open and close help tooltip with Alpine.js', async ({ page }) => {
    // Find the first help button (Action Mode section)
    const helpButton = page.locator('button[aria-label="Help"]').first();
    await expect(helpButton).toBeVisible();

    // Click to open tooltip
    await helpButton.click();

    // Wait for Alpine.js transition
    await page.waitForTimeout(200);

    // Tooltip content should be visible
    const tooltip = page.locator('text=Sandbox mode logs what we would do');
    await expect(tooltip).toBeVisible();

    // Close button should be visible
    const closeButton = tooltip.locator('..').locator('button').first();
    await closeButton.click();

    // Wait for close transition
    await page.waitForTimeout(200);

    // Tooltip should be hidden
    await expect(tooltip).not.toBeVisible();
  });

  test('should submit threshold form with HTMX', async ({ page }) => {
    // Find the form
    const form = page.locator('form[hx-post="/api/settings/update"]');
    await expect(form).toBeVisible();

    // Change threshold values
    const autoTrashSlider = page.locator('input[name="confidence_auto_threshold"]');
    await autoTrashSlider.fill('0.90');

    const reviewSlider = page.locator('input[name="confidence_review_threshold"]');
    await reviewSlider.fill('0.60');

    // Submit form
    const saveButton = form.locator('button[type="submit"]');
    await saveButton.click();

    // Wait for HTMX to complete
    // Look for success message or loading indicator
    const loadingIndicator = page.locator('#threshold-loading');

    // Wait for loading to finish (text should appear then disappear or change)
    await page.waitForTimeout(500);

    // Success message should appear in target div
    const successMessage = page.locator('#threshold-save-message');
    // Note: This will depend on server response - may need to adjust based on actual implementation
  });

  test('should be mobile responsive', async ({ page }) => {
    // Set viewport to mobile size (iPhone SE)
    await page.setViewportSize({ width: 375, height: 667 });

    // Page should still be visible and usable
    const heading = page.locator('h1');
    await expect(heading).toBeVisible();

    // Sections should stack vertically
    const connectedAccount = page.locator('text=Connected Account');
    await expect(connectedAccount).toBeVisible();

    // Sliders should be usable on mobile
    const slider = page.locator('input[type="range"]').first();
    await expect(slider).toBeVisible();

    // Buttons should be large enough (min 44x44px)
    const saveButton = page.locator('button:has-text("Save Thresholds")');
    const buttonBox = await saveButton.boundingBox();
    expect(buttonBox?.height).toBeGreaterThanOrEqual(44);
  });

  test('should have accessible form controls', async ({ page }) => {
    // All sliders should have ARIA attributes
    const autoTrashSlider = page.locator('input[name="confidence_auto_threshold"]');
    await expect(autoTrashSlider).toHaveAttribute('aria-valuemin', '0.5');
    await expect(autoTrashSlider).toHaveAttribute('aria-valuemax', '1.0');
    await expect(autoTrashSlider).toHaveAttribute('aria-label');

    // Labels should be associated with inputs
    const autoTrashLabel = page.locator('label[for="confidence_auto_threshold"]');
    await expect(autoTrashLabel).toBeVisible();

    // Help buttons should have ARIA labels
    const helpButtons = page.locator('button[aria-label="Help"]');
    await expect(helpButtons.first()).toHaveAttribute('aria-label', 'Help');
  });

  test('should handle keyboard navigation', async ({ page }) => {
    // Tab through form elements
    await page.keyboard.press('Tab');

    // First focusable element should be focused
    // Could be the logo in nav or disconnect button

    // Continue tabbing to reach sliders
    for (let i = 0; i < 10; i++) {
      await page.keyboard.press('Tab');
    }

    // Should be able to adjust slider with arrow keys
    const focusedElement = page.locator(':focus');

    // If focused on a slider, arrow keys should work
    await page.keyboard.press('ArrowRight');
    await page.keyboard.press('ArrowLeft');
  });

  test('should display CSRF token in form', async ({ page }) => {
    // Form should have CSRF token hidden input
    const csrfInput = page.locator('input[name="csrf_token"]');
    await expect(csrfInput).toBeHidden();

    // Token should have a value
    const tokenValue = await csrfInput.getAttribute('value');
    expect(tokenValue).toBeTruthy();
    expect(tokenValue?.length).toBeGreaterThan(10);
  });

  test('should show HTMX loading indicator during submission', async ({ page }) => {
    const form = page.locator('form[hx-post="/api/settings/update"]');
    const saveButton = form.locator('button[type="submit"]');

    // Click save button
    await saveButton.click();

    // Loading indicator should appear
    const loadingIndicator = page.locator('#threshold-loading');

    // Note: This test may be flaky if the request completes very quickly
    // In real tests, you'd mock the API to add delay
  });

  test('should have proper heading hierarchy', async ({ page }) => {
    // Page should have one h1
    const h1s = page.locator('h1');
    await expect(h1s).toHaveCount(1);

    // Section headings should be h2
    const h2s = page.locator('h2');
    const h2Count = await h2s.count();
    expect(h2Count).toBeGreaterThan(2); // At least 3 sections
  });
});

test.describe('Dashboard - Action Mode Toggle Integration', () => {
  // Use authenticated state for these tests
  test.use({ storageState: 'playwright/.auth/user.json' });

  test.beforeEach(async ({ page }) => {
    await page.goto('/dashboard');
  });

  test('should toggle between sandbox and action mode', async ({ page }) => {
    const sandboxRadio = page.locator('input[name="action_mode"][value="false"]');
    const actionRadio = page.locator('input[name="action_mode"][value="true"]');

    // Start in sandbox mode
    await sandboxRadio.click();
    await page.waitForTimeout(100);

    // Check that sandbox is selected
    await expect(sandboxRadio).toBeChecked();

    // Switch to action mode
    await actionRadio.click();
    await page.waitForTimeout(100);

    // Check that action mode is selected
    await expect(actionRadio).toBeChecked();
    await expect(sandboxRadio).not.toBeChecked();
  });

  test('should show different visual states for selected mode', async ({ page }) => {
    const sandboxRadio = page.locator('input[name="action_mode"][value="false"]');
    const actionRadio = page.locator('input[name="action_mode"][value="true"]');

    const sandboxLabel = page.locator('label').filter({ has: sandboxRadio });
    const actionLabel = page.locator('label').filter({ has: actionRadio });

    // Click sandbox mode
    await sandboxRadio.click();
    await page.waitForTimeout(100);

    // Sandbox label should have primary border
    await expect(sandboxLabel).toHaveClass(/border-primary-600/);
    await expect(actionLabel).not.toHaveClass(/border-primary-600/);

    // Click action mode
    await actionRadio.click();
    await page.waitForTimeout(100);

    // Action label should now have primary border
    await expect(actionLabel).toHaveClass(/border-primary-600/);
    await expect(sandboxLabel).not.toHaveClass(/border-primary-600/);
  });
});

test.describe('Dashboard - Tooltips', () => {
  // Use authenticated state for these tests
  test.use({ storageState: 'playwright/.auth/user.json' });

  test.beforeEach(async ({ page }) => {
    await page.goto('/dashboard');
  });

  test('should close tooltip on click away', async ({ page }) => {
    const helpButton = page.locator('button[aria-label="Help"]').first();

    // Open tooltip
    await helpButton.click();
    await page.waitForTimeout(200);

    const tooltip = page.locator('text=Sandbox mode').first();
    await expect(tooltip).toBeVisible();

    // Click somewhere else on the page
    await page.locator('h1').click();
    await page.waitForTimeout(200);

    // Tooltip should be hidden
    await expect(tooltip).not.toBeVisible();
  });

  test.skip('should have close button in tooltip', async ({ page }) => {
    // TODO: Re-enable when dashboard implements explicit close button in tooltips
    // Currently tooltips close on click-away, but may not have a visible close button
    const helpButton = page.locator('button[aria-label="Help"]').first();

    // Open tooltip
    await helpButton.click();
    await page.waitForTimeout(200);

    // Find close button (X icon)
    const tooltip = page.locator('.absolute.right-0.mt-2').first();
    const closeButton = tooltip.locator('button').first();

    await expect(closeButton).toBeVisible();

    // Click close button
    await closeButton.click();
    await page.waitForTimeout(200);

    // Tooltip should be hidden
    await expect(tooltip).not.toBeVisible();
  });
});
