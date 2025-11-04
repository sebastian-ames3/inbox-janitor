# Task List: Email Processing Pipeline (PRD 0001)

**Status:** Ready for Execution
**Created:** 2025-11-04
**PRD:** 0001-prd-email-processing-pipeline.md
**Owner:** Sebastian Ames

---

## Overview

This task list breaks down the Email Processing Pipeline PRD into 7 parent tasks with detailed sub-tasks. Each sub-task includes specific file paths and implementation details.

**Execution Strategy:**
- Complete sub-tasks sequentially within each parent task
- Get user review/approval after each sub-task ("yes" to continue)
- Run tests after each parent task completes
- Commit after each parent task
- Deploy to Railway after all tasks complete

---

## Task 1.0: Set up Celery Worker Infrastructure

**Goal:** Configure Celery + Redis for background task processing with Railway worker service.

**Files to Create/Modify:**
- `app/core/celery_app.py` (new)
- `app/tasks/__init__.py` (modify)
- `Procfile.worker` (new, for Railway)
- `app/main.py` (modify to import celery_app)

### Sub-tasks:

- [ ] **1.1** Create `app/core/celery_app.py`
  - Initialize Celery app with Redis broker
  - Configure task serialization (JSON)
  - Set task timeouts (30s for metadata extraction, 10s for classification)
  - Add task routes for different queues (default, priority)
  - Configure `acks_late=True` for reliability
  - Add exponential backoff for retries

- [ ] **1.2** Configure Celery Beat scheduler
  - Add beat schedule configuration to `celery_app.py`
  - Define `renew-gmail-watches` task (every 6 days at 3 AM)
  - Define `fallback-poll-gmail` task (every 10 minutes)
  - Use `PersistentScheduler` for reliability

- [ ] **1.3** Create worker start script
  - Create `Procfile.worker` for Railway deployment
  - Command: `celery -A app.core.celery_app worker --loglevel=info --beat`
  - Document environment variables needed

- [ ] **1.4** Create test task for verification
  - Add simple test task in `app/tasks/__init__.py`
  - Task: `test_celery_connection()` - logs "Celery works!"
  - Test locally: `celery -A app.core.celery_app worker --loglevel=info`
  - Verify task executes successfully

- [ ] **1.5** Update Railway configuration
  - Document adding Redis service to Railway
  - Document creating worker service (same codebase, different command)
  - Verify `REDIS_URL` environment variable propagates to both services

**Success Criteria:**
- [ ] Celery worker starts without errors
- [ ] Test task executes successfully
- [ ] Beat scheduler shows scheduled tasks in logs
- [ ] Redis connection confirmed in health check

---

## Task 2.0: Create Gmail Watch & Pub/Sub Setup

**Goal:** Implement Gmail Push Notifications with automatic watch renewal.

**Files to Create/Modify:**
- `app/modules/ingest/gmail_watch.py` (new)
- `app/tasks/ingest.py` (new)
- `app/modules/auth/gmail_oauth.py` (modify - add helper functions)

### Sub-tasks:

- [ ] **2.1** Create Gmail API helper utilities
  - Add to `app/modules/auth/gmail_oauth.py`
  - Function: `get_gmail_service(mailbox_id)` - creates authenticated Gmail API client
  - Function: `decrypt_and_refresh_token(mailbox)` - handles token decryption/refresh
  - Add error handling for expired tokens (mark mailbox inactive)

- [ ] **2.2** Create `app/modules/ingest/gmail_watch.py`
  - Function: `register_gmail_watch(mailbox_id: UUID) -> dict`
  - Call Gmail API `users().watch()` with:
    - `topicName`: from `GOOGLE_PUBSUB_TOPIC` env var
    - `labelIds`: ['INBOX'] (only watch inbox)
  - Return watch response with `historyId` and `expiration`
  - Update mailbox record with `watch_expiration` and `last_history_id`
  - Add logging for successful registration

- [ ] **2.3** Implement watch renewal logic
  - Function: `renew_gmail_watch(mailbox_id: UUID) -> bool`
  - Check if watch expires in next 24 hours
  - If yes, call `register_gmail_watch()` again
  - Return True if renewed, False if skipped
  - Log renewal status

- [ ] **2.4** Create Celery task for watch renewal
  - In `app/tasks/ingest.py`
  - Task: `renew_all_gmail_watches()`
  - Query all active mailboxes (`is_active=true`)
  - Filter mailboxes with `last_used_at` within 30 days
  - Call `renew_gmail_watch()` for each
  - Log count of renewed watches
  - Add to Celery beat schedule (every 6 days)

- [ ] **2.5** Create fallback polling task
  - Task: `fallback_poll_gmail()`
  - Query mailboxes where `last_webhook_received_at` > 15 minutes ago
  - Manually fetch history using `history.list()`
  - Enqueue processing tasks for new emails
  - Add to Celery beat schedule (every 10 minutes)
  - Add logging for catch-up events

- [ ] **2.6** Document Pub/Sub setup steps
  - Create `docs/pubsub-setup.md` with manual steps:
    1. Enable Cloud Pub/Sub API in Google Cloud Console
    2. Create topic: `projects/{PROJECT_ID}/topics/inbox-janitor-gmail`
    3. Create push subscription pointing to Railway webhook URL
    4. Grant Gmail API publish permission (automatic via watch() call)
  - Document required environment variables

**Success Criteria:**
- [ ] Gmail watch registers successfully for test mailbox
- [ ] Watch renewal task executes without errors
- [ ] Fallback polling task runs every 10 minutes
- [ ] Watches show expiration 7 days in future

---

## Task 3.0: Build Webhook Receiver Endpoint

**Goal:** Create POST endpoint to receive Gmail Pub/Sub notifications and enqueue processing tasks.

**Files to Create/Modify:**
- `app/api/webhooks.py` (new)
- `app/main.py` (modify - add webhook router)
- `app/models/webhook.py` (new - request/response models)

### Sub-tasks:

- [ ] **3.1** Create webhook request/response models
  - Create `app/models/webhook.py`
  - Model: `PubSubMessage` - base64 message, attributes, messageId
  - Model: `PubSubRequest` - message wrapper, subscription
  - Model: `WebhookResponse` - success status
  - Use Pydantic for validation

- [ ] **3.2** Create webhook router
  - Create `app/api/webhooks.py`
  - Route: `POST /webhooks/gmail`
  - Accept `PubSubRequest` body
  - Decode base64 message payload
  - Extract `emailAddress` and `historyId`
  - Return `200 OK` immediately (within 10ms)

- [ ] **3.3** Add Pub/Sub message validation
  - Function: `validate_pubsub_message(request: PubSubRequest) -> bool`
  - Check for required fields (message.data, message.messageId)
  - Decode base64 payload
  - Parse JSON payload
  - Return True if valid, False otherwise
  - Log invalid messages to Sentry (don't raise exception)

- [ ] **3.4** Implement mailbox lookup and task enqueueing
  - Query database for mailbox by `email_address`
  - If mailbox not found: log warning, return 200 OK (prevent retries)
  - If mailbox inactive: log warning, return 200 OK
  - Enqueue Celery task: `process_gmail_history.delay(mailbox_id, history_id)`
  - Update mailbox `last_webhook_received_at` timestamp
  - Catch and log task enqueueing errors (still return 200 OK)

- [ ] **3.5** Add webhook router to FastAPI app
  - In `app/main.py`
  - Import webhook router: `from app.api.webhooks import router as webhook_router`
  - Add router: `app.include_router(webhook_router, prefix="/webhooks", tags=["webhooks"])`
  - Verify endpoint appears in `/docs`

- [ ] **3.6** Create manual webhook testing endpoint
  - Route: `POST /webhooks/gmail/test` (development only)
  - Accept `mailbox_id` and trigger processing manually
  - Protected by `ENVIRONMENT == "development"` check
  - Use for local testing without Pub/Sub

**Success Criteria:**
- [ ] Webhook endpoint returns 200 OK immediately
- [ ] Invalid messages logged, not raised as errors
- [ ] Tasks successfully enqueued to Celery
- [ ] Mailbox lookup works correctly
- [ ] Test endpoint works for manual triggering

---

## Task 4.0: Implement Email Metadata Extraction

**Goal:** Build Celery task to fetch email metadata from Gmail API using delta sync.

**Files to Create/Modify:**
- `app/modules/ingest/metadata_extractor.py` (new)
- `app/tasks/ingest.py` (modify - add processing task)
- `app/models/email_metadata.py` (new - internal data model)

### Sub-tasks:

- [ ] **4.1** Create email metadata internal model
  - Create `app/models/email_metadata.py` (Pydantic model, NOT SQLAlchemy yet)
  - Model: `EmailMetadata` with fields:
    - `message_id`, `thread_id`, `from_address`, `from_name`, `from_domain`
    - `subject`, `snippet`, `gmail_labels`, `gmail_category`
    - `headers` (dict of extracted headers)
    - `received_at` (datetime)
  - Add validation for required fields

- [ ] **4.2** Create header extraction utilities
  - In `app/modules/ingest/metadata_extractor.py`
  - Function: `extract_header(headers: list, name: str) -> Optional[str]`
  - Function: `parse_from_header(from_header: str) -> tuple[str, str]`
    - Returns (email_address, display_name)
  - Function: `extract_domain(email: str) -> str`
  - Function: `determine_gmail_category(label_ids: list) -> Optional[str]`
    - Maps CATEGORY_PROMOTIONS → "promotional", etc.

- [ ] **4.3** Implement history delta sync
  - Function: `fetch_new_emails_from_history(mailbox_id: UUID, history_id: str) -> list[str]`
  - Get Gmail service for mailbox
  - Call `users().history().list(startHistoryId=history_id)`
  - Extract message IDs from `messagesAdded` events
  - Filter out non-INBOX messages (check labelIds)
  - Return list of message IDs to process
  - Handle pagination if history is large

- [ ] **4.4** Implement metadata extraction
  - Function: `extract_email_metadata(mailbox_id: UUID, message_id: str) -> EmailMetadata`
  - Get Gmail service for mailbox
  - Call `users().messages().get(id=message_id, format='metadata')`
  - Extract headers: From, Subject, List-Unsubscribe, Precedence, Auto-Submitted
  - Parse from_header to get email and name
  - Extract domain from email
  - Determine Gmail category from labelIds
  - Build and return `EmailMetadata` instance
  - **CRITICAL:** Never call format='full' or format='raw'

- [ ] **4.5** Create main processing Celery task
  - In `app/tasks/ingest.py`
  - Task: `process_gmail_history(mailbox_id: UUID, history_id: str)`
  - Call `fetch_new_emails_from_history()` to get message IDs
  - For each message ID:
    - Call `extract_email_metadata()`
    - Enqueue classification task: `classify_email_tier1.delay(mailbox_id, metadata)`
  - Update mailbox's `last_history_id` to latest
  - Add rate limiting: max 10 emails/min per mailbox (use Redis)
  - Add task retry with exponential backoff (max 3 retries)

- [ ] **4.6** Add error handling and logging
  - Catch Gmail API errors (401/403 → mark mailbox inactive)
  - Catch rate limit errors (429 → retry with exponential backoff)
  - Log processing metrics: message_id, processing time, success/failure
  - Send errors to Sentry with context (mailbox_id, message_id)

**Success Criteria:**
- [ ] History delta sync fetches only new messages
- [ ] Metadata extraction uses format='metadata' only
- [ ] Headers parsed correctly
- [ ] Gmail category determined correctly
- [ ] Rate limiting enforced (10/min per mailbox)
- [ ] Errors logged to Sentry, not raised

---

## Task 5.0: Build Tier 1 Classification Engine

**Goal:** Implement rule-based classifier using metadata signals with safety rails.

**Files to Create/Modify:**
- `app/modules/classifier/tier1.py` (new)
- `app/modules/classifier/signals.py` (new)
- `app/tasks/classify.py` (new)
- `app/models/classification.py` (new - Pydantic models)

### Sub-tasks:

- [ ] **5.1** Create classification result models
  - Create `app/models/classification.py`
  - Model: `ClassificationSignal` - name, score, reason
  - Model: `ClassificationResult` - action, confidence, signals[], reason
  - Enum: `ClassificationAction` - KEEP, ARCHIVE, TRASH, REVIEW
  - Add JSON serialization for logging

- [ ] **5.2** Implement individual signal functions
  - Create `app/modules/classifier/signals.py`
  - Function: `signal_gmail_category(category: str) -> ClassificationSignal`
    - CATEGORY_PROMOTIONS → +0.60 (trash)
    - CATEGORY_SOCIAL → +0.50 (trash)
    - CATEGORY_UPDATES → +0.30 (archive)
    - CATEGORY_FORUMS → +0.20 (archive)
    - CATEGORY_PERSONAL → -0.30 (keep)
  - Function: `signal_list_unsubscribe(headers: dict) -> ClassificationSignal`
    - Has List-Unsubscribe → +0.40 (trash)
  - Function: `signal_bulk_headers(headers: dict) -> ClassificationSignal`
    - Precedence: bulk → +0.35 (trash)
    - Auto-Submitted: auto-generated → +0.30 (archive)
    - Both → +0.50 (trash)
  - Function: `signal_sender_domain(domain: str) -> ClassificationSignal`
    - Check against marketing platform patterns (sendgrid, mailchimp, etc.)
    - Match → +0.45 (trash)

- [ ] **5.3** Implement safety rails
  - Function: `check_exception_keywords(subject: str, snippet: str) -> bool`
  - Keywords list: receipt, invoice, order, payment, booking, reservation, ticket, shipped, tracking, password, security, tax, medical, bank, interview, job
  - Case-insensitive matching
  - Return True if any keyword found
  - Function: `check_starred(label_ids: list) -> bool`
    - Return True if 'STARRED' in label_ids

- [ ] **5.4** Build main classification engine
  - In `app/modules/classifier/tier1.py`
  - Function: `classify_email_tier1(metadata: EmailMetadata) -> ClassificationResult`
  - Check safety rails first (starred → KEEP, exception keywords → KEEP)
  - Calculate all signals
  - Aggregate confidence scores
  - Determine action based on thresholds:
    - ≥0.85 → TRASH
    - 0.55-0.84 → ARCHIVE
    - 0.30-0.54 → REVIEW
    - <0.30 → KEEP
  - Build human-readable reason string
  - Return ClassificationResult with signals included

- [ ] **5.5** Create classification Celery task
  - In `app/tasks/classify.py`
  - Task: `classify_email_tier1(mailbox_id: UUID, metadata: EmailMetadata)`
  - Call classification engine
  - Insert result into `email_actions` table
  - Log classification (message_id, action, confidence, processing time)
  - Add error handling and Sentry logging

- [ ] **5.6** Add classification logging for learning
  - Log all classifications to structured logs (JSON format)
  - Include: message_id, action, confidence, all signal scores
  - Save to file: `logs/classifications.jsonl` (for analysis)
  - Add log rotation (daily, keep 30 days)

**Success Criteria:**
- [ ] All signals calculate correctly
- [ ] Safety rails prevent exception keyword emails from trash
- [ ] Starred emails always classified as KEEP
- [ ] Confidence thresholds applied correctly
- [ ] Classification results stored in email_actions table
- [ ] Logs include all signal details

---

## Task 6.0: Add Database Schema & Security Enforcement

**Goal:** Create email_metadata table with PostgreSQL trigger to prevent body storage.

**Files to Create/Modify:**
- `app/models/email_metadata.py` (new SQLAlchemy model - different from Pydantic in 4.1)
- `alembic/versions/002_email_metadata_and_triggers.py` (new migration)
- `app/core/database.py` (modify if needed)

### Sub-tasks:

- [ ] **6.1** Create SQLAlchemy email_metadata model
  - Create `app/models/email_metadata.py` (SQLAlchemy model)
  - Table: `email_metadata`
  - Columns:
    - `id` (UUID, primary key)
    - `mailbox_id` (UUID, foreign key)
    - `message_id` (String, indexed)
    - `thread_id` (String, indexed)
    - `from_address`, `from_name`, `from_domain` (String)
    - `subject` (String, max 500 chars)
    - `snippet` (String, max 200 chars)
    - `gmail_labels` (JSONB array)
    - `gmail_category` (String, nullable)
    - `headers` (JSONB dict)
    - `received_at` (DateTime)
    - `processed_at` (DateTime, default now)
    - `created_at` (DateTime, default now)
  - Add relationship to Mailbox model
  - **CRITICAL:** NO body, html_body, raw_content, or full_message columns

- [ ] **6.2** Add unique constraint and indexes
  - Unique constraint: `(mailbox_id, message_id)`
  - Index: `idx_email_metadata_processed_at` on `processed_at`
  - Index: `idx_email_metadata_mailbox_created` on `(mailbox_id, created_at)`
  - Index: `idx_email_actions_mailbox_created` on email_actions `(mailbox_id, created_at)`

- [ ] **6.3** Create Alembic migration
  - Generate migration: `alembic revision --autogenerate -m "Add email_metadata table and security triggers"`
  - File: `alembic/versions/002_email_metadata_and_triggers.py`
  - Include table creation
  - Include indexes

- [ ] **6.4** Add PostgreSQL trigger to prevent body columns
  - In migration, add raw SQL for event trigger:
  ```sql
  CREATE OR REPLACE FUNCTION prevent_body_columns()
  RETURNS event_trigger AS $$
  DECLARE
      obj record;
      cmd text;
  BEGIN
      FOR obj IN SELECT * FROM pg_event_trigger_ddl_commands()
      LOOP
          IF obj.command_tag = 'ALTER TABLE' THEN
              cmd := pg_event_trigger_ddl_commands();
              IF cmd ILIKE '%body%' OR cmd ILIKE '%content%' OR cmd ILIKE '%raw%' THEN
                  RAISE EXCEPTION 'Adding body/content columns to email tables is prohibited for privacy compliance';
              END IF;
          END IF;
      END LOOP;
  END;
  $$ LANGUAGE plpgsql;

  CREATE EVENT TRIGGER prevent_email_body_columns
  ON ddl_command_end
  WHEN TAG IN ('ALTER TABLE')
  EXECUTE FUNCTION prevent_body_columns();
  ```
  - Add downgrade to drop trigger

- [ ] **6.5** Run migration and verify
  - Run: `alembic upgrade head`
  - Verify tables created correctly
  - Test trigger: attempt to add body column (should fail)
  - Verify indexes exist
  - Check constraints work

- [ ] **6.6** Update metadata extraction task to store in database
  - Modify `process_gmail_history` task from Task 4.5
  - After extracting metadata, insert into `email_metadata` table
  - Use async database session
  - Handle duplicate message_id (upsert or skip)

**Success Criteria:**
- [ ] Migration runs successfully
- [ ] email_metadata table created with correct schema
- [ ] Trigger prevents body column additions
- [ ] Indexes improve query performance
- [ ] Metadata stored correctly after processing
- [ ] No email body content in database

---

## Task 7.0: Add Observability & Testing

**Goal:** Update health endpoint, add logging, and write comprehensive tests.

**Files to Create/Modify:**
- `app/api/health.py` (modify)
- `tests/security/test_no_body_storage.py` (new)
- `tests/classifier/test_tier1_accuracy.py` (new)
- `tests/integration/test_email_pipeline.py` (new)

### Sub-tasks:

- [ ] **7.1** Update health check endpoint
  - In `app/api/health.py`
  - Add metrics:
    - `gmail_watches_active`: count of active watch registrations
    - `last_webhook_received_at`: timestamp of most recent webhook
    - `celery_queue_length`: count of pending Celery tasks (query Redis)
    - `emails_processed_last_hour`: count from email_actions table
  - Add checks for Celery worker (ping task)
  - Return degraded status if any service unhealthy

- [ ] **7.2** Add Sentry error logging
  - In webhook endpoint: log invalid Pub/Sub messages
  - In metadata extraction: log Gmail API errors (401, 403, 429, 500)
  - In classification: log unexpected errors
  - Add context to Sentry events (mailbox_id, message_id, user_id)
  - Set up Sentry in `app/main.py` if not already done

- [ ] **7.3** Write security tests
  - Create `tests/security/test_no_body_storage.py`
  - Test: `test_email_metadata_model_has_no_body_columns()`
    - Inspect EmailMetadata SQLAlchemy model
    - Assert no columns named: body, html_body, raw_content, full_message, raw, content
  - Test: `test_database_trigger_prevents_body_columns()`
    - Attempt to add body column via raw SQL
    - Assert raises exception
  - Test: `test_gmail_api_never_fetches_full_format()`
    - Mock Gmail API calls
    - Assert format='metadata' always used, never format='full' or format='raw'

- [ ] **7.4** Write classification accuracy tests
  - Create `tests/classifier/test_tier1_accuracy.py`
  - Test: `test_promotional_email_classified_as_trash()`
    - Mock metadata with CATEGORY_PROMOTIONS + List-Unsubscribe
    - Assert action = TRASH, confidence ≥ 0.85
  - Test: `test_personal_email_classified_as_keep()`
    - Mock metadata with CATEGORY_PERSONAL, no bulk headers
    - Assert action = KEEP
  - Test: `test_exception_keywords_override_classification()`
    - Mock promotional email with subject "Your Receipt"
    - Assert action = KEEP (exception keyword overrides)
  - Test: `test_starred_email_always_kept()`
    - Mock email with STARRED label
    - Assert action = KEEP regardless of other signals

- [ ] **7.5** Write integration test for full pipeline
  - Create `tests/integration/test_email_pipeline.py`
  - Test: `test_webhook_to_classification_flow()`
    - Mock Pub/Sub webhook request
    - Mock Gmail API history.list() and messages.get() responses
    - Post to /webhooks/gmail
    - Wait for Celery tasks to complete
    - Assert email_actions record created with correct classification
  - Use pytest fixtures for database setup/teardown

- [ ] **7.6** Perform manual end-to-end testing
  - Connect test Gmail account (sebastianames3@gmail.com)
  - Register Gmail watch for test mailbox
  - Send test emails:
    - Promotional email (Old Navy, Groupon, etc.)
    - Personal email from real contact
    - Email with exception keyword ("Invoice attached")
    - Starred email
  - Verify webhook received
  - Check Railway logs for processing flow
  - Query email_actions table to verify classifications
  - Validate accuracy (expect ≥80% correct classifications)

**Success Criteria:**
- [ ] Health endpoint returns all metrics correctly
- [ ] Sentry logs errors with full context
- [ ] All security tests pass
- [ ] All classification tests pass
- [ ] Integration test passes
- [ ] Manual testing shows ≥80% accuracy
- [ ] No email bodies stored in database (verified)

---

## Execution Checklist

### Pre-Execution
- [ ] Create feature branch: `git checkout -b feature/email-processing-pipeline`
- [ ] Verify Railway has Redis service provisioned
- [ ] Verify all environment variables set (REDIS_URL, GOOGLE_PROJECT_ID, etc.)

### During Execution
- [ ] Complete each sub-task sequentially
- [ ] Get user approval after each sub-task
- [ ] Run relevant tests after each parent task
- [ ] Commit after each parent task with descriptive message

### Post-Execution
- [ ] Run full security test suite: `pytest tests/security/`
- [ ] Run all classifier tests: `pytest tests/classifier/`
- [ ] Run integration tests: `pytest tests/integration/`
- [ ] Verify Railway worker service deployed successfully
- [ ] Check health endpoint shows all services healthy
- [ ] Perform manual end-to-end test on real Gmail
- [ ] Create pull request with comprehensive description
- [ ] Wait for Railway preview deployment
- [ ] Merge PR after review
- [ ] Verify production deployment succeeds
- [ ] Monitor Sentry for errors (24 hours)

---

## Notes

**Estimated Time:** 8-12 hours (spread over 2-3 days)

**Critical Security Checks:**
- Never use `format='full'` or `format='raw'` with Gmail API
- Never add body columns to database tables
- Always encrypt OAuth tokens before storage
- Never log sensitive data (tokens, full headers, email content)

**Testing Priority:**
1. Security tests (MUST pass before merge)
2. Classification accuracy tests
3. Integration tests
4. Manual testing on real Gmail account

**Deployment Order:**
1. Deploy web service first (webhook endpoint)
2. Deploy worker service second (task processing)
3. Verify health checks pass
4. Monitor logs for errors

---

**Status:** ✅ Ready for Task 1.1 Execution
