# PRD: Web Portal Foundation + Email Templates

**PRD Number:** 0002
**Feature Name:** Web Portal Foundation + Email Templates
**Status:** Draft
**Created:** 2025-11-04
**Owner:** Sebastian Ames

---

## Introduction/Overview

This feature creates the customer-facing web portal and email communication system for Inbox Janitor, enabling users to discover the product, connect their Gmail accounts, manage settings, and receive email notifications. The portal prioritizes extreme simplicity for non-technical users (target: 70-year-old users comfortable with email but not apps) while implementing comprehensive security measures to protect OAuth tokens and user data.

**Problem it solves:** Currently, there is no way for customers to discover, sign up for, or configure Inbox Janitor. The backend email processing pipeline exists but has no user interface. Users need a simple, trustworthy way to connect Gmail and understand what the service does.

**Goal:** Build a secure, accessible web portal with landing page, OAuth flow, settings dashboard, and email templates that enable mom/sister (primary beta testers) to sign up and configure Inbox Janitor without assistance.

---

## Goals

1. **Accessible Landing Page:** Clear value proposition understandable by non-technical users (70+ years old)
2. **Frictionless OAuth:** One-click Gmail connection with clear trust signals
3. **Simple Settings Dashboard:** All configuration options with inline help ("?" icons)
4. **Email Communication:** Welcome, digest, and notification emails using Postmark templates
5. **Security-First Frontend:** CSRF protection, XSS prevention, session security, no token exposure
6. **Mobile-Friendly:** Responsive design works on phones (many users check email on mobile)
7. **Fast Time-to-Value:** User connects Gmail and receives welcome email within 60 seconds

---

## User Stories

### Primary Users: Mom & Sister (Beta Testers)

1. **As a Gmail user with 5,000+ emails**, I want to visit a simple website that explains what Inbox Janitor does in plain English, so I understand the benefit without technical jargon.

2. **As a privacy-conscious user**, I want to see clear trust signals (HTTPS, privacy policy, what data is accessed) before connecting my Gmail, so I feel safe authorizing access.

3. **As a 70-year-old user**, I want large, clear buttons and text, so I can navigate the site without reading glasses.

4. **As a new user**, I want to click "Connect Gmail" and complete OAuth in 3 clicks (Google login → select account → allow access), so I don't get lost in a complex signup flow.

5. **As a user who doesn't understand "confidence thresholds"**, I want a "?" help icon next to each setting that explains what it does in simple terms, so I can make informed choices.

6. **As a user nervous about automation**, I want to see sandbox mode is enabled by default with a clear explanation that no emails will be deleted until I opt-in, so I feel safe testing the service.

7. **As a user who prefers email**, I want to receive a welcome email after connecting Gmail that confirms everything is working and tells me what to expect next.

8. **As a weekly digest recipient**, I want the email to look professional but simple (like a personal email, not a marketing blast), so I trust it and read it.

9. **As a user checking the audit log**, I want to see a simple list of recent actions (what was archived/trashed and when) without technical jargon, so I can verify the service is working correctly.

10. **As a user who needs to adjust settings**, I want to access the dashboard on my phone while reading a digest email, so I can make quick changes without booting up my computer.

---

## Functional Requirements

### 1. Landing Page (Marketing Site)

**FR-1.1:** Create a landing page at `https://inbox-janitor-production-03fc.up.railway.app/` (Railway subdomain for testing) with the following sections:

#### Hero Section
- **Headline:** "Keep Your Inbox Clean, Automatically" (large, bold, 40px+ font)
- **Subheadline:** "Inbox Janitor quietly moves promotional emails out of your way so you can focus on messages from real people." (24px font, easy to read)
- **Primary CTA:** Large "Connect Your Gmail" button (60px height minimum, green/blue color, high contrast)
- **Trust Signal:** "Your emails stay private. We never read or store full email content." (small text below button)
- **Visual:** Simple illustration or screenshot showing cluttered inbox → clean inbox (optional for MVP)

#### How It Works Section
- **3-step process** with large icons/numbers:
  1. "Connect your Gmail account (takes 30 seconds)"
  2. "We analyze your emails using metadata only (no reading your messages)"
  3. "Promotional spam gets moved out of your way automatically"
- **Emphasis:** "You stay in control. Review changes weekly and undo anything."

#### Features Section
- **Simple bullet list** (large font, checkmarks):
  - ✓ Automatic cleanup of promotional emails
  - ✓ Keeps receipts, bills, and important mail safe
  - ✓ Weekly digest shows you what happened
  - ✓ Easy undo if we make a mistake
  - ✓ Works with Gmail (Microsoft 365 coming soon)

#### Pricing Section
- **Beta notice:** "Currently in beta. Free for our first 10 users. $6/month after launch."
- **Simple pricing card:**
  - Title: "Starter Plan"
  - Price: "$6/month"
  - Features: 1 Gmail account, Unlimited emails processed, 30-day action history
  - Note: "No credit card required during beta"

#### FAQ Section
- **Q: Is this safe?**
  - A: "Yes. We use Google's official security system (OAuth). We can only see email headers (sender, subject, date), not the full content of your messages. We never store or read your private emails."

- **Q: What if you delete something important?**
  - A: "We never permanently delete anything. Emails go to your Gmail trash (30-day recovery) or archive (always accessible). You can undo any action for 30 days."

- **Q: How is this different from Gmail's filters?**
  - A: "Gmail filters require manual setup for each sender. Inbox Janitor automatically learns what's promotional and what's personal, so you don't have to create dozens of rules."

- **Q: Can I stop using it anytime?**
  - A: "Yes. Disconnect your account anytime. All emails stay in your Gmail exactly where they are."

#### Footer
- **Links:** Privacy Policy, Terms of Service, Contact (email: hello@inboxjanitor.com)
- **Legal:** © 2025 Inbox Janitor. Built with privacy in mind.

**FR-1.2:** All text MUST be accessible (WCAG 2.1 AA minimum):
- Minimum font size: 16px for body text
- High contrast ratios: 4.5:1 for normal text, 3:1 for large text
- All interactive elements have focus states (keyboard navigation)

**FR-1.3:** Landing page MUST be mobile-responsive:
- Single column layout on mobile (<768px)
- Touch targets minimum 44x44px (Apple guidelines)
- No horizontal scrolling

**FR-1.4:** Landing page loads in <2 seconds (Lighthouse performance score >90):
- Inline critical CSS (no render-blocking)
- Tailwind CSS purged to remove unused classes
- Images optimized (<100KB total page weight)

### 2. OAuth Flow (Gmail Connection)

**FR-2.1:** Create route `GET /auth/google/login` that initiates OAuth flow:
- Generate CSRF state token (store in session)
- Redirect to Google OAuth consent screen
- Scopes requested:
  - `https://www.googleapis.com/auth/gmail.readonly` (read metadata only)
  - `https://www.googleapis.com/auth/gmail.modify` (archive/trash, but not delete)
  - `https://www.googleapis.com/auth/userinfo.email` (identify user)
- Display app name: "Inbox Janitor"
- Display logo (if configured in Google OAuth app)

**FR-2.2:** Create route `GET /auth/google/callback` that handles OAuth callback:
- Verify CSRF state token matches session
- Exchange authorization code for access + refresh tokens
- Decrypt and validate tokens
- Create or update user in database:
  - If email exists, update tokens
  - If new email, create user + mailbox record
- Encrypt tokens before database storage (use existing `encrypt_token()` from security.py)
- Create session for user (24-hour expiration)
- Redirect to `/welcome` page

**FR-2.3:** Create route `GET /welcome` (post-OAuth success page):
- **Headline:** "You're all set! 🎉"
- **Explanation:** "Your Gmail account (user@gmail.com) is now connected. Here's what happens next:"
  - "We're analyzing your inbox now (this takes a few minutes for large inboxes)"
  - "You'll get a welcome email shortly with next steps"
  - "For now, we're in sandbox mode – no emails will be moved until you're ready"
- **CTA:** "Go to Settings" button → `/dashboard`
- **Secondary CTA:** "View What We Found" → `/audit` (audit log)

**FR-2.4:** If OAuth fails (user denies access, expired state token):
- Redirect to `/auth/error` page
- **Message:** "Gmail connection failed. This usually happens if you clicked 'Deny' or the link expired."
- **CTA:** "Try Again" button → back to landing page
- **Support:** "Need help? Email us at hello@inboxjanitor.com"

**FR-2.5:** OAuth flow MUST implement security measures:
- CSRF protection (state token verification)
- HTTPS only (enforce via middleware)
- Session regeneration after successful login (prevent session fixation)
- No tokens in URL parameters or HTML (backend-only)

### 3. Settings Dashboard

**FR-3.1:** Create route `GET /dashboard` (requires authentication):
- If not logged in → redirect to `/auth/google/login`
- If session expired → redirect to `/auth/google/login` with message "Session expired, please log in again"

**FR-3.2:** Dashboard layout structure:
```
┌─────────────────────────────────────────┐
│  [Logo] Inbox Janitor     [Account ▼]  │  ← Top navigation
├─────────────────────────────────────────┤
│  Settings                               │  ← Page title
│                                         │
│  Connected Account:                     │
│  ✓ user@gmail.com (Active)              │
│  [Disconnect Account]                   │
│                                         │
│  ─────────────────────────────          │
│                                         │
│  Action Mode                       [?]  │  ← Help icon
│  ○ Sandbox (Review only, safe mode)    │
│  ○ Action (Archive/trash automatically)│
│                                         │
│  ⚠️ Sandbox mode is active. No emails  │  ← Warning banner
│     will be moved until you enable     │
│     Action Mode.                        │
│                                         │
│  ─────────────────────────────          │
│                                         │
│  Confidence Thresholds             [?]  │
│                                         │
│  Auto-Trash Threshold                   │
│  [====|====] 0.85                       │  ← Slider
│  Higher = only very obvious spam        │
│                                         │
│  Auto-Archive Threshold                 │
│  [====|====] 0.55                       │
│  Higher = fewer emails archived         │
│                                         │
│  ─────────────────────────────          │
│                                         │
│  Weekly Digest                     [?]  │
│  [x] Send weekly digest                 │
│  Schedule: [Every Sunday ▼] at [9 AM ▼]│
│                                         │
│  ─────────────────────────────          │
│                                         │
│  Block & Allow Lists               [?]  │
│                                         │
│  Always Trash (blocked):                │
│  [newsletter@spam.com            ] [+]  │
│  • marketing@oldnavy.com         [×]    │
│                                         │
│  Always Keep (allowed):                 │
│  [@work.com                      ] [+]  │
│  • noreply@bankofamerica.com     [×]    │
│                                         │
│  ─────────────────────────────          │
│                                         │
│  [Save Changes]                         │  ← Primary action
└─────────────────────────────────────────┘
```

**FR-3.3:** Each setting MUST have help tooltips (triggered by "?" icon):

- **Action Mode [?]:**
  - Tooltip: "Sandbox mode logs what we *would* do without actually moving emails. This lets you review our decisions safely. Action mode moves emails automatically (you can still undo for 30 days)."

- **Auto-Trash Threshold [?]:**
  - Tooltip: "This controls how confident we must be before moving an email to trash. Higher values (0.90+) mean only obvious spam gets trashed. Lower values (0.70-0.85) are more aggressive. We recommend starting at 0.85."

- **Auto-Archive Threshold [?]:**
  - Tooltip: "Emails between this value and the trash threshold get archived (out of inbox but not deleted). This is good for receipts, newsletters you might want later, etc."

- **Weekly Digest [?]:**
  - Tooltip: "We'll send you a summary every week showing what we moved, what we're unsure about, and quick links to undo anything."

- **Block & Allow Lists [?]:**
  - Tooltip: "Block list: Always trash emails from these senders/domains. Allow list: Always keep emails from these senders/domains, even if they look promotional."

**FR-3.4:** Settings form submission (`POST /settings/update`):
- Use HTMX for inline updates (no full page reload)
- Validate all inputs with Pydantic models:
  - `confidence_auto_threshold`: 0.5-1.0
  - `confidence_review_threshold`: 0.5-1.0
  - `digest_schedule`: enum('daily', 'weekly', 'off')
  - `action_mode_enabled`: boolean
  - `blocked_senders`: list of email/domain strings
  - `allowed_domains`: list of domain strings
- On success: Show green toast "Settings saved ✓" (HTMX response)
- On error: Show red toast with error message
- CSRF token required (validated server-side)

**FR-3.5:** "Disconnect Account" button behavior:
- Show confirmation modal: "Are you sure? This will stop email processing and delete all data within 7 days."
- If confirmed: Mark mailbox as `is_active=false`, revoke Gmail tokens, log out user
- Redirect to landing page with message "Account disconnected successfully"

### 4. Account Page

**FR-4.1:** Create route `GET /account` (requires authentication):
- Show user information:
  - Email address
  - Account created date
  - Current plan: "Beta (Free)" or "Starter ($6/mo)"
  - Billing status: "Active" or "No payment method"

**FR-4.2:** Billing section (placeholder for now):
- If beta user: "You're in our beta program. No payment required yet!"
- CTA: "Add Payment Method" button (disabled for now, will integrate Stripe in Week 2-3)
- Note: "Billing will be enabled before public launch. We'll notify you via email."

**FR-4.3:** Data export:
- Button: "Download My Data" (exports audit log as CSV)
- Generates CSV file with columns: timestamp, message_id, from_address, subject, action, confidence
- Downloads immediately (no background job for MVP)

**FR-4.4:** Account deletion:
- Button: "Delete My Account" (red, bottom of page)
- Shows confirmation modal with scary text: "⚠️ This will permanently delete all your data and disconnect your Gmail. You cannot undo this."
- Requires typing email address to confirm
- On confirm: Mark user as deleted, revoke tokens, schedule data deletion job (7-day delay)
- Redirect to landing page with message "Account deleted. Data will be permanently removed in 7 days."

### 5. Audit Log Viewer (Simple)

**FR-5.1:** Create route `GET /audit` (requires authentication):
- Show last 30 days of email actions
- Pagination: 50 items per page
- No search or filtering (defer to V1)

**FR-5.2:** Audit log table structure:
```
┌────────────────────────────────────────────────────────────┐
│  Recent Activity                                           │
│                                                            │
│  Showing actions from the last 30 days                    │
│                                                            │
│  ┌──────────────────────────────────────────────────────┐ │
│  │ Date       Sender           Subject            Action│ │
│  ├──────────────────────────────────────────────────────┤ │
│  │ Nov 3, 2PM Old Navy         50% off sale      Trash │ │
│  │ Nov 3, 1PM Amazon           Order shipped     Keep  │ │
│  │ Nov 2, 9AM LinkedIn         Weekly digest     Archive│ │
│  │ ...                                                  │ │
│  └──────────────────────────────────────────────────────┘ │
│                                                            │
│  [← Previous]  Page 1 of 5  [Next →]                      │
└────────────────────────────────────────────────────────────┘
```

**FR-5.3:** Table columns:
- **Date:** Human-readable relative time ("2 hours ago", "Nov 3 at 2:00 PM")
- **Sender:** From address (truncate if >30 chars, show full on hover)
- **Subject:** Email subject (truncate if >50 chars, show full on hover)
- **Action:** Badge with color coding:
  - "Trash" (red badge)
  - "Archive" (yellow badge)
  - "Keep" (green badge)
  - "Review" (gray badge)

**FR-5.4:** Click row to show details modal:
- Full sender email + name
- Full subject line
- First 200 chars of email (snippet)
- Classification reason ("CATEGORY_PROMOTIONS + List-Unsubscribe header")
- Confidence score (0.87)
- Timestamp (full datetime)
- **Undo button** (if action was trash/archive and within 30-day window)

**FR-5.5:** "Undo" button behavior (placeholder for now):
- Show toast: "Undo is coming in Week 2 after action mode is enabled"
- Button disabled for now (no Gmail API actions implemented yet)

### 6. Email Templates (Postmark Integration)

**FR-6.1:** Set up Postmark account:
- Sign up at postmark.com
- Create "Transactional" message stream
- Add sender signature: `noreply@inboxjanitor.com` (verify DNS)
- Generate API token (Server Token)
- Add `POSTMARK_API_KEY` to Railway environment variables

**FR-6.2:** Create email template models in database (optional, or hardcode for MVP):
- If hardcoded: Store templates in `app/modules/digest/templates/`
- If database: Create `email_templates` table with fields: `template_id`, `name`, `subject`, `html_body`, `text_body`

**FR-6.3:** Create welcome email template:
- **Trigger:** Sent immediately after successful OAuth (in callback handler)
- **From:** Inbox Janitor <noreply@inboxjanitor.com>
- **Subject:** "Welcome to Inbox Janitor! 🧹"
- **Body (text version):**
  ```
  Hi there!

  Your Gmail account (user@gmail.com) is now connected to Inbox Janitor.

  Here's what happens next:

  1. We're analyzing your inbox right now (this may take a few minutes if you have thousands of emails)

  2. We'll classify each email as:
     • Trash (promotional spam)
     • Archive (receipts, newsletters you might want later)
     • Keep (important messages)

  3. For now, we're in SANDBOX MODE. This means we're logging what we *would* do, but not actually moving any emails. You can review our decisions and enable "Action Mode" when you're comfortable.

  You'll receive your first weekly digest on Sunday at 9 AM with a summary of what we found.

  Questions? Just reply to this email.

  – Inbox Janitor

  ---
  Manage your settings: https://inbox-janitor-production-03fc.up.railway.app/dashboard
  ```

- **Body (HTML version):**
  - Simple HTML email (no fancy designs, looks like personal email)
  - Single column, large readable font
  - Green checkmarks for the 3-step process
  - Blue button "Go to Settings Dashboard"
  - Footer with unsubscribe link (required by law, even though transactional)

**FR-6.4:** Create weekly digest email template:
- **Trigger:** Celery beat task (Sundays at 9 AM user timezone, hardcode UTC for MVP)
- **From:** Inbox Janitor <noreply@inboxjanitor.com>
- **Subject:** "Your Inbox Janitor Weekly Digest"
- **Body structure:**
  ```
  Hi user@gmail.com,

  Here's what Inbox Janitor did this week:

  📊 Summary
  • 47 emails moved to trash (promotional spam)
  • 12 emails archived (receipts, newsletters)
  • 3 emails kept (important messages)

  🤔 We're Not Sure About These (Review Mode)

  [Email 1]
  From: newsletter@company.com
  Subject: Monthly Update - November 2025
  Our guess: Archive (confidence: 62%)
  [Keep It] [Trash It] [Archive It]

  [Email 2]
  From: notifications@linkedin.com
  Subject: You appeared in 5 searches this week
  Our guess: Trash (confidence: 78%)
  [Keep It] [Trash It]

  ⚙️ Quick Actions
  • [View Full Activity Log]
  • [Adjust Settings]
  • [Pause Inbox Janitor]

  Questions? Just reply to this email.

  – Inbox Janitor
  ```

- **Magic links:** Each action button is a magic link with JWT token:
  - Format: `https://app.inboxjanitor.com/a/{jwt_token}`
  - JWT contains: `user_id`, `action` (undo_message, keep_sender, etc.), `exp` (24-hour)
  - Clicking link performs action + redirects to confirmation page

**FR-6.5:** Create action receipt email (daily summary):
- **Trigger:** Celery beat task (daily at 8 AM user timezone if action mode enabled)
- **From:** Inbox Janitor <noreply@inboxjanitor.com>
- **Subject:** "Inbox Janitor Daily Summary"
- **Body:**
  ```
  Hi user@gmail.com,

  Yesterday, Inbox Janitor processed 23 new emails:

  • 15 moved to trash (promotional spam)
  • 5 archived (receipts, newsletters)
  • 3 kept in inbox (important messages)

  [View Details] [Undo Last Action]

  – Inbox Janitor
  ```

**FR-6.6:** Create backlog cleanup email:
- **Trigger:** User clicks "Clean Up Backlog" button (Week 3 feature, template ready now)
- **From:** Inbox Janitor <noreply@inboxjanitor.com>
- **Subject:** "Your Backlog Analysis is Ready"
- **Body:**
  ```
  Hi user@gmail.com,

  We analyzed your inbox and found:

  📦 6,247 old emails (older than 6 months)

  Breakdown by category:
  • 4,512 promotional emails (likely safe to trash)
  • 1,203 social notifications (LinkedIn, Facebook, etc.)
  • 532 transactional emails (receipts, confirmations)

  We can help you clean these up in batches. Here's what we recommend:

  [Clean Up Promotions (4,512 emails)] ← Magic link
  [Clean Up Social (1,203 emails)]
  [Leave Everything As-Is]

  This will take about 45 minutes and we'll send progress updates.

  Important: We'll never touch:
  • Starred emails
  • Emails from people in your contacts
  • Anything with keywords like "invoice", "receipt", "job", "medical", etc.

  – Inbox Janitor
  ```

**FR-6.7:** Email sending service module:
- Create `app/modules/digest/email_service.py` with functions:
  - `send_welcome_email(user: User)`
  - `send_weekly_digest(user: User, digest_data: DigestData)`
  - `send_daily_summary(user: User, summary_data: SummaryData)`
  - `send_backlog_analysis(user: User, backlog_data: BacklogData)`
- Use Postmark API client library: `pip install postmarker`
- All emails MUST sanitize headers (remove newlines, see FR-6.8)

**FR-6.8:** Email security measures:
- Sanitize all user-controlled fields (user.display_name, subject lines) to prevent email injection
- Use regex to remove `\r`, `\n`, `\0` from headers
- Postmark templates automatically escape HTML (XSS protection)
- Include unsubscribe link in footer (legal requirement, even for transactional)

### 7. Navigation & Layout

**FR-7.1:** Create base template `app/templates/base.html`:
- Top navigation bar:
  - Left: Logo + "Inbox Janitor" text (links to `/` if logged out, `/dashboard` if logged in)
  - Right:
    - If logged out: "Sign In" button → `/auth/google/login`
    - If logged in: User avatar (Gmail profile pic or initials) + dropdown menu
      - "Settings" → `/dashboard`
      - "Account" → `/account`
      - "Activity Log" → `/audit`
      - "Sign Out" → `/auth/logout`

**FR-7.2:** Responsive navigation:
- Desktop (>768px): Full horizontal nav
- Mobile (<768px): Hamburger menu icon → slide-out drawer

**FR-7.3:** Footer (appears on all pages):
- Links: Privacy Policy | Terms of Service | Contact
- Copyright: "© 2025 Inbox Janitor"

**FR-7.4:** Loading states:
- Show spinner overlay when HTMX requests are in progress
- Disable buttons during submission (prevent double-clicks)

**FR-7.5:** Error states:
- 404 page: "Page not found. [Go Home]"
- 500 page: "Something went wrong. We've been notified. [Go Home]"
- Offline page: "You're offline. Check your internet connection."

### 8. Security Requirements (CRITICAL)

**FR-8.1:** CSRF Protection:
- Install `starlette-csrf` middleware
- All POST/PUT/DELETE forms include CSRF token (hidden input + HTMX header)
- Server validates CSRF token on all state-changing endpoints
- CSRF token rotates on login (prevent token fixation)

**FR-8.2:** Session Security:
- Sessions stored server-side (Redis-backed via starlette-redis)
- Session cookies:
  - `HttpOnly=True` (JavaScript cannot access)
  - `Secure=True` (HTTPS only in production)
  - `SameSite=Lax` (CSRF protection)
  - Max age: 24 hours (force re-login daily)
- Session ID regenerated after login (prevent session fixation)

**FR-8.3:** XSS Prevention:
- Jinja2 auto-escaping ENABLED globally (verify in `main.py`)
- NEVER use `| safe` filter on user-controlled data
- HTMX responses sanitize user input with `markupsafe.escape()`
- Content-Security-Policy header:
  ```
  default-src 'self';
  script-src 'self' 'unsafe-inline' https://unpkg.com;
  style-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net;
  img-src 'self' data:;
  connect-src 'self';
  frame-ancestors 'none';
  ```

**FR-8.4:** Security Headers:
- Middleware adds headers to ALL responses:
  ```python
  X-Content-Type-Options: nosniff
  X-Frame-Options: DENY
  X-XSS-Protection: 1; mode=block
  Strict-Transport-Security: max-age=31536000; includeSubDomains
  Referrer-Policy: strict-origin-when-cross-origin
  Permissions-Policy: geolocation=(), microphone=(), camera=()
  ```

**FR-8.5:** Rate Limiting:
- Install `slowapi` middleware
- Apply limits:
  - `/auth/google/login`: 5 requests/minute per IP
  - `/auth/google/callback`: 10 requests/minute per IP
  - `/settings/update`: 30 requests/minute per user
  - Landing page: No limit (public)

**FR-8.6:** OAuth Token Security:
- Tokens NEVER appear in:
  - HTML templates (backend-only)
  - JavaScript variables
  - URL parameters
  - Query strings
  - Form values (hidden or visible)
  - Error messages
  - Logs (Sentry scrubbing enabled)
- Tokens decrypted only in backend functions, immediately before Gmail API calls
- Tokens discarded from memory after use (no caching)

**FR-8.7:** Open Redirect Prevention:
- Whitelist allowed redirect URLs after OAuth:
  ```python
  ALLOWED_REDIRECTS = ['/dashboard', '/welcome', '/settings', '/audit']
  ```
- Any redirect parameter not in whitelist → default to `/dashboard`

**FR-8.8:** Mass Assignment Prevention:
- All form inputs validated with Pydantic models
- Extra fields automatically stripped (not saved to database)
- Test: Verify adding `is_admin=true` to settings form is ignored

**FR-8.9:** Clickjacking Prevention:
- `X-Frame-Options: DENY` header prevents embedding in iframes
- CSP `frame-ancestors 'none'` as backup

**FR-8.10:** Subdomain Takeover Prevention:
- Use A records (not CNAME) for `inboxjanitor.com` DNS
- Document Railway deployment name to prevent accidental deletion

### 9. Accessibility Requirements (WCAG 2.1 AA)

**FR-9.1:** Keyboard Navigation:
- All interactive elements focusable (tab order logical)
- Focus indicators visible (2px outline, high contrast)
- Skip to main content link (hidden until focused)
- Modal dialogs trap focus (ESC to close)

**FR-9.2:** Screen Reader Support:
- Semantic HTML (`<nav>`, `<main>`, `<article>`, `<button>`, not `<div onclick>`)
- ARIA labels on icon-only buttons ("?" help icons have `aria-label="Help"`)
- ARIA live regions for dynamic updates (HTMX responses announce changes)
- Form labels associated with inputs (`<label for="...">`)

**FR-9.3:** Visual Accessibility:
- Minimum font size: 16px body, 14px secondary text
- Line height: 1.5 for body text
- Color contrast ratios:
  - Normal text: 4.5:1 minimum
  - Large text (18px+): 3:1 minimum
  - Interactive elements: 3:1 against background
- Never rely on color alone (use icons + text for status)

**FR-9.4:** Text Readability:
- Short sentences (max 20 words)
- Short paragraphs (max 3-4 sentences)
- Avoid jargon (use "delete" not "expunge", "settings" not "configuration")
- Define technical terms on first use

**FR-9.5:** Responsive Text:
- Text remains readable when zoomed to 200% (no horizontal scroll)
- Touch targets minimum 44x44px (mobile)
- Adequate spacing between links (8px minimum)

### 10. Performance Requirements

**FR-10.1:** Page Load Performance:
- Landing page: <2 seconds (3G connection)
- Dashboard: <1 second (logged in, cached session)
- Lighthouse scores:
  - Performance: >90
  - Accessibility: 100
  - Best Practices: 100
  - SEO: >90

**FR-10.2:** Optimization Techniques:
- Tailwind CSS purged (remove unused classes, <50KB)
- Critical CSS inlined in `<head>` (no render blocking)
- HTMX + Alpine.js loaded from CDN (cached across sites)
- Images lazy-loaded (loading="lazy" attribute)
- No custom fonts (system fonts only for performance)

**FR-10.3:** Database Query Optimization:
- Settings page: 1 query (fetch user + settings in single join)
- Audit log: Pagination with cursor-based paging (faster than offset)
- No N+1 queries (use SQLAlchemy eager loading)

**FR-10.4:** Caching:
- Static assets (CSS, JS, images): 1-year cache headers
- HTML pages: No cache (always fresh for logged-in users)
- Session data: Redis-cached (no database query per request)

---

## Non-Goals (Out of Scope)

1. **Stripe Billing Integration:** Deferred to Week 2-3 (placeholder UI only for now)
2. **Advanced Audit Log Features:** No search, filtering, or CSV export in this PRD (defer to V1)
3. **Multi-Account Support:** Single Gmail account per user for MVP
4. **Custom Email Templates:** Users cannot edit email templates (admin-controlled only)
5. **Real-Time Notifications:** No WebSocket/SSE for live updates (refresh to see new data)
6. **Mobile Native App:** Web-only for MVP (responsive design sufficient)
7. **User Profile Customization:** No avatars, display names, or preferences beyond settings
8. **Team Features:** No shared accounts, admin dashboards, or organization plans
9. **Advanced Analytics:** No charts, graphs, or trend analysis (simple counts only)
10. **Internationalization:** English only (no i18n for MVP)
11. **Dark Mode:** Light theme only (defer to V1 based on user feedback)
12. **Undo Implementation:** Undo buttons present but disabled (action mode comes in Week 2)

---

## Design Considerations

### Visual Design System

**Typography:**
- System font stack: `-apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif`
- Font sizes: 40px (hero), 24px (subheading), 18px (body), 16px (small text)
- Font weights: 700 (bold), 600 (semi-bold), 400 (normal)

**Colors (Simple Palette):**
- Primary: Blue (`#2563EB`) - CTAs, links
- Success: Green (`#10B981`) - Positive actions, success messages
- Warning: Yellow (`#F59E0B`) - Archive actions, warnings
- Danger: Red (`#EF4444`) - Trash actions, delete account
- Neutral: Gray scale (`#111827` → `#F9FAFB`)

**Components:**
- Buttons: Rounded corners (8px), padding (16px 24px), large touch targets
- Inputs: Border on focus (blue), clear labels above input
- Cards: Subtle shadow, white background, 12px border-radius
- Badges: Small rounded pills (trash=red, archive=yellow, keep=green)

**Spacing:**
- Base unit: 8px
- Common values: 8px, 16px, 24px, 32px, 48px
- Page margins: 24px mobile, 48px desktop

### User Flow Diagrams

**New User Journey:**
```
Landing Page → Click "Connect Gmail" → Google OAuth (3 clicks) →
Welcome Page → Go to Settings → Review Settings (sandbox mode) →
Close Browser → Receive Welcome Email → Click "View Dashboard" →
(Week later) → Receive Weekly Digest → Click "Enable Action Mode" → Done
```

**Returning User Journey:**
```
Click Email Link (digest) → Auto-login via magic link →
Perform Action (undo/adjust) → Close Browser
```

### Mobile Wireframes

**Landing Page (Mobile):**
```
┌─────────────────────┐
│  🧹 Inbox Janitor   │
│                     │
│  Keep Your Inbox    │
│  Clean,             │
│  Automatically      │
│                     │
│  Quietly moves      │
│  promotional emails │
│  out of your way    │
│                     │
│  [Connect Gmail]    │ ← Large button
│                     │
│  How It Works       │
│  1️⃣ Connect Gmail   │
│  2️⃣ We analyze      │
│  3️⃣ Spam moves      │
│                     │
│  Features ✓         │
│  • Auto cleanup     │
│  • Safe keeps       │
│  • Weekly digest    │
│                     │
└─────────────────────┘
```

**Dashboard (Mobile):**
```
┌─────────────────────┐
│ ☰  Inbox Janitor  👤│ ← Hamburger + Avatar
├─────────────────────┤
│  Settings           │
│                     │
│  ✓ user@gmail.com   │
│                     │
│  Action Mode    [?] │
│  ○ Sandbox          │
│  ○ Action           │
│                     │
│  ⚠️ Sandbox mode    │
│                     │
│  Thresholds     [?] │
│  [====|===] 0.85    │
│                     │
│  [Save]             │
└─────────────────────┘
```

### Help Icon Tooltip Behavior

**Desktop:**
- Hover "?" icon → Tooltip appears next to icon
- Click "?" icon → Tooltip toggles (stays open)
- Click outside or ESC → Tooltip closes

**Mobile:**
- Tap "?" icon → Tooltip appears below icon
- Tap "?" again → Tooltip closes
- Tap outside → Tooltip closes

**Tooltip Styling:**
- White background, subtle shadow
- Max width: 300px
- Arrow pointing to "?" icon
- Close button (×) in top-right

---

## Technical Considerations

### Tech Stack

**Backend:**
- FastAPI (existing)
- Jinja2 templates (built into FastAPI)
- SQLAlchemy ORM (existing)
- Alembic migrations (existing)

**Frontend:**
- HTMX 1.9+ (interactive updates without JavaScript frameworks)
- Alpine.js 3+ (small JS sprinkles for dropdowns, modals)
- Tailwind CSS 3+ (utility-first styling)
- No React/Vue (overkill for this use case)

**Email:**
- Postmark API (transactional email service)
- `postmarker` Python library

**Security:**
- `starlette-csrf` (CSRF protection)
- `slowapi` (rate limiting)
- `python-multipart` (form parsing)
- `starlette-redis` or `SessionMiddleware` (session management)

### Module Structure

```
app/
├── api/
│   ├── auth.py          # OAuth routes
│   ├── portal.py        # Dashboard, settings, account routes
│   └── webhooks.py      # Existing Gmail webhook
├── modules/
│   ├── auth/            # Existing OAuth module
│   ├── portal/          # NEW: Web portal module
│   │   ├── __init__.py
│   │   ├── routes.py    # FastAPI routers for /dashboard, /settings, etc.
│   │   ├── forms.py     # Pydantic models for form validation
│   │   └── dependencies.py  # get_current_user() dependency
│   ├── digest/          # NEW: Email templates module
│   │   ├── __init__.py
│   │   ├── email_service.py  # Postmark integration
│   │   ├── templates/   # Email template strings
│   │   └── schemas.py   # DigestData, SummaryData models
│   └── ingest/          # Existing webhook module
├── templates/           # NEW: Jinja2 HTML templates
│   ├── base.html        # Base layout with nav
│   ├── landing.html     # Marketing landing page
│   ├── auth/
│   │   ├── welcome.html
│   │   └── error.html
│   ├── portal/
│   │   ├── dashboard.html  # Settings page
│   │   ├── account.html
│   │   └── audit.html
│   └── components/      # Reusable components (modals, tooltips)
│       ├── modal.html
│       └── tooltip.html
├── static/              # NEW: Static assets
│   ├── css/
│   │   └── tailwind.css  # Compiled Tailwind (purged)
│   ├── js/
│   │   └── app.js       # Minimal custom JS (analytics, etc.)
│   └── images/
│       └── logo.svg
├── core/
│   ├── security.py      # Security headers, CSRF, session config
│   └── config.py        # Environment variables
└── main.py              # FastAPI app with middleware
```

### Environment Variables

**New variables to add:**
```bash
# Email Service
POSTMARK_API_KEY=...
FROM_EMAIL=noreply@inboxjanitor.com

# Session Management
SESSION_SECRET_KEY=...  # Different from JWT SECRET_KEY
REDIS_URL=...  # For session storage (optional, can use cookie-based)

# Domain
APP_URL=https://inbox-janitor-production-03fc.up.railway.app  # Will change to inboxjanitor.com

# Security
ENVIRONMENT=production  # Enables HTTPS enforcement, secure cookies
```

### Database Schema Changes

**New table: `user_settings`** (if doesn't exist, check existing schema)
```sql
CREATE TABLE user_settings (
    user_id UUID PRIMARY KEY REFERENCES users(id) ON DELETE CASCADE,
    confidence_auto_threshold FLOAT DEFAULT 0.85,
    confidence_review_threshold FLOAT DEFAULT 0.55,
    digest_schedule TEXT DEFAULT 'weekly',  -- 'daily' | 'weekly' | 'off'
    digest_day_of_week INT DEFAULT 0,  -- 0=Sunday
    digest_hour INT DEFAULT 9,  -- 9 AM
    action_mode_enabled BOOLEAN DEFAULT false,
    auto_trash_promotions BOOLEAN DEFAULT true,
    auto_trash_social BOOLEAN DEFAULT true,
    keep_receipts BOOLEAN DEFAULT true,
    blocked_senders TEXT[] DEFAULT '{}',
    allowed_domains TEXT[] DEFAULT '{}',
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);
```

**Migration:** `003_user_settings_and_portal.py`
- Create `user_settings` table
- Add trigger to auto-update `updated_at` on row changes
- Create default settings for existing users

### Dependencies to Add

```txt
# requirements.txt additions

# Frontend
python-multipart==0.0.6  # Form parsing

# Security
starlette-csrf==2.1.0    # CSRF protection
slowapi==0.1.9           # Rate limiting

# Email
postmarker==1.0          # Postmark API client

# Session Management (pick one)
starlette-redis==0.2.0   # Redis-backed sessions (recommended)
# OR use built-in SessionMiddleware (cookie-based, simpler)

# Utilities
python-dateutil==2.8.2   # Date parsing for digests
```

### Railway Deployment

**Current services:**
1. Web service (FastAPI)
2. Worker service (Celery)
3. PostgreSQL database
4. Redis cache

**No new services needed.** Web service serves both API + HTML.

**Deployment steps:**
1. Build frontend assets (compile Tailwind CSS)
2. Push to feature branch
3. Create pull request
4. Railway auto-deploys preview
5. Test on preview URL
6. Merge to main → production deployment
7. Verify health endpoint: `/health`
8. Manually test OAuth flow
9. (Later) Point `inboxjanitor.com` A record to Railway IP

### DNS Configuration (For Later)

**When ready to use `inboxjanitor.com`:**
```
# DNS Records (Namecheap/Cloudflare/etc.)
inboxjanitor.com.        A     <Railway IP>
www.inboxjanitor.com.    A     <Railway IP>
```

**Email DNS (for Postmark):**
```
# SPF Record
inboxjanitor.com.  TXT  "v=spf1 include:spf.mtasv.net ~all"

# DKIM Record (provided by Postmark after domain verification)
pm._domainkey.inboxjanitor.com.  CNAME  pm.mtasv.net

# Return-Path Domain
pm-bounces.inboxjanitor.com.  CNAME  pm.mtasv.net
```

---

## Success Metrics

### Quantitative Metrics

**User Onboarding:**
- ✅ 90%+ of users complete OAuth within 60 seconds of landing
- ✅ 100% of successful OAuth flows receive welcome email within 5 minutes
- ✅ Time-to-first-value: <3 minutes (landing → OAuth → welcome email)

**Accessibility:**
- ✅ Lighthouse accessibility score: 100
- ✅ Screen reader test: All interactive elements announced correctly
- ✅ Keyboard navigation test: Can complete full flow without mouse

**Performance:**
- ✅ Landing page loads in <2 seconds (3G connection)
- ✅ Dashboard loads in <1 second (logged in user)
- ✅ HTMX updates respond in <300ms (perceived instant)

**Security:**
- ✅ 0 tokens visible in HTML source (manual inspection)
- ✅ CSRF tokens present in all forms (automated test)
- ✅ Session expires after 24 hours (automated test)
- ✅ All security headers present (automated test)

**Email Deliverability:**
- ✅ Welcome email 99%+ delivery rate (Postmark metrics)
- ✅ Weekly digest <5% spam rate (Postmark spam score <5)
- ✅ 0 email injection vulnerabilities (automated test)

### Qualitative Metrics

**User Feedback (Mom & Sister):**
- ✅ "I understood what the service does without asking questions"
- ✅ "Connecting my Gmail felt safe and easy"
- ✅ "I could navigate the settings without help"
- ✅ "The help icons (?) explained things clearly"
- ✅ "The weekly digest email was easy to read and understand"

**Developer Experience:**
- ✅ Frontend code is maintainable (clear separation of concerns)
- ✅ Security patterns are consistent (no ad-hoc implementations)
- ✅ Templates are reusable (DRY principle)
- ✅ Railway deployment succeeds without manual intervention

---

## Open Questions

1. **Session Storage:**
   - Should we use Redis-backed sessions (more scalable) or cookie-based sessions (simpler)?
   - **Recommendation:** Cookie-based for MVP (built into Starlette), migrate to Redis at 100+ concurrent users

2. **Email Template Storage:**
   - Should email templates be hardcoded in Python strings or stored in database for easier editing?
   - **Recommendation:** Hardcoded for MVP (faster to implement), move to database if we need per-user customization

3. **Magic Link Token Format:**
   - JWT (self-contained, stateless) or random token (requires database lookup)?
   - **Recommendation:** JWT (simpler, no database queries), 24-hour expiration

4. **Landing Page Hosting:**
   - Same domain as app (`/` serves landing page) or separate static site (Vercel)?
   - **Recommendation:** Same domain (simpler deployment, no CORS issues)

5. **User Timezone Detection:**
   - Detect from browser (JavaScript) or ask user to select?
   - **Recommendation:** Hardcode UTC for MVP, add timezone selection in V1

6. **Help Tooltip Implementation:**
   - Alpine.js (client-side) or HTMX (server-side)?
   - **Recommendation:** Alpine.js (instant, no server round-trip)

7. **Audit Log Pagination:**
   - Offset-based (simple) or cursor-based (faster for large datasets)?
   - **Recommendation:** Offset-based for MVP (max 30 days = ~1000 rows), cursor-based in V1

---

## Next Steps

1. **Review this PRD** with user (Sebastian) for approval
2. **Research best practices** for accessible, senior-friendly web design (use research agent)
3. **Generate task list** using `@ai-dev-tasks/generate-tasks.md` skill
4. **Execute tasks** step-by-step with user review checkpoints
5. **Create feature branch:** `git checkout -b feature/web-portal-foundation`
6. **Security testing** before merge (run all security tests)
7. **Deploy to Railway** via pull request workflow
8. **Manual testing** with mom/sister on Railway subdomain
9. **(Later) Switch DNS** to point `inboxjanitor.com` to Railway

---

**PRD Status:** ✅ Ready for Review
