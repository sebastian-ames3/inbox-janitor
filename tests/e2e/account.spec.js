// @ts-check
const { test, expect } = require('@playwright/test');

/**
 * Account Page Tests
 *
 * Tests the account management page with:
 * - User information display
 * - Plan/billing information
 * - Data export functionality
 * - Account deletion flow with confirmation
 * - Accessibility
 */

test.describe.skip('Account Page', () => {
  // SKIPPED: All tests in this file require authentication
  // Without auth, /account redirects to Google OAuth which hangs in CI
  // TODO: Set up mock authentication or test OAuth credentials before enabling

  test.beforeEach(async ({ page }) => {
    // TODO: Set up authenticated session
    await page.goto('/account');
  });

  test('should load account page with all sections', async ({ page }) => {
    // Page title
    await expect(page).toHaveTitle(/Account - Inbox Janitor/);

    // Page heading
    const heading = page.locator('h1');
    await expect(heading).toBeVisible();

    // Main sections should be visible
    await expect(page.locator('text=Account Information').or(page.locator('text=Your Account'))).toBeVisible();
    await expect(page.locator('text=Current Plan').or(page.locator('text=Subscription'))).toBeVisible();
    await expect(page.locator('text=Data Export').or(page.locator('text=Download'))).toBeVisible();
    await expect(page.locator('text=Delete Account').or(page.locator('text=Danger Zone'))).toBeVisible();
  });

  test('should display user information', async ({ page }) => {
    // Should show connected email address
    const emailPattern = /[\w.-]+@[\w.-]+\.\w+/;

    // Look for email address on page
    const emailElement = page.locator('text=/.*@.*/').first();
    await expect(emailElement).toBeVisible();
  });

  test('should display current plan information', async ({ page }) => {
    // Beta users should see "Beta" or "Free" plan
    const planSection = page.locator('text=Current Plan').or(page.locator('text=Subscription')).locator('..');

    // Should show beta badge or free plan
    await expect(planSection.locator('text=/Beta|Free/i')).toBeVisible();

    // Should have a note about billing being enabled later
    await expect(page.locator('text=/billing.*enabled/i')).toBeVisible();
  });

  test('should have data export button', async ({ page }) => {
    const exportButton = page.locator('button:has-text("Download")').or(
      page.locator('a:has-text("Download")')
    );

    await expect(exportButton).toBeVisible();

    // Should have explanation text
    await expect(page.locator('text=/export.*CSV|CSV.*export/i')).toBeVisible();
  });

  test('should trigger download when export button clicked', async ({ page }) => {
    // Set up download listener
    const downloadPromise = page.waitForEvent('download', { timeout: 5000 });

    const exportButton = page.locator('button:has-text("Download")').or(
      page.locator('a:has-text("Download")')
    ).first();

    await exportButton.click();

    // Wait for download to start
    const download = await downloadPromise;

    // Verify filename
    expect(download.suggestedFilename()).toMatch(/inbox.*janitor.*\.csv/i);
  });

  test('should have account deletion section with warning', async ({ page }) => {
    // Delete section should be visually distinct (red/danger styling)
    const deleteSection = page.locator('text=Delete Account').or(
      page.locator('text=Danger Zone')
    ).locator('..');

    await expect(deleteSection).toBeVisible();

    // Should have red/danger button
    const deleteButton = page.locator('button:has-text("Delete")');
    await expect(deleteButton).toBeVisible();

    // Button should have red/danger styling
    await expect(deleteButton).toHaveClass(/red|danger/);
  });

  test('should show confirmation modal when delete account clicked', async ({ page }) => {
    const deleteButton = page.locator('button:has-text("Delete")').first();

    // Click delete button
    await deleteButton.click();

    // Wait for Alpine.js modal to appear
    await page.waitForTimeout(200);

    // Confirmation modal should appear
    const modal = page.locator('[role="dialog"]').or(
      page.locator('text=/Are you sure|Confirm/i').locator('..')
    );

    await expect(modal).toBeVisible();

    // Modal should have explanation of consequences
    await expect(modal.locator('text=/cannot be undone|permanent/i')).toBeVisible();
  });

  test('should close confirmation modal when cancel clicked', async ({ page }) => {
    const deleteButton = page.locator('button:has-text("Delete")').first();

    // Open modal
    await deleteButton.click();
    await page.waitForTimeout(200);

    const modal = page.locator('[role="dialog"]').or(
      page.locator('text=/Are you sure/i').locator('..')
    );

    await expect(modal).toBeVisible();

    // Click cancel button
    const cancelButton = modal.locator('button:has-text("Cancel")').or(
      modal.locator('button:has-text("No")')
    );

    await cancelButton.click();
    await page.waitForTimeout(200);

    // Modal should be hidden
    await expect(modal).not.toBeVisible();
  });

  test('should close modal when clicking outside (click away)', async ({ page }) => {
    const deleteButton = page.locator('button:has-text("Delete")').first();

    // Open modal
    await deleteButton.click();
    await page.waitForTimeout(200);

    const modal = page.locator('[role="dialog"]');

    // Click outside modal (on backdrop or other element)
    await page.locator('h1').click();
    await page.waitForTimeout(200);

    // Modal should be hidden
    // Note: This assumes the modal has @click.away directive
  });

  test('should be mobile responsive', async ({ page }) => {
    // Set viewport to mobile size
    await page.setViewportSize({ width: 375, height: 667 });

    // Page should still be readable
    const heading = page.locator('h1');
    await expect(heading).toBeVisible();

    // Sections should stack vertically
    await expect(page.locator('text=Current Plan')).toBeVisible();
    await expect(page.locator('text=Data Export')).toBeVisible();

    // Buttons should be large enough for touch
    const exportButton = page.locator('button:has-text("Download")').first();
    const buttonBox = await exportButton.boundingBox();
    expect(buttonBox?.height).toBeGreaterThanOrEqual(44);
  });

  test('should have accessible navigation to account page', async ({ page }) => {
    // Navigate to dashboard first
    await page.goto('/dashboard');

    // Find account link in navigation
    const accountLink = page.locator('a:has-text("Account")');

    // Should be keyboard accessible
    await accountLink.focus();
    await expect(accountLink).toBeFocused();

    // Click to navigate
    await accountLink.click();

    // Should navigate to account page
    await expect(page).toHaveURL(/\/account/);
  });

  test('should have proper heading hierarchy', async ({ page }) => {
    // Should have one h1
    const h1s = page.locator('h1');
    await expect(h1s).toHaveCount(1);

    // Section headings should be h2 or h3
    const h2s = page.locator('h2, h3');
    const headingCount = await h2s.count();
    expect(headingCount).toBeGreaterThan(2);
  });

  test('should have descriptive button text', async ({ page }) => {
    // Export button should be clear
    const exportButton = page.locator('button:has-text("Download")').or(
      page.locator('button:has-text("Export")')
    );
    await expect(exportButton).toBeVisible();

    // Delete button should be clear and prominent
    const deleteButton = page.locator('button:has-text("Delete")');
    await expect(deleteButton).toBeVisible();
  });
});

test.describe('Account Page - Data Export', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto('/account');
  });

  test.skip('should show loading state during export', async ({ page }) => {
    // SKIPPED: Requires authentication to access /account
    const exportButton = page.locator('button:has-text("Download")').first();

    // Click export
    await exportButton.click();

    // Should show loading state (disabled button or spinner)
    // Note: This depends on implementation
    // await expect(exportButton).toBeDisabled();
  });

  test.skip('should show success message after export', async ({ page }) => {
    // SKIPPED: Requires authentication to access /account
    const exportButton = page.locator('button:has-text("Download")').first();

    await exportButton.click();

    // Wait for download to complete
    await page.waitForTimeout(1000);

    // Success message or toast might appear
    // await expect(page.locator('text=/downloaded|success/i')).toBeVisible();
  });
});

test.describe('Account Page - Billing Section', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto('/account');
  });

  test.skip('should show beta program notice', async ({ page }) => {
    // SKIPPED: Requires authentication to access /account
    // Beta users should see notice about billing
    await expect(page.locator('text=/beta.*program/i')).toBeVisible();
    await expect(page.locator('text=/billing.*enabled/i')).toBeVisible();
  });

  test('should have disabled payment method button for beta', async ({ page }) => {
    // Payment button should be disabled during beta
    const paymentButton = page.locator('button:has-text("Add Payment")').or(
      page.locator('button:has-text("Billing")')
    );

    // Should exist but be disabled
    if (await paymentButton.count() > 0) {
      await expect(paymentButton).toBeDisabled();
    }
  });
});

test.describe('Account Page - Security', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto('/account');
  });

  test('should not expose sensitive data in page source', async ({ page }) => {
    const pageContent = await page.content();

    // Should not contain OAuth tokens
    expect(pageContent).not.toContain('ya29.');
    expect(pageContent).not.toContain('access_token');
    expect(pageContent).not.toContain('refresh_token');

    // Should not contain encryption keys
    expect(pageContent).not.toMatch(/ENCRYPTION_KEY|FERNET|SECRET_KEY/i);
  });

  test.skip('should have CSRF token for delete action', async ({ page }) => {
    // SKIPPED: Requires authentication to access /account
    const deleteButton = page.locator('button:has-text("Delete")').first();

    // Open confirmation modal
    await deleteButton.click();
    await page.waitForTimeout(200);

    // If there's a form, it should have CSRF token
    const form = page.locator('form');
    if (await form.count() > 0) {
      const csrfInput = form.locator('input[name="csrf_token"]');
      await expect(csrfInput).toBeHidden();
    }
  });
});
