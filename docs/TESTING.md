# Manual Testing Checklist

**Last Updated:** 2025-11-04
**Purpose:** Pre-deployment manual testing to validate security, functionality, and user experience.

This checklist must be completed before any production deployment or major release.

---

## Table of Contents

1. [Browser Compatibility](#browser-compatibility)
2. [Mobile Responsiveness](#mobile-responsiveness)
3. [Keyboard Navigation](#keyboard-navigation)
4. [Screen Reader Accessibility](#screen-reader-accessibility)
5. [OAuth Flow](#oauth-flow)
6. [Dashboard Functionality](#dashboard-functionality)
7. [Security Validation](#security-validation)
8. [Session Management](#session-management)
9. [Email Functionality](#email-functionality)
10. [Performance](#performance)
11. [Error Handling](#error-handling)

---

## Browser Compatibility

Test on all major browsers to ensure cross-browser compatibility.

### Desktop Browsers

- [ ] **Chrome (Latest)**
  - [ ] Landing page loads correctly
  - [ ] Dashboard interactive elements work (sliders, toggles)
  - [ ] Forms submit successfully
  - [ ] HTMX requests work
  - [ ] Alpine.js components function
  - [ ] No console errors

- [ ] **Firefox (Latest)**
  - [ ] Landing page loads correctly
  - [ ] Dashboard interactive elements work
  - [ ] Forms submit successfully
  - [ ] HTMX requests work
  - [ ] Alpine.js components function
  - [ ] No console errors

- [ ] **Safari (Latest)**
  - [ ] Landing page loads correctly
  - [ ] Dashboard interactive elements work
  - [ ] Forms submit successfully
  - [ ] HTMX requests work
  - [ ] Alpine.js components function
  - [ ] No console errors

- [ ] **Edge (Latest)**
  - [ ] Landing page loads correctly
  - [ ] All interactive features work
  - [ ] No console errors

### Mobile Browsers

- [ ] **Mobile Chrome (Android)**
  - [ ] Pages render correctly
  - [ ] Touch targets are ≥44x44px
  - [ ] Forms are usable
  - [ ] Mobile menu works

- [ ] **Mobile Safari (iOS)**
  - [ ] Pages render correctly
  - [ ] Touch targets are ≥44x44px
  - [ ] Forms are usable
  - [ ] Mobile menu works

---

## Mobile Responsiveness

Test on various screen sizes to ensure responsive design.

### Viewport Sizes to Test

- [ ] **Mobile (375px - iPhone SE)**
  - [ ] Landing page: Single column layout
  - [ ] Navigation: Hamburger menu visible
  - [ ] Dashboard: Sections stack vertically
  - [ ] Forms: Full-width, easy to fill
  - [ ] Touch targets: ≥44px height/width
  - [ ] Text: Readable without zooming

- [ ] **Tablet (768px - iPad)**
  - [ ] Landing page: Adapts to wider screen
  - [ ] Navigation: Desktop nav appears at md breakpoint
  - [ ] Dashboard: Readable, well-spaced
  - [ ] Forms: Appropriately sized

- [ ] **Desktop (1024px and above)**
  - [ ] Landing page: Full desktop layout
  - [ ] Dashboard: Multi-column where appropriate
  - [ ] Max-width containers prevent overly wide text

### Specific Elements

- [ ] **Mobile Menu**
  - [ ] Hamburger icon visible on mobile
  - [ ] Click hamburger → menu slides in
  - [ ] Click away → menu closes
  - [ ] Menu items clickable
  - [ ] No horizontal overflow

- [ ] **Tables (Audit Log)**
  - [ ] Horizontal scroll on mobile OR
  - [ ] Card layout on mobile
  - [ ] No content cut off

- [ ] **Modals**
  - [ ] Full-width on mobile
  - [ ] Properly sized on desktop
  - [ ] Close button accessible

---

## Keyboard Navigation

Test full keyboard accessibility (no mouse required).

### Tab Order

- [ ] **Landing Page**
  - [ ] Tab → Skip to main content link (first)
  - [ ] Tab → Logo
  - [ ] Tab → Navigation links
  - [ ] Tab → "Connect Gmail" CTA
  - [ ] Tab → Footer links
  - [ ] Tab order is logical (top to bottom, left to right)

- [ ] **Dashboard**
  - [ ] Tab through all interactive elements
  - [ ] Tab order follows visual order
  - [ ] No focus trapped accidentally

### Keyboard Shortcuts

- [ ] **Forms**
  - [ ] Tab navigates between fields
  - [ ] Shift+Tab navigates backwards
  - [ ] Enter submits forms
  - [ ] Escape closes modals

- [ ] **Radio Buttons**
  - [ ] Tab to radio group
  - [ ] Arrow keys switch between options
  - [ ] Space selects option

- [ ] **Sliders**
  - [ ] Tab to slider
  - [ ] Arrow keys adjust value
  - [ ] Home/End for min/max

- [ ] **Modals**
  - [ ] Escape closes modal
  - [ ] Focus returns to trigger element after close

### Focus Indicators

- [ ] All interactive elements have visible focus ring
- [ ] Focus ring is high contrast (visible against background)
- [ ] Custom focus styles applied (Tailwind focus-visible)

---

## Screen Reader Accessibility

Test with screen readers to ensure accessibility for visually impaired users.

### Tools

- **Windows:** NVDA (free) or JAWS
- **Mac:** VoiceOver (built-in)
- **Linux:** Orca

### Testing Checklist

- [ ] **Landmarks**
  - [ ] Navigation announced as "navigation"
  - [ ] Main content announced as "main"
  - [ ] Footer announced as "contentinfo"

- [ ] **Headings**
  - [ ] Page has one h1
  - [ ] Headings are in logical order (no skipping)
  - [ ] Screen reader can navigate by headings

- [ ] **Forms**
  - [ ] Labels associated with inputs
  - [ ] Required fields announced
  - [ ] Error messages announced
  - [ ] ARIA labels present on unlabeled controls

- [ ] **Images**
  - [ ] All images have alt text (when applicable)
  - [ ] Decorative images have alt="" or aria-hidden="true"

- [ ] **Buttons**
  - [ ] All buttons have accessible names
  - [ ] Icon-only buttons have aria-label

- [ ] **Live Regions**
  - [ ] HTMX loading indicators use aria-live
  - [ ] Success/error messages announced
  - [ ] Dynamic updates announced

- [ ] **Skip Links**
  - [ ] "Skip to main content" link present
  - [ ] Skip link works (jumps to main content)

---

## OAuth Flow

Test the complete OAuth authentication flow with a real Google account.

### Initial Connection

- [ ] **Landing Page**
  - [ ] "Connect Gmail" button visible and clickable
  - [ ] Click button → redirects to /auth/google/login

- [ ] **Google OAuth**
  - [ ] Redirects to accounts.google.com
  - [ ] Shows Google consent screen
  - [ ] Lists requested permissions (Gmail read/modify)
  - [ ] "Allow" button works

- [ ] **Callback**
  - [ ] Redirects back to app after consent
  - [ ] URL contains `code` parameter (authorization code)
  - [ ] No errors in browser console
  - [ ] No error messages displayed

- [ ] **Session Creation**
  - [ ] User is logged in (session cookie set)
  - [ ] Redirected to /welcome page
  - [ ] Welcome page shows connected email
  - [ ] No tokens visible in page source (inspect DevTools)

### Error Cases

- [ ] **User Denies Permission**
  - [ ] Redirects to /auth/error
  - [ ] Shows helpful error message
  - [ ] "Try Again" button present
  - [ ] Try Again redirects back to landing

- [ ] **Invalid State Token (CSRF)**
  - [ ] Manipulate state parameter in callback URL
  - [ ] Should reject and show error
  - [ ] Should NOT create session

### Token Security

- [ ] **DevTools Inspection**
  - [ ] Open browser DevTools → Network tab
  - [ ] Complete OAuth flow
  - [ ] Verify tokens are NOT in query parameters
  - [ ] Verify tokens are NOT in response bodies visible to client

- [ ] **Page Source**
  - [ ] View page source (Ctrl+U)
  - [ ] Search for "ya29." → Should not be found
  - [ ] Search for "access_token" → Should not be found (except csrf_token)
  - [ ] Search for "refresh_token" → Should not be found

- [ ] **Cookies**
  - [ ] DevTools → Application → Cookies
  - [ ] Session cookie should be HttpOnly (not accessible via JS)
  - [ ] No access_token or refresh_token cookies
  - [ ] CSRF token cookie should be present (not HttpOnly)

---

## Dashboard Functionality

Test all dashboard features and settings.

### Settings Display

- [ ] **Connected Account**
  - [ ] Shows connected email address
  - [ ] Shows "Active" status
  - [ ] Disconnect button present

- [ ] **Action Mode**
  - [ ] Radio buttons for Sandbox/Action mode
  - [ ] Current mode selected correctly
  - [ ] Help tooltip (?) opens and closes
  - [ ] Warning banner shows in Sandbox mode

- [ ] **Confidence Thresholds**
  - [ ] Auto-trash slider shows current value
  - [ ] Auto-archive slider shows current value
  - [ ] Slider value updates live (Alpine.js)
  - [ ] Values displayed next to sliders

- [ ] **Weekly Digest**
  - [ ] Checkbox for enable/disable
  - [ ] Schedule dropdown (daily/weekly/off)
  - [ ] Current schedule selected

### Settings Updates

- [ ] **Action Mode Toggle**
  - [ ] Click Sandbox radio → mode changes
  - [ ] Click Action radio → mode changes
  - [ ] Visual feedback (border color changes)
  - [ ] Page reload shows saved selection

- [ ] **Threshold Sliders**
  - [ ] Adjust slider → value updates
  - [ ] Click "Save Thresholds" → form submits
  - [ ] Success message appears
  - [ ] Page reload shows saved values

- [ ] **Form Validation**
  - [ ] Try invalid values (if possible)
  - [ ] Validation errors displayed
  - [ ] Form does not submit with errors

### HTMX Interactions

- [ ] **Partial Updates**
  - [ ] Form submissions don't reload entire page
  - [ ] Only target div updates
  - [ ] Loading indicator appears during request
  - [ ] Success message appears in target div

- [ ] **CSRF Protection**
  - [ ] Inspect form HTML → has hidden csrf_token field
  - [ ] Network tab → POST requests include X-CSRF-Token header
  - [ ] Requests without CSRF token rejected (test manually if possible)

### Alpine.js Components

- [ ] **Tooltips**
  - [ ] Click help (?) → tooltip opens
  - [ ] Click close (X) → tooltip closes
  - [ ] Click away → tooltip closes
  - [ ] Multiple tooltips can't be open simultaneously

- [ ] **Modals (if present)**
  - [ ] Modal opens on trigger
  - [ ] Modal closes on close button
  - [ ] Modal closes on click outside
  - [ ] Modal closes on Escape key

---

## Security Validation

Validate security measures are working correctly.

### CSRF Protection

- [ ] **Visual Checks**
  - [ ] Forms have hidden csrf_token input
  - [ ] DevTools → Network → POST requests have X-CSRF-Token header

- [ ] **Manual Test (Advanced)**
  - [ ] Copy form HTML
  - [ ] Create test page without CSRF token
  - [ ] Try to submit → Should receive 403 Forbidden

### XSS Prevention

- [ ] **Page Source Inspection**
  - [ ] No unescaped user content
  - [ ] Email subjects displayed as text (not HTML)
  - [ ] Special characters escaped (`<` becomes `&lt;`)

- [ ] **Content-Security-Policy**
  - [ ] DevTools → Network → Response Headers
  - [ ] CSP header present
  - [ ] CSP includes script-src, default-src directives

### Security Headers

- [ ] **Response Headers** (DevTools → Network → Headers)
  - [ ] X-Frame-Options: DENY
  - [ ] X-Content-Type-Options: nosniff
  - [ ] X-XSS-Protection: 1; mode=block
  - [ ] Content-Security-Policy: (policy present)
  - [ ] Referrer-Policy: strict-origin-when-cross-origin
  - [ ] Permissions-Policy: geolocation=(), microphone=(), camera=()
  - [ ] (Production only) Strict-Transport-Security: max-age=31536000

### Token Exposure

- [ ] **HTML Source**
  - [ ] No "ya29." (Google access tokens)
  - [ ] No "1//" (Google refresh tokens)
  - [ ] No ENCRYPTION_KEY, SECRET_KEY
  - [ ] No DATABASE_URL, REDIS_URL
  - [ ] No API keys (OPENAI_API_KEY, POSTMARK_API_KEY)

- [ ] **JavaScript Console**
  - [ ] No sensitive data in global variables
  - [ ] No tokens in window object
  - [ ] No credentials logged to console

- [ ] **Cookies**
  - [ ] No access_token or refresh_token cookies
  - [ ] Session cookie values are opaque (not readable data)

---

## Session Management

Test session behavior and security.

### Session Lifecycle

- [ ] **Login**
  - [ ] After OAuth, session cookie is set
  - [ ] Session persists across page refreshes
  - [ ] Can access protected pages (dashboard)

- [ ] **Logout** (if implemented)
  - [ ] Click logout → session cleared
  - [ ] Redirected to landing page
  - [ ] Cannot access protected pages anymore
  - [ ] Session cookie deleted or set to empty

- [ ] **Expiration** (24 hours)
  - [ ] (Cannot test in real-time, verify in code/config)
  - [ ] Session max_age set to 86400 seconds
  - [ ] After expiration, user must re-authenticate

### Cookie Security

- [ ] **Session Cookie Attributes** (DevTools → Application → Cookies)
  - [ ] HttpOnly: ✓ (checkmark present)
  - [ ] Secure: ✓ in production (HTTPS only)
  - [ ] SameSite: Lax
  - [ ] Path: /
  - [ ] Max-Age or Expires: 86400 seconds (24 hours)

---

## Email Functionality

Test email sending (if Postmark is configured).

### Welcome Email

- [ ] **After OAuth**
  - [ ] Welcome email received within 5 minutes
  - [ ] Email from: noreply@inboxjanitor.com
  - [ ] Email subject contains "Welcome"
  - [ ] Email body explains sandbox mode
  - [ ] Email has link to settings dashboard
  - [ ] Email has unsubscribe link (CAN-SPAM)

- [ ] **Email Content**
  - [ ] No HTML rendering issues
  - [ ] Links are clickable
  - [ ] Text version is readable

### Email Security

- [ ] **Email Headers** (View raw email source)
  - [ ] From address is legitimate
  - [ ] No extra Bcc/Cc headers (header injection check)
  - [ ] SPF, DKIM pass (if configured)

---

## Performance

Test page load times and responsiveness.

### Page Load Times

- [ ] **Landing Page**
  - [ ] Loads in <2 seconds (good connection)
  - [ ] Loads in <5 seconds (3G connection)
  - [ ] Largest Contentful Paint (LCP) < 2.5s

- [ ] **Dashboard**
  - [ ] Loads in <2 seconds
  - [ ] Interactive in <3 seconds
  - [ ] No layout shift (CLS < 0.1)

### Lighthouse Scores

Run Lighthouse audit in Chrome DevTools:

- [ ] **Performance:** >90
- [ ] **Accessibility:** 100
- [ ] **Best Practices:** >90
- [ ] **SEO:** >90

### Network Performance

- [ ] **Static Assets**
  - [ ] Tailwind CSS is minified (<100KB)
  - [ ] Static files cached (Cache-Control header)
  - [ ] HTMX/Alpine.js loaded from CDN (cached)

- [ ] **API Requests**
  - [ ] Settings updates respond in <500ms
  - [ ] No unnecessary requests
  - [ ] HTMX requests efficient (partial updates)

---

## Error Handling

Test error scenarios to ensure graceful failures.

### Network Errors

- [ ] **Simulate Offline**
  - [ ] DevTools → Network → Offline
  - [ ] Try to load page → Show error
  - [ ] Try to submit form → Show error message
  - [ ] No crashes or blank pages

### Form Errors

- [ ] **Invalid Input**
  - [ ] Enter invalid threshold (>1.0) → Validation error
  - [ ] Enter invalid email → Validation error
  - [ ] Error messages are clear and helpful

### Server Errors

- [ ] **500 Internal Server Error**
  - [ ] (Trigger by breaking something temporarily)
  - [ ] User sees friendly error page
  - [ ] No stack traces or sensitive info exposed
  - [ ] Error logged to Sentry

### 404 Not Found

- [ ] **Invalid URLs**
  - [ ] Go to /nonexistent-page → 404 error
  - [ ] 404 page is styled
  - [ ] Link back to home page

---

## Pre-Deployment Checklist

Final checks before deploying to production.

### Code Quality

- [ ] All automated tests pass (`pytest tests/`)
- [ ] All E2E tests pass (`npm test`)
- [ ] No failing CI/CD checks
- [ ] Code reviewed by second person (if applicable)

### Security

- [ ] Bandit scan passed (no HIGH or MEDIUM issues)
- [ ] npm audit passed (no vulnerabilities)
- [ ] No secrets in codebase (git-secrets scan)
- [ ] .env file not committed
- [ ] All environment variables set in Railway

### Database

- [ ] Migrations applied (`alembic upgrade head`)
- [ ] Database backups enabled
- [ ] Connection pooling configured

### Monitoring

- [ ] Sentry configured and receiving events
- [ ] Railway logs accessible
- [ ] Health endpoint returns 200 OK
- [ ] Uptime monitoring set up (if applicable)

### Documentation

- [ ] README.md up to date
- [ ] CHANGELOG.md updated
- [ ] Deployment notes documented

---

## Testing Notes

### Test Environment

- **Local:** http://localhost:8000
- **Staging:** (Railway preview URL from PR)
- **Production:** https://inbox-janitor-production-03fc.up.railway.app

### Test Data

- Use test Gmail account for OAuth testing
- Do NOT test with production user data
- Clean up test data after testing

### Issue Reporting

If you find issues during manual testing:

1. Note exact steps to reproduce
2. Include browser/device info
3. Attach screenshots if relevant
4. Check browser console for errors
5. Report in GitHub Issues

---

## Completed By

**Tester:** _______________
**Date:** _______________
**Environment:** [ ] Local [ ] Staging [ ] Production
**Result:** [ ] PASS [ ] FAIL (see issues)

**Issues Found:** _______________

---

**End of Manual Testing Checklist**
