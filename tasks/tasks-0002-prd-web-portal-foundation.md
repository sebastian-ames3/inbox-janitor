# Task List: Web Portal Foundation + Email Templates

**Based on:** PRD 0002 - Web Portal Foundation + Email Templates
**Created:** 2025-11-04
**Status:** Ready for Implementation

---

## Relevant Files

### New Files to Create

**Templates (Jinja2 HTML):**
- `app/templates/base.html` - Base layout with navigation, footer, security headers
- `app/templates/landing.html` - Marketing landing page
- `app/templates/auth/welcome.html` - Post-OAuth success page
- `app/templates/auth/error.html` - OAuth error page
- `app/templates/portal/dashboard.html` - Settings dashboard with all controls
- `app/templates/portal/account.html` - Account management page
- `app/templates/portal/audit.html` - Audit log viewer (simple, 30 days)
- `app/templates/components/modal.html` - Reusable modal component
- `app/templates/components/tooltip.html` - Reusable help tooltip component
- `app/templates/components/toast.html` - Toast notification template

**Static Assets:**
- `app/static/css/tailwind.css` - Compiled Tailwind CSS (with purge)
- `app/static/css/input.css` - Tailwind source file (before compilation)
- `app/static/js/app.js` - Minimal custom JavaScript (toast triggers, analytics)
- `app/static/images/logo.svg` - Inbox Janitor logo (optional for MVP)

**Backend Modules:**
- `app/modules/portal/__init__.py` - Portal module initialization
- `app/modules/portal/routes.py` - FastAPI routes for dashboard, settings, account, audit
- `app/modules/portal/forms.py` - Pydantic models for form validation
- `app/modules/portal/dependencies.py` - `get_current_user()` dependency
- `app/modules/digest/__init__.py` - Digest module initialization
- `app/modules/digest/email_service.py` - Postmark integration, email sending
- `app/modules/digest/templates.py` - Email template strings (welcome, digest, etc.)
- `app/modules/digest/schemas.py` - DigestData, SummaryData Pydantic models

**Security & Middleware:**
- `app/core/middleware.py` - Security headers, CSRF, rate limiting, session middleware
- `app/core/session.py` - Session management utilities

**Configuration:**
- `tailwind.config.js` - Tailwind configuration (colors, fonts, purge)
- `package.json` - Node.js dependencies (Tailwind CLI)

### Files to Modify

- `app/main.py` - Mount portal router, add security middleware, configure Jinja2, mount static files
- `app/modules/auth/routes.py` - Update OAuth callback to create session, redirect to welcome page
- `app/core/config.py` - Add Postmark API key, session secret, app URL settings
- `app/core/security.py` - Add session utilities, CSRF token generation
- `requirements.txt` - Add starlette-csrf, slowapi, jinja2, postmarker

### Test Files

- `tests/security/test_csrf.py` - CSRF protection tests
- `tests/security/test_xss.py` - XSS prevention tests (Jinja2 escaping)
- `tests/security/test_session.py` - Session security tests (expiration, regeneration)
- `tests/security/test_rate_limiting.py` - Rate limiting tests
- `tests/security/test_headers.py` - Security headers tests
- `tests/portal/test_dashboard.py` - Dashboard functionality tests
- `tests/portal/test_settings.py` - Settings update tests
- `tests/digest/test_email_service.py` - Email sending tests
- `tests/integration/test_oauth_flow.py` - End-to-end OAuth + session test
- `tests/accessibility/test_wcag.py` - Accessibility compliance tests

### Notes

- All templates use Jinja2 auto-escaping (verify `autoescape=True`)
- Tailwind CSS compiled via CLI (not CDN) for production performance
- HTMX and Alpine.js loaded from CDN (unpkg.com) for simplicity
- All forms include CSRF tokens (hidden input + HTMX header)
- Static files served with 1-year cache headers
- Session stored in encrypted cookies (max age: 24 hours)

---

## Tasks

- [ ] **1.0 Frontend Foundation Setup**
  - [ ] 1.1 Initialize Node.js project and install Tailwind CSS CLI
    - Run `npm init -y` in project root
    - Install: `npm install -D tailwindcss @tailwindcss/forms`
    - Create `tailwind.config.js` with custom colors (primary blue #2563eb, gray scale)
    - Create `app/static/css/input.css` with Tailwind directives
    - Add build script to `package.json`: `"build:css": "tailwindcss -i ./app/static/css/input.css -o ./app/static/css/tailwind.css --minify"`

  - [ ] 1.2 Create templates directory structure
    - Create `app/templates/` directory
    - Create subdirectories: `auth/`, `portal/`, `components/`
    - Create `app/static/` directory
    - Create subdirectories: `css/`, `js/`, `images/`

  - [ ] 1.3 Configure Jinja2 templates in FastAPI
    - Update `app/main.py` to import `Jinja2Templates` from `fastapi.templating`
    - Initialize templates: `templates = Jinja2Templates(directory="app/templates")`
    - Verify `autoescape=True` is enabled (default, but verify)
    - Mount static files: `app.mount("/static", StaticFiles(directory="app/static"), name="static")`

  - [ ] 1.4 Create base layout template (`app/templates/base.html`)
    - Include Inter font from Google Fonts: `<link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap" rel="stylesheet">`
    - Include compiled Tailwind CSS: `<link href="{{ url_for('static', path='/css/tailwind.css') }}" rel="stylesheet">`
    - Include HTMX: `<script src="https://unpkg.com/htmx.org@1.9.10"></script>`
    - Include Alpine.js: `<script defer src="https://cdn.jsdelivr.net/npm/alpinejs@3.x.x/dist/cdn.min.js"></script>`
    - Add global HTMX indicator (top-right spinner)
    - Add CSRF token injection script (for HTMX requests)
    - Create navigation bar (logo, links to dashboard/settings/account if logged in)
    - Create footer (Privacy Policy, Terms, Contact links)
    - Define content block: `{% block content %}{% endblock %}`
    - Add `[x-cloak] { display: none !important; }` style for Alpine.js

  - [ ] 1.5 Build Tailwind CSS and verify output
    - Run `npm run build:css`
    - Verify `app/static/css/tailwind.css` is created and minified
    - Check file size (<100KB for production)

- [ ] **2.0 Security Middleware & Session Management**
  - [ ] 2.1 Add security dependencies to requirements.txt
    - Add `starlette-csrf==2.1.0` (CSRF protection)
    - Add `slowapi==0.1.9` (rate limiting)
    - Add `itsdangerous==2.1.2` (session signing, if using cookie sessions)
    - Run `pip install -r requirements.txt`

  - [ ] 2.2 Create session management module (`app/core/session.py`)
    - Import `SessionMiddleware` from `starlette.middleware.sessions`
    - Create `get_session_user_id(request: Request) -> Optional[UUID]` function
    - Create `set_session_user_id(request: Request, user_id: UUID)` function
    - Create `clear_session(request: Request)` function
    - Create `regenerate_session(request: Request)` function (copy old session, clear, update)

  - [ ] 2.3 Create security middleware module (`app/core/middleware.py`)
    - Create `add_security_headers()` middleware function
      - Add `X-Content-Type-Options: nosniff`
      - Add `X-Frame-Options: DENY`
      - Add `X-XSS-Protection: 1; mode=block`
      - Add `Strict-Transport-Security: max-age=31536000; includeSubDomains` (production only)
      - Add Content-Security-Policy header (see PRD FR-8.3 for full policy)
      - Add `Referrer-Policy: strict-origin-when-cross-origin`
      - Add `Permissions-Policy: geolocation=(), microphone=(), camera=()`
    - Create `configure_csrf()` function to set up starlette-csrf middleware
    - Create `configure_rate_limiting()` function to set up slowapi limiter

  - [ ] 2.4 Update `app/main.py` to add all security middleware
    - Import session, CSRF, rate limiting middleware
    - Add `SessionMiddleware` with config:
      - `secret_key=settings.SECRET_KEY`
      - `max_age=86400` (24 hours)
      - `same_site="lax"`
      - `https_only=True` (production only, check `settings.ENVIRONMENT`)
      - `session_cookie="session"`
    - Add `CSRFMiddleware` from starlette-csrf
    - Add security headers middleware
    - Configure rate limiting with slowapi
    - Order matters: Session → CSRF → Rate Limiting → Security Headers

  - [ ] 2.5 Create authentication dependency (`app/modules/portal/dependencies.py`)
    - Create `get_current_user(request: Request, db: AsyncSession = Depends(get_db)) -> User` dependency
    - Check session for `user_id`
    - If not present, raise `HTTPException(status_code=401, detail="Not authenticated")`
    - Check session age (created_at field), expire if >24 hours
    - Query database for user by ID
    - If user not found, clear session and raise 401
    - Return user object

  - [ ] 2.6 Add environment variables to Railway/`.env`
    - `SESSION_SECRET_KEY` (generate: `python -c "import secrets; print(secrets.token_urlsafe(32))"`)
    - `POSTMARK_API_KEY` (from Postmark account)
    - `FROM_EMAIL=noreply@inboxjanitor.com`
    - `APP_URL=https://inbox-janitor-production-03fc.up.railway.app` (Railway subdomain for now)

- [ ] **3.0 Landing Page & OAuth Flow Enhancement**
  - [ ] 3.1 Create landing page template (`app/templates/landing.html`)
    - Extend `base.html`
    - Hero section:
      - Headline: "Keep Your Inbox Clean, Automatically" (text-4xl font-bold text-gray-900)
      - Subheadline: "Inbox Janitor quietly moves promotional emails..." (text-xl text-gray-600)
      - Primary CTA: Large "Connect Your Gmail" button (bg-blue-600 hover:bg-blue-700, min-h-[60px])
      - Trust signal below button: "Your emails stay private. We never read or store full email content."
    - How It Works section (3 steps with icons/numbers)
    - Features section (checkmarks with benefits)
    - Pricing section (beta notice, $6/mo plan)
    - FAQ section (4-5 common questions)
    - Footer with Privacy Policy, Terms, Contact links
    - All text: max-w-2xl for readability, leading-relaxed line height

  - [ ] 3.2 Create landing page route in portal module (`app/modules/portal/routes.py`)
    - Create `router = APIRouter(tags=["portal"])`
    - `@router.get("/")` - Landing page
    - If user is logged in (check session), redirect to `/dashboard`
    - Otherwise, render `landing.html` template

  - [ ] 3.3 Update OAuth routes to use sessions (`app/modules/auth/routes.py`)
    - Import session utilities from `app.core.session`
    - In `/auth/google/login`: Store state token in session (not just Redis)
    - In `/auth/google/callback`:
      - After successful token exchange, call `regenerate_session(request)` (prevent session fixation)
      - Store `user_id` in session via `set_session_user_id(request, user.id)`
      - Store `created_at` timestamp in session
      - Redirect to `/welcome` (new route)

  - [ ] 3.4 Create welcome page template (`app/templates/auth/welcome.html`)
    - Headline: "You're all set! 🎉"
    - Show connected email address (from session user)
    - Explanation of what happens next (3 bullet points)
    - Note about sandbox mode being active
    - Primary CTA: "Go to Settings" → `/dashboard`
    - Secondary CTA: "View Activity Log" → `/audit`

  - [ ] 3.5 Create welcome page route (`app/modules/portal/routes.py`)
    - `@router.get("/welcome")` - Requires authentication (Depends on get_current_user)
    - Fetch user and mailbox from database
    - Render `welcome.html` with user data

  - [ ] 3.6 Create OAuth error page template (`app/templates/auth/error.html`)
    - Message: "Gmail connection failed..."
    - Explanation of common reasons (user denied, link expired)
    - CTA: "Try Again" button → back to landing page
    - Support email: hello@inboxjanitor.com

  - [ ] 3.7 Create error page route and update OAuth callback error handling
    - `@router.get("/auth/error")` - Render error.html
    - In `/auth/google/callback`, catch exceptions and redirect to `/auth/error?reason=...`

  - [ ] 3.8 Mount portal router in main app (`app/main.py`)
    - Import `from app.modules.portal.routes import router as portal_router`
    - `app.include_router(portal_router)` (no prefix, serves from root)

- [ ] **4.0 Settings Dashboard & Portal Module**
  - [ ] 4.1 Create settings form models (`app/modules/portal/forms.py`)
    - `SettingsUpdate(BaseModel)`:
      - `confidence_auto_threshold: float = Field(ge=0.5, le=1.0)`
      - `confidence_review_threshold: float = Field(ge=0.5, le=1.0)`
      - `digest_schedule: str = Field(pattern="^(daily|weekly|off)$")`
      - `action_mode_enabled: bool`
      - `auto_trash_promotions: bool`
      - `auto_trash_social: bool`
      - `keep_receipts: bool`
    - `BlockedSenderAdd(BaseModel)`:
      - `email_or_domain: str = Field(min_length=3, max_length=255)`
    - `AllowedDomainAdd(BaseModel)`:
      - `domain: str = Field(pattern="^[a-zA-Z0-9.-]+\\.[a-zA-Z]{2,}$")`

  - [ ] 4.2 Create dashboard template (`app/templates/portal/dashboard.html`)
    - Connected account section (show email, "Disconnect" button)
    - Action mode section:
      - Radio buttons (Alpine.js for toggle, HTMX for save)
      - Help icon (?) with tooltip explaining sandbox vs action mode
      - Warning banner if sandbox mode active
    - Confidence thresholds section:
      - Two range sliders (auto-trash, auto-archive)
      - Show current value next to slider (Alpine.js x-text)
      - Help icons with tooltips
    - Weekly digest section:
      - Checkbox "Send weekly digest"
      - Dropdown for schedule (daily/weekly/off)
      - Help icon with tooltip
    - Block & Allow lists section:
      - Input + "Add" button for blocked senders
      - List of current blocked senders with "×" remove button
      - Same for allowed domains
      - Help icons with tooltips
    - "Save Changes" button (manual save for thresholds)
    - Use HTMX for all updates:
      - Auto-save toggles: `hx-post="/api/settings/toggle" hx-swap="none" hx-indicator="#save-indicator"`
      - Manual save form: `hx-post="/api/settings/update" hx-target="#success-message"`
    - All help tooltips use Alpine.js dropdown pattern (see design research)

  - [ ] 4.3 Create dashboard route (`app/modules/portal/routes.py`)
    - `@router.get("/dashboard")` - Requires authentication
    - Fetch user settings from database
    - Fetch mailbox info (email address, is_active)
    - Render `dashboard.html` with settings data and CSRF token

  - [ ] 4.4 Create settings update endpoints
    - `@router.post("/api/settings/update")` - Manual save (thresholds)
      - Rate limit: `@limiter.limit("30/minute")`
      - Validate with `SettingsUpdate` Pydantic model
      - Check CSRF token (starlette-csrf auto-validates)
      - Update user_settings in database
      - Return HTMX response: `<p class='text-green-600'>✓ Settings saved</p>`
    - `@router.post("/api/settings/toggle")` - Auto-save toggles
      - Rate limit: `@limiter.limit("30/minute")`
      - Accept single field updates (action_mode_enabled, auto_trash_promotions, etc.)
      - Update database immediately
      - Return empty 200 response (HTMX `hx-swap="none"`)
    - `@router.post("/api/settings/blocked-senders/add")` - Add blocked sender
      - Validate with `BlockedSenderAdd` model
      - Append to `user_settings.blocked_senders` array
      - Return HTMX response with updated list item
    - `@router.delete("/api/settings/blocked-senders/{sender}")` - Remove blocked sender
      - Remove from array, update database
      - Return 204 No Content

  - [ ] 4.5 Create account page template (`app/templates/portal/account.html`)
    - User info section (email, account created date)
    - Current plan section: "Beta (Free)" badge
    - Billing section (placeholder):
      - "You're in our beta program" message
      - "Add Payment Method" button (disabled for now)
      - Note: "Billing will be enabled before public launch"
    - Data export section:
      - "Download My Data" button
      - Explanation: "Exports audit log as CSV"
    - Account deletion section (bottom, red):
      - "Delete My Account" button (red, prominent warning)
      - Confirmation modal required (Alpine.js)

  - [ ] 4.6 Create account page route and endpoints
    - `@router.get("/account")` - Requires authentication
      - Fetch user, mailbox, settings
      - Render `account.html`
    - `@router.get("/api/account/export")` - Export data as CSV
      - Query email_actions for user's mailbox
      - Generate CSV with columns: timestamp, from, subject, action, confidence
      - Return as downloadable file: `Response(content=csv_data, media_type="text/csv", headers={"Content-Disposition": "attachment; filename=inbox-janitor-data.csv"})`
    - `@router.post("/api/account/delete")` - Delete account
      - Show confirmation modal (requires typing email address)
      - Mark user as deleted, revoke Gmail tokens
      - Schedule data deletion job (Celery task, 7-day delay)
      - Clear session, redirect to landing page with message

  - [ ] 4.7 Create audit log template (`app/templates/portal/audit.html`)
    - Page title: "Recent Activity"
    - Subtitle: "Showing actions from the last 30 days"
    - Table with columns: Date, Sender, Subject, Action (badge)
    - Pagination controls (Previous/Next, page number)
    - Click row to show details modal (HTMX loads modal content)
    - Details modal shows:
      - Full sender, subject, snippet
      - Classification reason
      - Confidence score
      - Timestamp
      - "Undo" button (disabled with message "Coming in Week 2")

  - [ ] 4.8 Create audit log route and endpoints
    - `@router.get("/audit")` - Requires authentication
      - Query `email_actions` table for user's mailbox
      - Filter: `created_at >= now() - 30 days`
      - Order by `created_at DESC`
      - Paginate: 50 items per page (offset-based for now)
      - Render `audit.html` with actions list
    - `@router.get("/api/audit/{action_id}")` - Get action details
      - Fetch single email_action by ID
      - Verify belongs to current user's mailbox
      - Return HTML fragment for modal content (HTMX target)

- [ ] **5.0 Email Templates & Postmark Integration**
  - [ ] 5.1 Create email service module (`app/modules/digest/email_service.py`)
    - Import `postmarker` library: `from postmarker.core import PostmarkClient`
    - Create `get_postmark_client() -> PostmarkClient`:
      - Initialize with `settings.POSTMARK_API_KEY`
      - Return client instance
    - Create `sanitize_email_header(value: str) -> str`:
      - Remove newlines, carriage returns, null bytes: `re.sub(r'[\r\n\0]', '', value)`
      - Strip whitespace, return sanitized value
    - Create `send_email(to: str, subject: str, html_body: str, text_body: str)`:
      - Sanitize `to` header
      - Use Postmark client to send email
      - Handle exceptions (log to Sentry, don't raise)
      - Return success boolean

  - [ ] 5.2 Create email template strings (`app/modules/digest/templates.py`)
    - Define `WELCOME_EMAIL_SUBJECT = "Welcome to Inbox Janitor! 🧹"`
    - Define `WELCOME_EMAIL_HTML` (simple HTML email):
      - Single column, max-width: 600px
      - Large readable font (16px+)
      - Greeting: "Hi there!"
      - 3-step explanation (numbered list)
      - "Sandbox mode" explanation in highlighted box
      - Blue button: "Go to Settings Dashboard" (links to app)
      - Footer with unsubscribe link (required by law)
    - Define `WELCOME_EMAIL_TEXT` (plain text version)
    - Define `WEEKLY_DIGEST_SUBJECT`, `WEEKLY_DIGEST_HTML`, `WEEKLY_DIGEST_TEXT`
    - Define `DAILY_SUMMARY_SUBJECT`, `DAILY_SUMMARY_HTML`, `DAILY_SUMMARY_TEXT`
    - Define `BACKLOG_ANALYSIS_SUBJECT`, `BACKLOG_ANALYSIS_HTML`, `BACKLOG_ANALYSIS_TEXT`

  - [ ] 5.3 Create email sending functions (`app/modules/digest/email_service.py`)
    - `async def send_welcome_email(user: User, db: AsyncSession)`:
      - Fetch user's mailbox email address
      - Render welcome email template (replace {{email}} placeholder)
      - Call `send_email()` with welcome template
      - Log event: "Welcome email sent to {email}"
    - `async def send_weekly_digest(user: User, digest_data: DigestData, db: AsyncSession)`:
      - Render digest template with data (actions count, review items)
      - Generate magic links for each action (JWT tokens)
      - Send email
    - `async def send_daily_summary(user: User, summary_data: SummaryData, db: AsyncSession)`:
      - Render summary template
      - Send email
    - `async def send_backlog_analysis(user: User, backlog_data: BacklogData, db: AsyncSession)`:
      - Render backlog template
      - Generate magic links for cleanup actions
      - Send email

  - [ ] 5.4 Create digest data models (`app/modules/digest/schemas.py`)
    - `DigestData(BaseModel)`:
      - `trash_count: int`
      - `archive_count: int`
      - `keep_count: int`
      - `review_items: List[ReviewItem]`
    - `ReviewItem(BaseModel)`:
      - `message_id: str`
      - `from_address: str`
      - `subject: str`
      - `action: str`
      - `confidence: float`
    - `SummaryData(BaseModel)`:
      - `trash_count: int`
      - `archive_count: int`
      - `keep_count: int`
    - `BacklogData(BaseModel)`:
      - `total_count: int`
      - `promotions_count: int`
      - `social_count: int`
      - `transactional_count: int`

  - [ ] 5.5 Trigger welcome email in OAuth callback (`app/modules/auth/routes.py`)
    - After successful OAuth and session creation
    - Import `send_welcome_email` from digest module
    - Call `await send_welcome_email(user, db)`
    - Don't block on email send (fire-and-forget or use Celery task)
    - If using Celery: Create `app/tasks/emails.py` with `send_welcome_email_task.delay(user_id)`

  - [ ] 5.6 Set up Postmark sender signature (manual step, document in README)
    - Sign up at postmark.com (free tier: 100 emails/month)
    - Create "Transactional" message stream
    - Add sender signature: `noreply@inboxjanitor.com`
    - Verify email or domain (DNS records)
    - Copy Server API Token to Railway environment variable `POSTMARK_API_KEY`

- [ ] **6.0 Mobile Responsiveness & Accessibility**
  - [ ] 6.1 Implement mobile-responsive navigation
    - Update `base.html` navigation:
      - Desktop (md:flex): Horizontal nav with links
      - Mobile (<768px): Hamburger menu icon
    - Add Alpine.js mobile menu toggle:
      - `x-data="{ mobileMenuOpen: false }"`
      - Hamburger button: `@click="mobileMenuOpen = !mobileMenuOpen"`
      - Mobile menu: `x-show="mobileMenuOpen"` with slide-in transition
      - Click-away to close: `@click.away="mobileMenuOpen = false"`

  - [ ] 6.2 Ensure all pages are mobile-responsive
    - Landing page: Single column on mobile, grid on desktop
    - Dashboard: Stack settings sections vertically on mobile
    - Account page: Full-width cards on mobile
    - Audit log: Horizontal scroll for table on mobile (or card layout)
    - Test on 375px width (iPhone SE size)
    - Touch targets minimum 44x44px (buttons, links)

  - [ ] 6.3 Add focus states to all interactive elements
    - Update button classes: `focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-blue-500 focus-visible:ring-offset-2`
    - Update link classes: `focus-visible:ring-2 focus-visible:ring-blue-500 focus-visible:rounded`
    - Test with keyboard navigation (Tab key)
    - Verify focus order is logical (top to bottom, left to right)

  - [ ] 6.4 Add ARIA labels and semantic HTML
    - Use semantic tags: `<nav>`, `<main>`, `<article>`, `<aside>`, `<footer>`
    - Help icons: `<button aria-label="Help">?</button>`
    - Form labels: `<label for="threshold-input">` with matching `id` on input
    - Range sliders: Add `aria-valuemin`, `aria-valuemax`, `aria-valuenow`
    - HTMX loading states: `aria-busy="true"` during requests
    - Live regions for dynamic updates: `<div aria-live="polite">` for toast notifications

  - [ ] 6.5 Ensure color contrast meets WCAG AA
    - Check all text/background combinations with contrast checker
    - Normal text: 4.5:1 minimum
    - Large text (18px+): 3:1 minimum
    - Interactive elements: 3:1 against background
    - Fix any failing combinations (adjust colors in Tailwind config)

  - [ ] 6.6 Add keyboard shortcuts for common actions (optional, nice-to-have)
    - Settings page: "Cmd+S" or "Ctrl+S" to save
    - Modals: "Esc" to close (already in Alpine.js modal pattern)
    - Navigation: "?" to show keyboard shortcuts help modal

- [ ] **7.0 Testing & Security Validation**
  - [ ] 7.1 Write CSRF protection tests (`tests/security/test_csrf.py`)
    - Test: POST without CSRF token returns 403
    - Test: POST with valid CSRF token succeeds
    - Test: CSRF token rotates after login
    - Use pytest fixtures for test client

  - [ ] 7.2 Write XSS prevention tests (`tests/security/test_xss.py`)
    - Test: Malicious script in email subject is escaped in HTML
    - Test: `<script>alert('XSS')</script>` rendered as `&lt;script&gt;...`
    - Test: HTMX responses sanitize user input
    - Verify Jinja2 auto-escaping is enabled

  - [ ] 7.3 Write session security tests (`tests/security/test_session.py`)
    - Test: Session expires after 24 hours
    - Test: Session regenerates after login (different session ID)
    - Test: Logout clears session
    - Test: Session cookies have HttpOnly, Secure, SameSite=Lax flags (in production)

  - [ ] 7.4 Write rate limiting tests (`tests/security/test_rate_limiting.py`)
    - Test: OAuth endpoint allows 5 requests/minute, blocks 6th
    - Test: Settings update allows 30 requests/minute
    - Test: Rate limit returns 429 status code

  - [ ] 7.5 Write security headers tests (`tests/security/test_headers.py`)
    - Test: All pages include X-Frame-Options: DENY
    - Test: All pages include X-Content-Type-Options: nosniff
    - Test: CSP header present with correct directives
    - Test: HSTS header present in production (not in dev)

  - [ ] 7.6 Write token exposure tests (`tests/security/test_token_exposure.py`)
    - Test: Dashboard HTML source contains no "ya29." (Google token prefix)
    - Test: Dashboard HTML contains no "access_token" string
    - Test: Dashboard HTML contains no "refresh_token" string
    - Test: Error pages don't expose tokens in messages

  - [ ] 7.7 Write dashboard functionality tests (`tests/portal/test_dashboard.py`)
    - Test: Unauthenticated user redirects to /auth/google/login
    - Test: Authenticated user sees dashboard
    - Test: Settings update changes database values
    - Test: Block/allow list add/remove works

  - [ ] 7.8 Write email service tests (`tests/digest/test_email_service.py`)
    - Test: Welcome email sends successfully
    - Test: Email headers are sanitized (no newlines)
    - Test: Email send failure logs to Sentry but doesn't raise
    - Mock Postmark API calls (use pytest-mock)

  - [ ] 7.9 Write end-to-end OAuth flow test (`tests/integration/test_oauth_flow.py`)
    - Test: Landing page → OAuth → Welcome page → Dashboard
    - Test: Session created after OAuth
    - Test: User redirected to dashboard if already logged in
    - Mock Google OAuth responses

  - [ ] 7.10 Write accessibility tests (`tests/accessibility/test_wcag.py`)
    - Test: All form inputs have associated labels
    - Test: All images have alt text (when added)
    - Test: Heading hierarchy is correct (h1 → h2 → h3)
    - Test: Focus states are visible (manual test)
    - Run axe-core or Pa11y for automated accessibility checks (optional)

  - [ ] 7.11 Manual testing checklist (document in `/docs/TESTING.md`)
    - [ ] Test on Chrome, Firefox, Safari
    - [ ] Test on mobile (real device or browser DevTools)
    - [ ] Test keyboard navigation (Tab, Enter, Esc)
    - [ ] Test screen reader (NVDA on Windows or VoiceOver on Mac)
    - [ ] Verify no tokens in browser DevTools (Network tab, Application → Cookies)
    - [ ] Test OAuth flow with real Gmail account
    - [ ] Test welcome email received within 5 minutes
    - [ ] Test settings persist after page refresh
    - [ ] Test logout clears session
    - [ ] Test session expires after 24 hours (mock time)

  - [ ] 7.12 Security audit with automated tools
    - Run `bandit -r app/` to check for Python security issues
    - Fix any HIGH or MEDIUM severity issues
    - Run `npm audit` to check for npm dependency vulnerabilities
    - Update any vulnerable packages
    - (Optional) Run OWASP ZAP scan against running app

---

## Implementation Notes

### Order of Implementation

**Phase 1 (Foundation):** Tasks 1.0, 2.0 - Set up infrastructure first
**Phase 2 (Core Pages):** Tasks 3.0, 4.0 - Build user-facing features
**Phase 3 (Email):** Task 5.0 - Integrate Postmark and templates
**Phase 4 (Polish):** Task 6.0 - Mobile and accessibility
**Phase 5 (Validation):** Task 7.0 - Testing and security audit

### Design System Reference

**Colors (60-30-10 rule):**
- 60% Neutral: `bg-gray-50`, `bg-white`, `bg-gray-100`
- 30% Structure: `bg-gray-800`, `text-gray-700`, `border-gray-200`
- 10% Accent: `bg-blue-600`, `bg-green-500`, `bg-red-500`

**Typography:**
- Font: Inter (400, 500, 600, 700 weights)
- Sizes: 16px body, 24px headings, 40px hero
- Line height: `leading-relaxed` (1.625)
- Max width: `max-w-2xl` for text blocks

**Spacing:**
- Base unit: 8px
- Section spacing: `space-y-8`
- Content spacing: `space-y-4`
- Card padding: `p-6`

**Components:**
- Buttons: `rounded-md`, `px-4 py-2`, `transition-all`
- Cards: `bg-white rounded-lg border shadow-sm`
- Inputs: `form-input` (from @tailwindcss/forms plugin)

### HTMX Patterns

**Auto-save toggle:**
```html
<button
  hx-post="/api/settings/toggle"
  hx-vals='{"field": "action_mode_enabled", "value": true}'
  hx-swap="none"
  hx-indicator="#save-indicator"
>
```

**Form with validation:**
```html
<form
  hx-post="/api/settings/update"
  hx-target="#success-message"
  hx-swap="innerHTML"
>
  <input name="threshold" type="range" />
  <button type="submit">Save</button>
</form>
<div id="success-message"></div>
```

**Modal content loading:**
```html
<button
  hx-get="/api/audit/123"
  hx-target="#modal-content"
  @click="modalOpen = true"
>
  View Details
</button>
```

### Alpine.js Patterns

**Modal:**
```html
<div x-data="{ open: false }">
  <button @click="open = true">Open Modal</button>
  <div x-show="open" @click.away="open = false" x-transition>
    <!-- Modal content -->
  </div>
</div>
```

**Tooltip:**
```html
<div x-data="{ tooltip: false }">
  <button @click="tooltip = !tooltip">?</button>
  <div x-show="tooltip" x-transition>Tooltip text</div>
</div>
```

**Dropdown menu:**
```html
<div x-data="{ open: false }" @click.away="open = false">
  <button @click="open = !open">Account ▼</button>
  <div x-show="open" x-transition>
    <a href="/settings">Settings</a>
    <a href="/logout">Logout</a>
  </div>
</div>
```

### Security Checklist

Before merging to main:
- [ ] All security tests passing
- [ ] CSRF protection enabled
- [ ] Session security configured (HttpOnly, Secure, SameSite)
- [ ] XSS prevention verified (Jinja2 auto-escaping)
- [ ] Rate limiting applied to all forms
- [ ] Security headers present
- [ ] No tokens in HTML source (manual check)
- [ ] No tokens in browser DevTools
- [ ] Sentry scrubbing configured

### Performance Checklist

Before deploying:
- [ ] Tailwind CSS purged and minified (<100KB)
- [ ] Static files cached (1-year cache headers)
- [ ] HTMX loaded from CDN (cached across sites)
- [ ] Images optimized (if any added)
- [ ] No N+1 queries (use SQLAlchemy eager loading)
- [ ] Lighthouse performance score >90

---

## Next Steps After Task Completion

1. **Create feature branch:** `git checkout -b feature/web-portal-foundation`
2. **Execute tasks sequentially** (get user approval after each major task)
3. **Run all tests** before creating PR
4. **Create pull request** with description from PRD
5. **Wait for Railway deployment** to preview URL
6. **Manual testing** on Railway preview
7. **User approves PR** after review
8. **Merge to main** → Production deployment
9. **Verify health endpoint:** https://inbox-janitor-production-03fc.up.railway.app/health
10. **Test OAuth flow** with real Gmail account
11. **Verify welcome email** received

---

**Task List Status:** ✅ Ready for Implementation
