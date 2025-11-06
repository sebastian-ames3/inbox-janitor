# Task List: PRD 0004 - Action Execution Engine

**PRD Reference:** `0004-prd-action-execution-engine.md`
**Created:** 2025-11-05

---

## Current State Assessment

**Existing Infrastructure (Already Built):**
- ✅ Database models: `EmailAction`, `UserSettings`, `Mailbox`, `User`
- ✅ Classification models: `EmailMetadata`, `ClassificationResult`, `SafetyOverride`
- ✅ Safety rails: `app/modules/classifier/safety_rails.py` (exception keywords, starred, important, recent)
- ✅ Tier 1 classifier: `app/modules/classifier/tier1.py` (metadata-based classification)
- ✅ Classification signals: `app/modules/classifier/signals.py` (Gmail category, headers, etc.)
- ✅ Metadata extraction: `app/modules/ingest/metadata_extractor.py` (Gmail API parsing)
- ✅ Celery tasks: `app/tasks/classify.py` (classification task infrastructure)
- ✅ Session management: `app/core/session.py`
- ✅ OAuth tokens: Encrypted in database (Fernet)

**What Needs to Be Built (This PRD):**
- ❌ Gmail API email fetching (paginated list, filters, rate limiting)
- ❌ AI classification (Tier 2 - OpenAI GPT-4o-mini fallback)
- ❌ Action execution (trash, archive via Gmail API)
- ❌ Auto-labeling system (document type detection + Gmail label creation)
- ❌ Undo functionality (restore emails from trash/archive)
- ❌ Backlog cleanup (batch processing for thousands of old emails)
- ❌ Background job scheduler (Celery Beat polling)
- ❌ User settings UI (action mode toggle, thresholds, auto-labeling)
- ❌ Audit log UI (display email_actions, undo buttons)

---

## Relevant Files

### New Files to Create

**Gmail API Integration:**
- `app/modules/ingest/gmail_client.py` - Gmail API client (fetch emails, modify, trash)
- `app/modules/ingest/rate_limiter.py` - Rate limiting for Gmail API quota
- `tests/unit/test_gmail_client.py` - Unit tests for Gmail client
- `tests/unit/test_rate_limiter.py` - Unit tests for rate limiter

**AI Classification:**
- `app/modules/classifier/tier2_ai.py` - OpenAI GPT-4o-mini classifier
- `app/modules/classifier/openai_client.py` - OpenAI API client wrapper
- `tests/unit/test_tier2_ai.py` - Unit tests for AI classifier
- `tests/security/test_ai_no_body.py` - Security test (verify no full body sent to AI)

**Action Execution:**
- `app/modules/executor/actions.py` - Execute trash/archive actions via Gmail API
- `app/modules/executor/undo.py` - Undo action implementation
- `app/modules/executor/labels.py` - Gmail label creation/management
- `tests/unit/test_actions.py` - Unit tests for action execution
- `tests/safety/test_no_permanent_delete.py` - Safety test (verify no .delete() calls)

**Auto-Labeling:**
- `app/modules/executor/document_classifier.py` - Detect document type (receipt, invoice, etc.)
- `tests/unit/test_document_classifier.py` - Unit tests for document type detection

**Backlog Cleanup:**
- `app/modules/ingest/backlog_analyzer.py` - Analyze backlog (count by category/age)
- `app/tasks/backlog.py` - Celery task for batch backlog processing
- `tests/unit/test_backlog_analyzer.py` - Unit tests for backlog analyzer

**Background Jobs:**
- `app/tasks/process_emails.py` - Celery task for polling new emails
- `app/tasks/scheduler.py` - Celery Beat schedule configuration

**Web Portal UI:**
- `app/modules/portal/settings_routes.py` - Settings page routes (update thresholds, toggle action mode)
- `app/modules/portal/audit_routes.py` - Audit log page routes (view email_actions, undo)
- `app/templates/settings.html` - Settings page template
- `app/templates/audit.html` - Audit log page template
- `tests/e2e/settings.spec.js` - E2E tests for settings page
- `tests/e2e/audit.spec.js` - E2E tests for audit log page

**Database Migrations:**
- `alembic/versions/005_add_user_settings_backlog.py` - Add backlog cleanup settings to user_settings
- `alembic/versions/006_add_original_label_ids.py` - Add original_label_ids column to email_actions (for undo)

### Files to Modify

**Existing Files:**
- `app/models/user_settings.py` - Add `auto_label_archived_emails`, `backlog_cleanup_enabled`, `backlog_cleanup_age_days`
- `app/models/email_action.py` - Add `original_label_ids` column for undo
- `app/tasks/classify.py` - Integrate AI classification (Tier 2) after Tier 1
- `app/core/config.py` - Add `OPENAI_API_KEY`, Gmail API rate limit settings
- `app/main.py` - Register new portal routes (settings, audit)
- `CLAUDE.md` - Update with PRD 0004 completion status
- `CHANGELOG.md` - Document completion of action execution engine

---

## Tasks

- [ ] **1.0 Gmail API Integration - Email Fetching**
  - [ ] 1.1 Create `app/modules/ingest/gmail_client.py`:
    - Import Google API client libraries (`google-auth`, `google-api-python-client`)
    - Create `GmailClient` class with `__init__(mailbox: Mailbox)` constructor
    - Decrypt OAuth tokens using Fernet (from `mailbox.encrypted_access_token`)
    - Build Gmail API service using decrypted credentials
    - Implement `list_messages(query: str, max_results: int, page_token: str) -> dict` method
      - Use `users().messages().list()` API
      - Support query filters: `in:inbox category:promotions newer_than:7d`
      - Return `{'messages': [...], 'nextPageToken': '...'}`
    - Implement `get_message(message_id: str, format: str = 'metadata') -> dict` method
      - Use `users().messages().get()` API
      - Extract headers, labels, snippet, internalDate
      - NEVER fetch full body (format='metadata' only)
    - Add error handling for 401, 403, 429, 500/503 errors
    - Add logging for all API calls
  - [ ] 1.2 Create `app/modules/ingest/rate_limiter.py`:
    - Create `RateLimiter` class using Redis backend
    - Implement sliding window rate limiting (10 emails/min per user)
    - Track quota units: `messages.list()` = 5, `messages.get()` = 5, `messages.modify()` = 5
    - Implement `check_rate_limit(user_id: str, quota_units: int) -> bool` method
    - Implement `wait_for_rate_limit(user_id: str, quota_units: int)` method with exponential backoff
    - Add Redis key format: `rate_limit:{user_id}:{timestamp_window}`
  - [ ] 1.3 Integrate rate limiting into `GmailClient`:
    - Wrap all API calls with rate limiter
    - Implement exponential backoff for 429 (quota exceeded) errors: 1s, 2s, 4s, 8s, 16s max
    - Add retry logic (max 3 retries) for 500/503 server errors
    - Refresh OAuth token on 401 errors (call `refresh_access_token()`)
  - [ ] 1.4 Create `tests/unit/test_gmail_client.py`:
    - Mock Gmail API responses
    - Test `list_messages()` with pagination
    - Test `get_message()` with metadata format
    - Test error handling (401, 429, 500)
    - Test OAuth token refresh flow
  - [ ] 1.5 Create `tests/unit/test_rate_limiter.py`:
    - Mock Redis connection
    - Test rate limit enforcement (reject if over quota)
    - Test sliding window logic
    - Test exponential backoff
  - [ ] 1.6 Update `app/core/config.py`:
    - Add `GMAIL_API_RATE_LIMIT_PER_MIN = 10`
    - Add `GMAIL_API_MAX_RETRIES = 3`
    - Add `GMAIL_API_RETRY_DELAY_BASE = 1`
  - [ ] 1.7 Test manually:
    - Run `GmailClient.list_messages()` against test Gmail account
    - Verify pagination works (fetch 100+ emails)
    - Verify rate limiting prevents quota exhaustion
    - Verify error handling (trigger 429 by rapid requests)

- [ ] **2.0 AI Classification (Tier 2 - OpenAI Fallback)**
  - [ ] 2.1 Create `app/modules/classifier/openai_client.py`:
    - Import OpenAI SDK (`openai` package)
    - Create `OpenAIClient` class with `__init__(api_key: str)` constructor
    - Implement `classify_email(metadata: EmailMetadata) -> dict` method
    - Build prompt:
      ```
      Classify this email as TRASH (promotional spam), ARCHIVE (receipts/transactional), or KEEP (important personal).

      Email metadata:
      - From: {sender_address}
      - Subject: {subject}
      - Snippet: {first_200_chars}
      - Has unsubscribe link: {yes/no}
      - Gmail category: {category}

      Respond with JSON: {"action": "trash|archive|keep", "confidence": 0.0-1.0, "reason": "brief explanation"}
      ```
    - Use GPT-4o-mini model (`gpt-4o-mini`)
    - Parse JSON response, validate structure
    - Add error handling for API failures (timeout, rate limit, invalid JSON)
    - Track token usage and cost
  - [ ] 2.2 Create `app/modules/classifier/tier2_ai.py`:
    - Import `OpenAIClient`
    - Create `classify_email_tier2(metadata: EmailMetadata) -> ClassificationResult` function
    - Call `OpenAIClient.classify_email(metadata)`
    - Convert OpenAI response to `ClassificationResult` object
    - Add confidence adjustment (reduce AI confidence by 0.1 for safety)
    - Implement response caching in Redis (key: `ai_classification:{sender_domain}:{subject_pattern_hash}`, TTL: 30 days)
    - Add logging for AI calls (track cost, response time)
  - [ ] 2.3 Update `app/tasks/classify.py`:
    - Modify `classify_email_tier1()` task to check Tier 1 confidence
    - If Tier 1 confidence <0.90, call `classify_email_tier2()`
    - Combine Tier 1 + Tier 2 results: `final_confidence = (tier1_confidence * 0.4) + (tier2_confidence * 0.6)`
    - If trash action AND final_confidence <0.85, demote to `review`
    - Update `classification_metadata` JSONB to include AI response
  - [ ] 2.4 Update `app/core/config.py`:
    - Add `OPENAI_API_KEY` (required)
    - Add `OPENAI_MODEL = "gpt-4o-mini"`
    - Add `AI_CONFIDENCE_THRESHOLD = 0.90` (when to call AI)
    - Add `AI_CACHE_TTL_DAYS = 30`
  - [ ] 2.5 Create `tests/unit/test_tier2_ai.py`:
    - Mock OpenAI API responses
    - Test successful classification (trash, archive, keep)
    - Test confidence adjustment
    - Test response caching (verify Redis key)
    - Test error handling (API timeout, invalid JSON)
  - [ ] 2.6 Create `tests/security/test_ai_no_body.py`:
    - Verify AI prompt does NOT contain full email body
    - Verify prompt only includes: sender, subject, snippet (200 chars max)
    - Test with mock emails containing sensitive data (ensure not sent to AI)
  - [ ] 2.7 Test AI classification manually:
    - Run on 50 test emails from own Gmail
    - Compare Tier 1 vs Tier 2 classifications
    - Verify AI improves accuracy on uncertain emails
    - Check OpenAI API usage and cost

- [ ] **3.0 Action Execution (Trash, Archive, Keep)**
  - [ ] 3.1 Create `app/modules/executor/actions.py`:
    - Import `GmailClient`
    - Create `execute_trash_action(mailbox: Mailbox, message_id: str) -> dict` function
      - Use `gmail.users().messages().trash(userId='me', id=message_id)`
      - Return `{'status': 'success', 'action': 'trash', 'message_id': message_id}`
      - Add error handling (404 = message not found, 403 = permission denied)
    - Create `execute_archive_action(mailbox: Mailbox, message_id: str) -> dict` function
      - Use `gmail.users().messages().modify(userId='me', id=message_id, body={'removeLabelIds': ['INBOX']})`
      - Return `{'status': 'success', 'action': 'archive', 'message_id': message_id}`
    - Create `execute_keep_action(message_id: str) -> dict` function
      - No-op (no Gmail API call needed)
      - Return `{'status': 'success', 'action': 'keep', 'message_id': message_id}`
    - Add logging for all actions
  - [ ] 3.2 Create `execute_action(mailbox: Mailbox, email_action: EmailAction) -> dict` orchestrator function:
    - Check if `user_settings.action_mode_enabled = true` (if false, skip execution - sandbox mode)
    - Route to appropriate action function based on `email_action.action`
    - Store original Gmail labels in `email_action.original_label_ids` before executing (for undo)
    - Handle errors gracefully (log error, update email_action with failure reason)
  - [ ] 3.3 Update `app/models/email_action.py`:
    - Add `original_label_ids` column: `Column(ARRAY(String), nullable=True)`
    - Add `executed_at` column: `Column(DateTime, nullable=True)`
    - Add `execution_error` column: `Column(Text, nullable=True)`
  - [ ] 3.4 Create Alembic migration `006_add_execution_fields.py`:
    - Add `original_label_ids`, `executed_at`, `execution_error` columns to `email_actions` table
    - Run migration: `alembic upgrade head`
  - [ ] 3.5 Integrate action execution into classification flow:
    - After classification completes in `classify_email_tier1()` task
    - If `action != 'review'` AND `user_settings.action_mode_enabled = true`
    - Call `execute_action(mailbox, email_action)`
    - Update `email_action.executed_at` and `email_action.original_label_ids`
  - [ ] 3.6 Create `tests/unit/test_actions.py`:
    - Mock Gmail API calls
    - Test `execute_trash_action()` calls `.trash()` API
    - Test `execute_archive_action()` calls `.modify()` with removeLabelIds
    - Test sandbox mode skips execution
    - Test error handling (404, 403)
  - [ ] 3.7 Create `tests/safety/test_no_permanent_delete.py`:
    - Scan entire codebase for `.delete()` method calls
    - Assert NO calls to `gmail.users().messages().delete()` exist
    - Only allow `.trash()` (reversible) and `.modify()` (archive)
    - Fail test if permanent delete detected
  - [ ] 3.8 Test action execution manually:
    - Enable action mode in user settings
    - Process 10 test emails
    - Verify trash action moves emails to Gmail Trash (30-day countdown)
    - Verify archive action removes from inbox, email still searchable in All Mail
    - Verify keep action is no-op

- [ ] **4.0 Auto-Labeling System (Document Type Detection)**
  - [ ] 4.1 Create `app/modules/executor/document_classifier.py`:
    - Define document type patterns:
      ```python
      DOCUMENT_PATTERNS = {
          'Receipts': ['receipt', 'your order', 'purchase confirmation', 'thank you for your order'],
          'Invoices': ['invoice', 'payment due', 'bill', 'statement'],
          'Shipping': ['shipped', 'tracking', 'delivery', 'out for delivery', 'package'],
          'Bookings': ['reservation', 'booking confirmed', 'check-in', 'itinerary', 'ticket'],
          'Financial': ['statement', 'balance', 'tax', 'W-2', '1099', 'bank', 'paypal', 'stripe'],
          'Newsletters': ['newsletter', 'digest', 'weekly roundup', 'this week', 'substack', 'medium'],
          'Research': ['research', 'analysis', 'report', 'market update', 'analyst', 'whitepaper'],
      }
      ```
    - Create `detect_document_type(metadata: EmailMetadata) -> tuple[str, float]` function
      - Check subject + snippet against patterns
      - Check sender domain for financial senders (banks, PayPal, Stripe)
      - Return `(document_type, confidence)` tuple
      - Return `('Other', 0.0)` if no match
    - Require confidence >0.85 to apply label
  - [ ] 4.2 Create `app/modules/executor/labels.py`:
    - Create `ensure_label_exists(gmail_client: GmailClient, label_name: str) -> str` function
      - Get list of user's existing labels via `gmail.users().labels().list()`
      - If label exists, return label ID
      - If not, create label via `gmail.users().labels().create()`
      - Cache label IDs in Redis (key: `gmail_labels:{user_id}`, TTL: 24h)
    - Create `apply_label(gmail_client: GmailClient, message_id: str, label_name: str) -> dict` function
      - Ensure label exists (call `ensure_label_exists()`)
      - Apply label via `gmail.users().messages().modify(userId='me', id=message_id, body={'addLabelIds': [label_id]})`
      - Return `{'status': 'success', 'label_applied': label_name}`
  - [ ] 4.3 Integrate auto-labeling into archive action:
    - Update `execute_archive_action()` in `actions.py`
    - After removing INBOX label, check if `user_settings.auto_label_archived_emails = true`
    - If true, call `detect_document_type(metadata)`
    - If confidence >0.85, call `apply_label(gmail_client, message_id, document_type)`
    - Store document type in `email_action.classification_metadata['document_type']`
  - [ ] 4.4 Update `app/models/user_settings.py`:
    - Add `auto_label_archived_emails = Column(Boolean, default=True, nullable=False)`
  - [ ] 4.5 Create Alembic migration `007_add_auto_label_setting.py`:
    - Add `auto_label_archived_emails` column to `user_settings` table
    - Set default to `true` for existing users
    - Run migration: `alembic upgrade head`
  - [ ] 4.6 Create `tests/unit/test_document_classifier.py`:
    - Test receipt detection: "Your Amazon order receipt"
    - Test invoice detection: "Invoice #12345 - Payment due"
    - Test shipping detection: "Your package has shipped"
    - Test research detection: "Market analysis report Q4 2024"
    - Test no match: "Meeting tomorrow?" → 'Other'
    - Test confidence thresholds
  - [ ] 4.7 Test auto-labeling manually:
    - Archive 10 test emails (receipts, invoices, shipping notifications)
    - Verify Gmail labels are created: "Receipts", "Invoices", "Shipping"
    - Verify labels applied to correct emails
    - Search Gmail for `label:Receipts` and verify results

- [ ] **5.0 Undo Functionality**
  - [ ] 5.1 Create `app/modules/executor/undo.py`:
    - Create `undo_action(email_action: EmailAction, mailbox: Mailbox) -> dict` function
    - Check if `email_action.can_undo` is true (within 30-day window, not already undone)
    - If original action was `trash`:
      - Call `gmail.users().messages().untrash(userId='me', id=message_id)`
    - If original action was `archive`:
      - Call `gmail.users().messages().modify(userId='me', id=message_id, body={'addLabelIds': ['INBOX']})`
    - Update `email_action.undone_at = datetime.utcnow()`
    - Create new `EmailAction` record with `action='undo'` and reference to original action
    - Return `{'status': 'success', 'undone_action': email_action.action, 'message_id': email_action.message_id}`
  - [ ] 5.2 Create API endpoint `/api/undo/{email_action_id}` in `app/modules/portal/audit_routes.py`:
    - Accept POST request with JWT magic link token
    - Decode token, verify user_id matches email_action owner
    - Verify token not expired (24-hour expiration)
    - Call `undo_action(email_action, mailbox)`
    - Return JSON response: `{'status': 'success', 'message': 'Email restored to inbox'}`
  - [ ] 5.3 Create magic link generator in `app/core/security.py`:
    - Create `generate_undo_link(email_action_id: str, user_id: str) -> str` function
    - Encode JWT with payload: `{'email_action_id': email_action_id, 'user_id': user_id, 'exp': datetime.utcnow() + timedelta(hours=24)}`
    - Return URL: `f"https://app.inboxjanitor.com/undo/{token}"`
  - [ ] 5.4 Create `tests/unit/test_undo.py`:
    - Mock Gmail API untrash/modify calls
    - Test undo trash action (verify `.untrash()` called)
    - Test undo archive action (verify `.modify()` with addLabelIds=['INBOX'])
    - Test expired undo (30+ days old) raises error
    - Test already undone action raises error
  - [ ] 5.5 Create `tests/safety/test_undo_flow.py`:
    - End-to-end undo test:
      1. Execute trash action
      2. Verify email in Gmail Trash
      3. Call undo
      4. Verify email restored to inbox
    - Test with archive action (archive → undo → back in inbox)
    - Test undo deadline enforcement (can't undo after 30 days)
  - [ ] 5.6 Test undo manually:
    - Trash 3 test emails via action execution
    - Generate magic links for each
    - Click magic link, verify email restored to inbox
    - Test with archived email (verify re-added to inbox)

- [ ] **6.0 Background Job Scheduler (Polling)**
  - [ ] 6.1 Create `app/tasks/process_emails.py`:
    - Create `process_recent_emails()` Celery task
    - Fetch all active mailboxes from database
    - For each mailbox:
      - Call `GmailClient.list_messages(query='in:inbox category:promotions newer_than:7d', max_results=100)`
      - For each message, check if already processed (query `email_actions` table for existing `message_id`)
      - If not processed, fetch metadata via `GmailClient.get_message(message_id, format='metadata')`
      - Enqueue classification task: `classify_email_tier1.delay(mailbox_id, metadata.dict())`
    - Add rate limiting (10 emails/min per user)
    - Add error handling (skip mailbox on OAuth failure, log error)
  - [ ] 6.2 Create `app/tasks/scheduler.py`:
    - Configure Celery Beat schedule:
      ```python
      celery.conf.beat_schedule = {
          'process-recent-emails': {
              'task': 'app.tasks.process_emails.process_recent_emails',
              'schedule': crontab(minute='*/10')  # Every 10 minutes
          }
      }
      ```
  - [ ] 6.3 Update `app/core/celery_app.py`:
    - Import `app/tasks/scheduler.py` to register beat schedule
    - Verify Celery Beat configuration loads correctly
  - [ ] 6.4 Test background job locally:
    - Start Celery worker: `celery -A app.core.celery_app worker --loglevel=info`
    - Start Celery beat: `celery -A app.core.celery_app beat --loglevel=info`
    - Wait 10 minutes, verify `process_recent_emails` task runs
    - Send test email to Gmail, verify it's classified within 10 minutes
  - [ ] 6.5 Update Railway deployment configuration:
    - Verify web service runs Celery beat: `celery -A app.core.celery_app beat`
    - Verify worker service runs: `celery -A app.core.celery_app worker`
    - Check Railway logs for Celery beat execution

- [ ] **7.0 Settings UI (Action Mode, Thresholds, Toggles)**
  - [ ] 7.1 Create `app/modules/portal/settings_routes.py`:
    - Create GET `/dashboard/settings` route
      - Fetch `user_settings` from database
      - Render `settings.html` template with current settings
    - Create POST `/dashboard/settings` route
      - Accept form data: `action_mode_enabled`, `confidence_auto_threshold`, `auto_label_archived_emails`, `backlog_cleanup_age_days`
      - Validate inputs (thresholds 0.0-1.0, age_days >0)
      - Update `user_settings` in database
      - Show success message: "Settings saved"
      - Add CSRF protection
  - [ ] 7.2 Create `app/templates/settings.html`:
    - Action mode toggle with warning: "Action mode will modify emails in Gmail. You have 30 days to undo. Continue?"
    - Confidence threshold sliders (Alpine.js):
      - Auto-action threshold (default 0.85)
      - Review threshold (default 0.70)
    - Auto-labeling toggle: "Auto-label archived emails by document type"
    - Backlog cleanup settings:
      - Enable/disable toggle
      - Age threshold: "Auto-archive promotional emails older than [90] days"
    - Save button (HTMX form submission)
  - [ ] 7.3 Register routes in `app/main.py`:
    - Import `settings_routes` router
    - Include router: `app.include_router(settings_routes.router)`
  - [ ] 7.4 Update `app/models/user_settings.py`:
    - Add `backlog_cleanup_enabled = Column(Boolean, default=False, nullable=False)`
    - Add `backlog_cleanup_age_days = Column(Integer, default=90, nullable=False)`
  - [ ] 7.5 Create Alembic migration `008_add_backlog_settings.py`:
    - Add `backlog_cleanup_enabled`, `backlog_cleanup_age_days` columns to `user_settings`
    - Run migration: `alembic upgrade head`
  - [ ] 7.6 Create `tests/e2e/settings.spec.js`:
    - Test action mode toggle (click toggle, verify warning shown, submit form)
    - Test confidence threshold sliders (adjust slider, verify value updates)
    - Test auto-labeling toggle
    - Test backlog cleanup age input
    - Test form submission (HTMX, verify success message)
    - Test CSRF protection (submit without token, expect 403)
  - [ ] 7.7 Test settings UI manually:
    - Navigate to `/dashboard/settings`
    - Toggle action mode, verify warning appears
    - Adjust sliders, submit form, verify settings saved
    - Reload page, verify settings persisted

- [ ] **8.0 Audit Log UI (View Actions, Undo Buttons)**
  - [ ] 8.1 Create `app/modules/portal/audit_routes.py`:
    - Create GET `/audit` route
      - Fetch recent 100 `email_actions` for current user (paginated)
      - Support filters: `action` type (trash/archive/keep), date range, sender
      - Support search: sender or subject
      - Render `audit.html` template with actions
    - Create POST `/audit/export` route
      - Generate CSV export of all email_actions for user
      - Include columns: date, from, subject, action, confidence, can_undo
      - Stream CSV download
  - [ ] 8.2 Create `app/templates/audit.html`:
    - Table showing recent email actions:
      - Columns: Date, From, Subject, Action, Confidence, Undo
      - Undo button for actions where `can_undo = true` (within 30 days)
      - Show "Cannot undo (expired)" for actions >30 days old
      - Show "Undone at {date}" for already-undone actions
    - Filters: Action type dropdown, date range picker
    - Search box: Filter by sender or subject
    - Export button: Download CSV
    - Pagination: 100 actions per page
  - [ ] 8.3 Integrate undo button with API:
    - When user clicks "Undo" button, send POST request to `/api/undo/{email_action_id}`
    - Show loading spinner during request
    - On success, update UI: "Email restored to inbox"
    - On error, show error message
  - [ ] 8.4 Register routes in `app/main.py`:
    - Import `audit_routes` router
    - Include router: `app.include_router(audit_routes.router)`
  - [ ] 8.5 Create `tests/e2e/audit.spec.js`:
    - Test audit log page loads with actions
    - Test pagination (click "Next page", verify new actions shown)
    - Test filters (select "trash" action, verify only trash actions shown)
    - Test search (enter sender email, verify filtered results)
    - Test undo button (click undo, verify success message)
    - Test expired undo (verify "Cannot undo" shown for old actions)
    - Test CSV export (click export, verify CSV downloads)
  - [ ] 8.6 Test audit log UI manually:
    - Navigate to `/audit`
    - Verify recent actions displayed
    - Test filters and search
    - Click "Undo" button, verify email restored
    - Download CSV export, verify data

- [ ] **9.0 Backlog Cleanup (Batch Processing)**
  - [ ] 9.1 Create `app/modules/ingest/backlog_analyzer.py`:
    - Create `analyze_backlog(mailbox: Mailbox) -> dict` function
      - Query Gmail API for email counts by category and age:
        - `in:inbox category:promotions` (total)
        - `in:inbox category:promotions older_than:30d`
        - `in:inbox category:promotions older_than:90d`
        - `in:inbox category:promotions older_than:180d`
      - Return dict:
        ```python
        {
          'total_inbox': 20287,
          'promotions_total': 33927,
          'promotions_30d': 32000,
          'promotions_90d': 28000,
          'promotions_180d': 25000
        }
        ```
  - [ ] 9.2 Create welcome email template for backlog cleanup (Postmark):
    - Subject: "Inbox Janitor found {promotions_total} promotional emails"
    - Body:
      ```
      Hi {user_name},

      We analyzed your Gmail and found:
      - {promotions_total} promotional emails
      - {promotions_90d} are older than 90 days

      Want us to clean them up?
      [Yes, clean up old promotions] [No, just handle new emails]

      Settings:
      - Emails older than 90 days → Trash
      - Receipts/invoices → Archive with labels
      - Important emails (starred, contacts) → Keep

      You can undo any action within 30 days.
      ```
    - Magic link: "Yes, clean up" → `/api/backlog/start/{jwt_token}`
  - [ ] 9.3 Create `app/tasks/backlog.py`:
    - Create `process_backlog_batch(mailbox_id: str, age_days: int, batch_size: int = 100)` Celery task
      - Query Gmail API: `in:inbox category:promotions older_than:{age_days}d`
      - Fetch first `batch_size` emails
      - For each email, enqueue classification task: `classify_email_tier1.delay(mailbox_id, metadata.dict())`
      - If more emails remain (nextPageToken), enqueue next batch: `process_backlog_batch.delay(mailbox_id, age_days, batch_size)`
      - Track progress in Redis: `backlog_progress:{user_id}` → `{'processed': 1000, 'total': 33000}`
  - [ ] 9.4 Create `app/modules/portal/backlog_routes.py`:
    - Create POST `/api/backlog/start` route (JWT magic link)
      - Decode JWT, verify user_id
      - Get `user_settings.backlog_cleanup_age_days`
      - Enqueue first batch: `process_backlog_batch.delay(mailbox_id, age_days, batch_size=100)`
      - Return success message: "Backlog cleanup started. We'll send progress updates."
    - Create GET `/api/backlog/progress` route
      - Fetch progress from Redis: `backlog_progress:{user_id}`
      - Return JSON: `{'processed': 1000, 'total': 33000, 'percentage': 3.0}`
  - [ ] 9.5 Send progress emails (Postmark):
    - Every 1,000 emails processed, send email:
      ```
      Backlog cleanup progress: {processed}/{total} emails ({percentage}%)

      So far:
      - {trash_count} emails trashed
      - {archive_count} emails archived
      - {keep_count} emails kept

      You can view details in your audit log.
      ```
  - [ ] 9.6 Create `tests/unit/test_backlog_analyzer.py`:
    - Mock Gmail API responses
    - Test backlog analysis (verify counts by age)
    - Test edge cases (empty inbox, no old emails)
  - [ ] 9.7 Test backlog cleanup manually:
    - Trigger backlog analysis on test account
    - Click "Yes, clean up" magic link
    - Monitor progress via `/api/backlog/progress`
    - Verify emails processed in batches (100 at a time)
    - Verify progress emails sent every 1,000 emails

- [ ] **10.0 Integration Testing & Production Validation**
  - [ ] 10.1 End-to-end integration test (manual):
    - Set up test Gmail account with 500+ promotional emails
    - Connect account via OAuth
    - Enable sandbox mode (action_mode_enabled = false)
    - Wait for background job to process emails (10 min polling)
    - Verify classifications appear in audit log
    - Review 100 random classifications for accuracy
    - Calculate accuracy: (correct classifications / total) * 100
    - Target: >95% accuracy
  - [ ] 10.2 Enable action mode and validate:
    - Toggle action_mode_enabled = true in settings
    - Process 50 test emails
    - Verify trash actions move emails to Gmail Trash
    - Verify archive actions remove from inbox, add document type labels
    - Verify keep actions leave emails untouched
    - Verify no starred or important emails touched
    - Test undo for 10 random actions
  - [ ] 10.3 Test backlog cleanup on own Gmail:
    - Run backlog analysis on own account (33,927 promotions)
    - Review proposed actions for first 100 emails
    - If accuracy >95%, approve backlog cleanup
    - Monitor progress over 2-3 days (rate limited to 10 emails/min)
    - Review audit log after completion
    - Calculate undo rate: (undone actions / total actions) * 100
    - Target: <1% undo rate (indicates high quality)
  - [ ] 10.4 Security validation:
    - Run all security tests: `pytest tests/security/`
    - Verify no email bodies stored in database: `SELECT snippet FROM email_actions WHERE length(snippet) > 200;` (should be empty)
    - Verify OAuth tokens encrypted: `SELECT encrypted_access_token FROM mailboxes;` (should be Fernet-encrypted)
    - Scan codebase for `.delete()` calls: `grep -r "\.delete()" app/` (should only find SQLAlchemy deletes, not Gmail API)
  - [ ] 10.5 Safety validation:
    - Run all safety tests: `pytest tests/safety/`
    - Manually test safety rails:
      - Star an email, verify it's kept (not trashed)
      - Send email from contact, verify it's kept
      - Send email with "interview" keyword, verify it's kept
      - Send recent email (<3 days), verify it goes to review (not trashed)
  - [ ] 10.6 Performance validation:
    - Monitor Gmail API quota usage over 24 hours
    - Verify rate limiting prevents quota exhaustion
    - Check Redis cache hit rate for AI classifications
    - Monitor OpenAI API costs (target <$3/month per user for 100 emails/day)
    - Check Celery worker lag (should be <5 min)
  - [ ] 10.7 Create production deployment checklist:
    - [ ] All environment variables set in Railway (OPENAI_API_KEY, GMAIL_API_RATE_LIMIT_PER_MIN)
    - [ ] Database migrations applied: `alembic upgrade head`
    - [ ] Celery worker running
    - [ ] Celery beat running (scheduler)
    - [ ] Health check returns 200 OK
    - [ ] Test OAuth flow (connect Gmail account)
    - [ ] Test background job (verify emails processed every 10 min)
    - [ ] Monitor Sentry for errors (target: 0 errors in first 24h)
  - [ ] 10.8 Week 1 sandbox mode validation:
    - Run on own Gmail for 7 consecutive days
    - Review all classifications daily
    - Track false positives (important emails marked trash): target <1 per day
    - Track false negatives (spam marked keep): acceptable, user can manually trash
    - Tune confidence thresholds if needed
    - Document any safety rail improvements
  - [ ] 10.9 Week 2 action mode validation:
    - Enable action mode after Week 1 sandbox validation
    - Process 100 emails with real Gmail actions
    - Verify no unintended deletions
    - Test undo flow for 10 random actions
    - Monitor undo rate: target <1%
  - [ ] 10.10 Update documentation:
    - Update `CLAUDE.md` with PRD 0004 completion status
    - Update `CHANGELOG.md` with detailed completion notes
    - Document lessons learned
    - Create runbook for common issues (OAuth failures, quota exhaustion, undo requests)

---

## Implementation Notes

**Current Capabilities (Already Working):**
- Tier 1 classification works (metadata-based, no AI yet)
- Safety rails prevent trashing starred/important emails
- Email metadata extracted from Gmail API
- Classification results stored in `email_actions` table
- BUT: No actual Gmail actions executed yet (sandbox mode only)

**Key Integration Points:**
1. **Tier 1 → Tier 2 Flow:** If Tier 1 confidence <0.90, call AI classifier
2. **Classification → Execution:** After classification, execute action (trash/archive) if action_mode_enabled=true
3. **Archive → Auto-Label:** When archiving, detect document type and apply Gmail label
4. **Execution → Audit:** Log all actions in email_actions table with original_label_ids for undo

**Safety Requirements (CRITICAL):**
- NEVER use `gmail.users().messages().delete()` (permanent delete)
- ONLY use `.trash()` (30-day recovery) and `.modify()` (archive/label)
- All actions logged in immutable email_actions table
- Safety rails override classifier when critical keywords detected

**Testing Strategy:**
- Unit tests for each module (Gmail client, AI classifier, actions, labels)
- Security tests (no email bodies stored, no permanent delete)
- Safety tests (starred/important never touched, undo works)
- E2E tests (settings form, audit log, undo button)
- Manual testing: Run in sandbox mode on own Gmail for 1 week before enabling actions

---

I have generated the high-level tasks based on the PRD. Ready to generate the sub-tasks? Respond with "Go" to proceed.
