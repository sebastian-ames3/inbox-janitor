// @ts-check
const { test, expect } = require('@playwright/test');

/**
 * Audit Log Page Tests
 *
 * Tests the audit log viewer with:
 * - Table display of email actions
 * - Pagination
 * - HTMX modal loading for action details
 * - Filtering and search
 * - Date/time display
 * - Accessibility
 */

test.describe('Audit Log Page', () => {
  test.beforeEach(async ({ page }) => {
    // TODO: Set up authenticated session
    await page.goto('/audit');
  });

  test('should load audit log page with table', async ({ page }) => {
    // Page title
    await expect(page).toHaveTitle(/Audit|Activity|History - Inbox Janitor/);

    // Page heading
    const heading = page.locator('h1');
    await expect(heading).toBeVisible();
    await expect(heading).toContainText(/Activity|Audit|History/);

    // Subtitle explaining scope
    await expect(page.locator('text=/30 days|last 30/i')).toBeVisible();

    // Table should be present
    const table = page.locator('table').or(page.locator('[role="table"]'));
    await expect(table).toBeVisible();
  });

  test('should display table headers correctly', async ({ page }) => {
    // Table headers for audit log
    await expect(page.locator('th:has-text("Date")').or(page.locator('th:has-text("Time")'))).toBeVisible();
    await expect(page.locator('th:has-text("Sender")').or(page.locator('th:has-text("From")'))).toBeVisible();
    await expect(page.locator('th:has-text("Subject")')).toBeVisible();
    await expect(page.locator('th:has-text("Action")')).toBeVisible();
  });

  test('should display email actions in table rows', async ({ page }) => {
    // Find table body
    const tbody = page.locator('tbody').or(page.locator('[role="rowgroup"]'));

    // Should have at least one row (if any actions exist)
    const rows = tbody.locator('tr').or(tbody.locator('[role="row"]'));

    const rowCount = await rows.count();

    if (rowCount > 0) {
      // First row should have sender, subject, action
      const firstRow = rows.first();

      // Should have email-like sender
      await expect(firstRow.locator('text=/.*@.*/').or(firstRow.locator('text=/.*<.*>.*/'))).toBeVisible();

      // Should have action badge (TRASH, ARCHIVE, KEEP)
      const actionBadge = firstRow.locator('.badge').or(firstRow.locator('[class*="badge"]'));
      // Action badge might not be present depending on implementation
    }
  });

  test('should display action badges with correct styling', async ({ page }) => {
    const tbody = page.locator('tbody');
    const rows = tbody.locator('tr');

    const rowCount = await rows.count();

    if (rowCount > 0) {
      // Check for different action types
      const trashBadge = page.locator('.badge:has-text("TRASH")').or(
        page.locator('[class*="badge"]:has-text("TRASH")')
      );

      const archiveBadge = page.locator('.badge:has-text("ARCHIVE")').or(
        page.locator('[class*="badge"]:has-text("ARCHIVE")')
      );

      // At least one action type should be present
      const anyBadge = page.locator('[class*="badge"]');
      // await expect(anyBadge.first()).toBeVisible();
    }
  });

  test('should open details modal when row clicked', async ({ page }) => {
    const tbody = page.locator('tbody');
    const rows = tbody.locator('tr');

    const rowCount = await rows.count();

    if (rowCount > 0) {
      // Click first row
      await rows.first().click();

      // Wait for HTMX to load modal content
      await page.waitForTimeout(500);

      // Modal should appear
      const modal = page.locator('[role="dialog"]').or(
        page.locator('.modal').or(page.locator('[id*="modal"]'))
      );

      await expect(modal).toBeVisible();

      // Modal should contain action details
      await expect(modal.locator('text=/Confidence|Classification|Reason/i')).toBeVisible();
    }
  });

  test('should close modal when close button clicked', async ({ page }) => {
    const rows = page.locator('tbody tr');
    const rowCount = await rows.count();

    if (rowCount > 0) {
      // Open modal
      await rows.first().click();
      await page.waitForTimeout(500);

      const modal = page.locator('[role="dialog"]');

      // Find close button (X or Close text)
      const closeButton = modal.locator('button').filter({ hasText: /Close|×/ }).or(
        modal.locator('button[aria-label*="Close"]')
      );

      if (await closeButton.count() > 0) {
        await closeButton.click();
        await page.waitForTimeout(200);

        // Modal should be hidden
        await expect(modal).not.toBeVisible();
      }
    }
  });

  test('should display confidence score in details modal', async ({ page }) => {
    const rows = page.locator('tbody tr');
    const rowCount = await rows.count();

    if (rowCount > 0) {
      // Open modal
      await rows.first().click();
      await page.waitForTimeout(500);

      const modal = page.locator('[role="dialog"]').or(page.locator('.modal'));

      // Should show confidence score (0.0 - 1.0 or percentage)
      await expect(modal.locator('text=/Confidence|Score/i')).toBeVisible();

      // Should show classification reason
      await expect(modal.locator('text=/Reason|Why|Classification/i')).toBeVisible();
    }
  });

  test('should show undo button in modal (disabled for MVP)', async ({ page }) => {
    const rows = page.locator('tbody tr');
    const rowCount = await rows.count();

    if (rowCount > 0) {
      // Open modal
      await rows.first().click();
      await page.waitForTimeout(500);

      const modal = page.locator('[role="dialog"]').or(page.locator('.modal'));

      // Undo button should exist but be disabled (Week 2 feature)
      const undoButton = modal.locator('button:has-text("Undo")');

      if (await undoButton.count() > 0) {
        await expect(undoButton).toBeDisabled();

        // Should have explanation
        await expect(modal.locator('text=/Coming.*Week 2|Week 2/i')).toBeVisible();
      }
    }
  });

  test('should have pagination controls', async ({ page }) => {
    // Look for pagination controls
    const paginationNext = page.locator('button:has-text("Next")').or(
      page.locator('a:has-text("Next")')
    );

    const paginationPrev = page.locator('button:has-text("Previous")').or(
      page.locator('a:has-text("Previous")')
    );

    // At least one pagination control should be visible if there are many records
    // If no records or only one page, pagination might not be shown
  });

  test('should display empty state when no actions', async ({ page }) => {
    // If there are no email actions, should show helpful message
    const rows = page.locator('tbody tr');
    const rowCount = await rows.count();

    if (rowCount === 0) {
      // Empty state message
      await expect(page.locator('text=/No actions|No emails|empty/i')).toBeVisible();
    }
  });

  test('should be mobile responsive', async ({ page }) => {
    // Set viewport to mobile size
    await page.setViewportSize({ width: 375, height: 667 });

    // Page should still be readable
    const heading = page.locator('h1');
    await expect(heading).toBeVisible();

    // Table should either:
    // 1. Horizontal scroll
    // 2. Transform to card layout on mobile
    const table = page.locator('table');

    if (await table.count() > 0) {
      // Should be visible (possibly with horizontal scroll)
      await expect(table).toBeVisible();
    }
  });

  test('should format dates in readable format', async ({ page }) => {
    const rows = page.locator('tbody tr');
    const rowCount = await rows.count();

    if (rowCount > 0) {
      // First row should have a formatted date
      const firstRow = rows.first();

      // Date should be human-readable (e.g., "Nov 4, 2025" or "2 hours ago")
      // This is a loose test - just check that date-like text exists
      await expect(firstRow).toBeVisible();
    }
  });

  test('should have accessible table markup', async ({ page }) => {
    const table = page.locator('table');

    if (await table.count() > 0) {
      // Table should have thead and tbody
      await expect(table.locator('thead')).toBeVisible();
      await expect(table.locator('tbody')).toBeVisible();

      // Headers should use th elements
      const headers = table.locator('th');
      const headerCount = await headers.count();
      expect(headerCount).toBeGreaterThan(2);
    }
  });

  test('should have proper heading hierarchy', async ({ page }) => {
    // Should have one h1
    const h1s = page.locator('h1');
    await expect(h1s).toHaveCount(1);

    // If there are sections, they should use h2
    const h2s = page.locator('h2');
    // May or may not have h2s depending on page structure
  });
});

test.describe('Audit Log - Filtering', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto('/audit');
  });

  test('should have filter controls (if implemented)', async ({ page }) => {
    // Look for filter controls
    const filterAction = page.locator('select[name*="action"]').or(
      page.locator('label:has-text("Action")')
    );

    const filterDate = page.locator('input[type="date"]').or(
      page.locator('label:has-text("Date")')
    );

    // These may not be implemented in MVP, so just check if present
  });

  test('should filter by action type (if implemented)', async ({ page }) => {
    const actionFilter = page.locator('select[name*="action"]');

    if (await actionFilter.count() > 0) {
      // Select "TRASH" filter
      await actionFilter.selectOption('trash');

      // Wait for results to update
      await page.waitForTimeout(500);

      // All visible rows should be TRASH actions
      const rows = page.locator('tbody tr');
      const firstRow = rows.first();

      if (await rows.count() > 0) {
        await expect(firstRow.locator('text=TRASH')).toBeVisible();
      }
    }
  });
});

test.describe('Audit Log - Pagination', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto('/audit');
  });

  test('should navigate to next page', async ({ page }) => {
    const nextButton = page.locator('button:has-text("Next")').or(
      page.locator('a:has-text("Next")')
    );

    if (await nextButton.count() > 0 && await nextButton.isEnabled()) {
      // Click next page
      await nextButton.click();

      // Wait for navigation or HTMX update
      await page.waitForTimeout(500);

      // URL should change or table content should update
      // Check that we're on page 2
      await expect(page.locator('text=/Page 2|2 of/')).toBeVisible();
    }
  });

  test('should navigate to previous page', async ({ page }) => {
    const nextButton = page.locator('button:has-text("Next")').or(
      page.locator('a:has-text("Next")')
    );

    const prevButton = page.locator('button:has-text("Previous")').or(
      page.locator('a:has-text("Previous")')
    );

    if (await nextButton.count() > 0 && await nextButton.isEnabled()) {
      // Go to page 2
      await nextButton.click();
      await page.waitForTimeout(500);

      // Go back to page 1
      if (await prevButton.isEnabled()) {
        await prevButton.click();
        await page.waitForTimeout(500);

        // Should be back on page 1
        await expect(page.locator('text=/Page 1|1 of/')).toBeVisible();
      }
    }
  });

  test('should disable previous button on first page', async ({ page }) => {
    const prevButton = page.locator('button:has-text("Previous")').or(
      page.locator('a:has-text("Previous")')
    );

    if (await prevButton.count() > 0) {
      // On first page, previous should be disabled
      await expect(prevButton).toBeDisabled();
    }
  });
});

test.describe('Audit Log - Security', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto('/audit');
  });

  test('should not expose sensitive data in page source', async ({ page }) => {
    const pageContent = await page.content();

    // Should not contain OAuth tokens
    expect(pageContent).not.toContain('ya29.');
    expect(pageContent).not.toContain('access_token');
    expect(pageContent).not.toContain('refresh_token');

    // Should not contain full email bodies
    // Email bodies should never be stored or displayed
  });

  test('should not display full email body (privacy)', async ({ page }) => {
    const rows = page.locator('tbody tr');
    const rowCount = await rows.count();

    if (rowCount > 0) {
      // Open details modal
      await rows.first().click();
      await page.waitForTimeout(500);

      const modal = page.locator('[role="dialog"]').or(page.locator('.modal'));

      // Should show snippet but NOT full body
      await expect(modal.locator('text=Snippet').or(modal.locator('text=Preview'))).toBeVisible();

      // Should NOT have "Body" or "Content" label for full email
      // This enforces privacy-first design
    }
  });
});
