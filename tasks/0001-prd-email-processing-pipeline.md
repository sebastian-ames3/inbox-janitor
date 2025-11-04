# PRD: Week 1 Core - Email Processing Pipeline

**PRD Number:** 0001
**Feature Name:** Email Processing Pipeline
**Status:** Draft
**Created:** 2025-11-04
**Owner:** Sebastian Ames

---

## Introduction/Overview

This feature establishes the core email processing pipeline for Inbox Janitor, enabling real-time email ingestion, metadata extraction, and intelligent classification. When a user receives a new email in Gmail, the system will automatically detect it, extract relevant metadata (headers, category, sender info), and classify it using rule-based signals (Tier 1 classification). This forms the foundation for Week 2's automated actions (archive/trash).

**Problem it solves:** Users currently have no automated way to process incoming emails. This pipeline enables real-time awareness of new mail and intelligent categorization without requiring manual intervention.

**Goal:** Build a reliable, secure, and scalable email processing pipeline that handles Gmail emails in real-time, extracts metadata without storing sensitive content, and classifies emails with 80%+ accuracy using metadata signals only.

---

## Goals

1. **Real-time Email Detection:** Receive webhook notifications within 30 seconds of email arrival
2. **Secure Metadata Extraction:** Fetch email headers, category, and sender info without storing full body content
3. **Tier 1 Classification:** Achieve 80%+ classification accuracy using metadata signals only (no AI/LLM)
4. **Background Processing:** Process emails asynchronously via Celery to avoid blocking the web service
5. **Security-First Design:** Ensure no email bodies are stored in the database, all tokens remain encrypted
6. **Sandbox Mode:** Log all classifications without taking Gmail actions (safe testing)

---

## User Stories

1. **As a beta tester**, I want the system to detect new emails immediately after they arrive, so I can see near-instant processing without manual triggers.

2. **As a privacy-conscious user**, I want the system to analyze my emails without storing the full content, so my private conversations remain secure.

3. **As a Gmail user with promotional overload**, I want the system to automatically identify marketing emails using Gmail's category labels and unsubscribe headers, so it can distinguish spam from important mail.

4. **As the developer**, I want all email processing to happen in background jobs, so the web API remains fast and responsive even during high email volume.

5. **As a security-focused founder**, I want all classifications logged to an immutable audit table, so I can review decisions and debug issues without compromising user privacy.

---

## Functional Requirements

### 1. Gmail Watch + Pub/Sub Setup

**FR-1.1:** The system MUST register Gmail Push Notifications using the Gmail API `watch()` method for each connected mailbox.

**FR-1.2:** Gmail watch registrations MUST renew every 6 days (watches expire after 7 days) via a Celery beat scheduled task.

**FR-1.3:** The system MUST create a Google Cloud Pub/Sub topic (e.g., `inbox-janitor-gmail-notifications`) to receive push notifications.

**FR-1.4:** The system MUST create a Pub/Sub subscription with a push endpoint pointing to Railway's web service (e.g., `https://inbox-janitor-production-03fc.up.railway.app/webhooks/gmail`).

**FR-1.5:** The webhook endpoint MUST verify Pub/Sub message authenticity (check `X-Goog-*` headers or use JWT verification if configured).

### 2. Webhook Receiver Endpoint

**FR-2.1:** Create a POST endpoint at `/webhooks/gmail` that receives Pub/Sub push notifications.

**FR-2.2:** The endpoint MUST decode the base64-encoded Pub/Sub message payload to extract `historyId` and `emailAddress`.

**FR-2.3:** The endpoint MUST validate that the `emailAddress` corresponds to an active mailbox in the database.

**FR-2.4:** The endpoint MUST enqueue a Celery task (`process_gmail_history`) with the mailbox ID and history ID.

**FR-2.5:** The endpoint MUST return `200 OK` immediately (within 10ms) to prevent Pub/Sub retries, even if task enqueueing fails.

**FR-2.6:** If task enqueueing fails, the endpoint MUST log the error to Sentry but still return `200 OK`.

### 3. Email Metadata Extraction

**FR-3.1:** Create a Celery task `process_gmail_history(mailbox_id, history_id)` that fetches new emails using Gmail API's `history.list()` method.

**FR-3.2:** The task MUST use the mailbox's `last_history_id` to fetch only delta changes (new emails, not full sync).

**FR-3.3:** For each new email, the task MUST call Gmail API `messages.get()` with `format=metadata` to fetch:
- `id` (Gmail message ID)
- `threadId`
- `labelIds` (Gmail labels including category)
- `payload.headers` (From, To, Subject, List-Unsubscribe, Precedence, Auto-Submitted, etc.)
- `snippet` (first ~200 characters, auto-provided by Gmail)
- `internalDate` (timestamp)

**FR-3.4:** The task MUST extract and parse the following headers from `payload.headers`:
- `From` (sender email and name)
- `Subject`
- `List-Unsubscribe` (if present)
- `Precedence` (bulk indicator)
- `Auto-Submitted` (auto-generated indicator)
- `X-Mailer`, `X-Campaign-ID`, or other marketing platform headers

**FR-3.5:** The task MUST determine the Gmail category from `labelIds`:
- `CATEGORY_PROMOTIONS` → Promotional
- `CATEGORY_SOCIAL` → Social network
- `CATEGORY_UPDATES` → Transactional updates
- `CATEGORY_FORUMS` → Forum/mailing list
- `CATEGORY_PERSONAL` → Personal (default if no category label)

**FR-3.6:** The task MUST extract the sender domain from the `From` header (e.g., `marketing@oldnavy.com` → `oldnavy.com`).

**FR-3.7:** The task MUST **NEVER** fetch `format=full` or `format=raw` (this would include email body content, violating privacy requirements).

### 4. Tier 1 Classification (Metadata Signals)

**FR-4.1:** Create a Celery task `classify_email_tier1(mailbox_id, message_id, metadata)` that runs rule-based classification.

**FR-4.2:** The classifier MUST implement the following signals with weighted confidence scoring:

#### Signal A: Gmail Category
- `CATEGORY_PROMOTIONS` → +0.60 confidence (trash)
- `CATEGORY_SOCIAL` → +0.50 confidence (trash)
- `CATEGORY_UPDATES` → +0.30 confidence (archive)
- `CATEGORY_FORUMS` → +0.20 confidence (archive)
- `CATEGORY_PERSONAL` → -0.30 confidence (keep)

#### Signal B: List-Unsubscribe Header
- If `List-Unsubscribe` header is present → +0.40 confidence (trash)
- Reasoning: Legal requirement for commercial email, 99% indicates marketing

#### Signal C: Bulk Mail Headers
- If `Precedence: bulk` header present → +0.35 confidence (trash)
- If `Auto-Submitted: auto-generated` present → +0.30 confidence (archive)
- If both present → +0.50 confidence (trash)

#### Signal E: Sender Domain Analysis
- If sender domain matches marketing platform patterns → +0.45 confidence (trash)
- Marketing platforms to detect:
  - `*.sendgrid.net`, `*.customeriomail.com`, `*.mailchimp.com`
  - `*.mcsv.net` (Mailchimp), `*.cmail*.com` (Campaign Monitor)
  - `*.em*.com` (generic email marketing patterns)
  - `*bounce*` or `*mail*` subdomains (e.g., `mail.company.com`)

**FR-4.3:** The classifier MUST aggregate confidence scores and determine action:
- Total confidence ≥ 0.85 → `trash` (high confidence marketing/spam)
- Total confidence 0.55-0.84 → `archive` (promotional but may have value)
- Total confidence 0.30-0.54 → `review` (uncertain, needs human review)
- Total confidence < 0.30 → `keep` (likely important)

**FR-4.4:** The classifier MUST implement exception keyword safety rails:
- If subject or snippet contains exception keywords, override to `keep` regardless of confidence
- Exception keywords: `receipt`, `invoice`, `order`, `payment`, `booking`, `reservation`, `ticket`, `shipped`, `tracking`, `password`, `security`, `tax`, `medical`, `bank`, `interview`, `job`
- Case-insensitive matching

**FR-4.5:** The classifier MUST implement starred email protection:
- If email has `STARRED` label → always `keep` (user manually starred it)

**FR-4.6:** The classifier MUST return a classification result containing:
- `action` (trash | archive | review | keep)
- `confidence` (float 0.0-1.0)
- `signals` (JSON object with each signal's contribution)
- `reason` (human-readable explanation, e.g., "CATEGORY_PROMOTIONS + List-Unsubscribe header")

### 5. Database Storage

**FR-5.1:** Create a table `email_metadata` (if not already in schema) with columns:
- `id` (UUID primary key)
- `mailbox_id` (foreign key to mailboxes)
- `message_id` (Gmail message ID, unique per mailbox)
- `thread_id` (Gmail thread ID)
- `from_address` (sender email)
- `from_name` (sender display name)
- `from_domain` (extracted domain)
- `subject` (email subject line, max 500 chars)
- `snippet` (first 200 chars, provided by Gmail API)
- `gmail_labels` (JSONB array of label IDs)
- `gmail_category` (text: promotional, social, updates, forums, personal, null)
- `headers` (JSONB object with extracted headers)
- `received_at` (timestamp from internalDate)
- `processed_at` (timestamp when processed)
- `created_at` (timestamp)

**FR-5.2:** The table MUST **NOT** include columns: `body`, `html_body`, `raw_content`, `full_message`, or any similar naming that suggests full email content storage.

**FR-5.3:** Create a database migration that adds a PostgreSQL trigger to prevent adding body-related columns:
```sql
CREATE OR REPLACE FUNCTION prevent_body_columns()
RETURNS event_trigger AS $$
DECLARE
    obj record;
BEGIN
    FOR obj IN SELECT * FROM pg_event_trigger_ddl_commands()
    LOOP
        IF obj.command_tag = 'ALTER TABLE' AND
           (obj.object_identity LIKE '%body%' OR
            obj.object_identity LIKE '%content%' OR
            obj.object_identity LIKE '%raw%')
        THEN
            RAISE EXCEPTION 'Adding body/content columns to email tables is prohibited';
        END IF;
    END LOOP;
END;
$$ LANGUAGE plpgsql;
```

**FR-5.4:** After classification, insert a row into `email_actions` table (from existing schema) with:
- `mailbox_id`
- `message_id`
- `from_address`
- `subject`
- `snippet`
- `action` (classification result)
- `reason` (explanation)
- `confidence` (score)
- `classification_metadata` (JSONB with signals)
- `created_at`

**FR-5.5:** Update the mailbox's `last_history_id` to the latest processed history ID (for delta sync).

### 6. Celery Background Queue Setup

**FR-6.1:** Create a separate Railway service named `inbox-janitor-worker` that runs Celery worker + beat scheduler.

**FR-6.2:** The worker service MUST use the same Docker image/codebase as the web service but with a different start command:
```bash
celery -A app.core.celery_app worker --loglevel=info --beat --scheduler=celery.beat:PersistentScheduler
```

**FR-6.3:** The worker service MUST connect to the same Redis instance as the web service (use `REDIS_URL` environment variable).

**FR-6.4:** The worker service MUST have access to the same environment variables as the web service (database, encryption keys, API credentials).

**FR-6.5:** Configure Celery beat schedule to run every 6 days:
```python
'renew-gmail-watches': {
    'task': 'app.tasks.ingest.renew_gmail_watches',
    'schedule': crontab(hour='3', minute='0', day_of_week='*/6')
}
```

**FR-6.6:** Create a fallback polling task that runs every 10 minutes to catch missed webhooks:
```python
'fallback-poll-gmail': {
    'task': 'app.tasks.ingest.fallback_poll_gmail',
    'schedule': crontab(minute='*/10')
}
```

### 7. Security Requirements

**FR-7.1:** The system MUST use encrypted OAuth tokens from the database to authenticate Gmail API calls (tokens already encrypted via Fernet in Week 0).

**FR-7.2:** The system MUST **NEVER** log:
- OAuth access tokens or refresh tokens
- Email body content
- Full email headers (only log specific extracted headers)
- User passwords (N/A for OAuth but document for future)

**FR-7.3:** All Gmail API calls MUST use exponential backoff with max 3 retries on rate limit errors (429 status).

**FR-7.4:** The system MUST implement per-user rate limiting: max 10 email processing tasks per minute per mailbox.

**FR-7.5:** If a mailbox's OAuth token is invalid (401/403 from Gmail API), the system MUST:
- Mark the mailbox as `is_active=false`
- Send an email to the user requesting re-authentication
- NOT retry the task (prevent infinite loops)

### 8. Observability

**FR-8.1:** Add metrics to the `/health` endpoint:
- `gmail_watches_active` (count of active watch registrations)
- `last_webhook_received_at` (timestamp of most recent webhook)
- `celery_queue_length` (number of pending tasks)
- `emails_processed_last_hour` (count)

**FR-8.2:** Log the following events to Sentry:
- Pub/Sub webhook failures (invalid payload, missing mailbox)
- Gmail API errors (quota exceeded, token expired, network errors)
- Classification errors (exception during signal calculation)
- Database errors (connection failures, constraint violations)

**FR-8.3:** Log the following info-level events to stdout (for Railway logs):
- Webhook received (mailbox ID, history ID)
- Email processed (message ID, classification result, processing time)
- Gmail watch renewed (mailbox ID, new expiration timestamp)

---

## Non-Goals (Out of Scope)

1. **Tier 2 AI Classification:** GPT-4o-mini classification is deferred to Week 2 (this PRD focuses on Tier 1 metadata-only)

2. **Gmail Actions:** No archive/trash actions will be performed in this phase. Classification results are logged only (sandbox mode).

3. **Undo Flow:** 7-day quarantine and 30-day undo are deferred to Week 2 (requires action mode first)

4. **User Settings:** Confidence thresholds are hardcoded for now. User-configurable settings come in Week 3+.

5. **Sender Stats Learning:** Tracking open rates and reply rates per sender is deferred to Week 4+.

6. **Microsoft 365 Support:** Gmail only for Week 1. M365 integration deferred to Week 9+.

7. **Email Sending:** No digest emails or notifications to users yet. Focus is on ingestion and classification only.

8. **Web Portal UI:** No frontend changes. All work is backend API and background jobs.

---

## Design Considerations

### Module Structure

Follow the modular monolith pattern defined in CLAUDE.md:

```
app/
├── modules/
│   ├── ingest/
│   │   ├── __init__.py
│   │   ├── gmail_watch.py       # Gmail watch registration/renewal
│   │   ├── webhook_handler.py   # POST /webhooks/gmail endpoint
│   │   └── metadata_extractor.py # Gmail API metadata fetching
│   ├── classifier/
│   │   ├── __init__.py
│   │   ├── tier1.py             # Metadata signal classification
│   │   └── signals.py           # Individual signal implementations
├── tasks/
│   ├── __init__.py
│   ├── ingest.py                # Celery tasks for email ingestion
│   └── classify.py              # Celery tasks for classification
├── models/
│   ├── email_metadata.py        # New model (if not in schema)
│   └── email_actions.py         # Existing model (append-only)
└── api/
    └── webhooks.py              # FastAPI router for /webhooks/*
```

### Gmail API Best Practices

- Use `format=metadata` to avoid fetching email bodies
- Use `history.list()` for delta sync (more efficient than full inbox scans)
- Implement exponential backoff on 429 rate limit errors
- Cache sender domain patterns in Redis (reduce repeated regex matching)

### Celery Task Patterns

- Keep tasks idempotent (safe to retry)
- Use `acks_late=True` to prevent message loss on worker crashes
- Set task timeouts (30 seconds for metadata extraction, 10 seconds for classification)
- Use task retries with exponential backoff

---

## Technical Considerations

### Dependencies

**New Python packages to add to `requirements.txt`:**
- `celery[redis]>=5.3.0` (task queue)
- `google-cloud-pubsub>=2.18.0` (Pub/Sub client for setup, optional if using push-only)

**Existing packages (already in project):**
- `google-auth`, `google-auth-oauthlib`, `google-api-python-client` (Gmail API)
- `redis>=5.0.0` (Celery broker)
- `asyncpg` (PostgreSQL async driver)
- `sqlalchemy[asyncio]` (ORM)

### Environment Variables

**New variables to add to Railway:**
- `REDIS_URL` (Celery broker, format: `redis://default:password@host:port`)
- `CELERY_BROKER_URL` (alias for REDIS_URL, optional)
- `GCP_PROJECT_ID` (for Pub/Sub setup, if using gcloud SDK)
- `PUBSUB_VERIFICATION_TOKEN` (optional, for webhook security)

**Existing variables (already configured):**
- `DATABASE_URL` (PostgreSQL connection string)
- `ENCRYPTION_KEY` (Fernet key for OAuth tokens)
- `GOOGLE_CLIENT_ID`, `GOOGLE_CLIENT_SECRET` (OAuth credentials)
- `SECRET_KEY` (JWT signing)

### Railway Deployment

**Two services required:**

1. **Web Service** (existing)
   - Start command: `uvicorn app.main:app --host 0.0.0.0 --port $PORT`
   - Handles HTTP traffic (webhooks, API endpoints)

2. **Worker Service** (new)
   - Start command: `celery -A app.core.celery_app worker --loglevel=info --beat`
   - Processes background jobs
   - Same codebase, different command
   - Needs all the same environment variables as web service

### Database Migration

**Create Alembic migration:** `002_email_metadata_and_triggers.py`

**Migration should:**
1. Create `email_metadata` table (if not already exists)
2. Add trigger to prevent body column additions
3. Add indexes:
   - `idx_email_metadata_mailbox_message` on `(mailbox_id, message_id)` (unique)
   - `idx_email_metadata_processed_at` on `(processed_at)` for cleanup queries
   - `idx_email_actions_mailbox_created` on `(mailbox_id, created_at)` for audit queries

### Google Cloud Pub/Sub Setup

**Manual setup required (document in Railway setup guide):**

1. Create GCP project (can reuse existing OAuth project)
2. Enable Cloud Pub/Sub API
3. Create topic: `inbox-janitor-gmail-notifications`
4. Create push subscription pointing to Railway webhook URL
5. Grant Gmail API permission to publish to topic (automatic when calling `watch()`)

**Alternative (simpler for MVP):** Use Gmail's built-in push notifications without Pub/Sub (register watch with `push` type, Gmail sends directly to webhook).

---

## Success Metrics

### Quantitative Metrics

1. **Real-time Performance:**
   - ✅ 95%+ of webhooks received within 30 seconds of email arrival
   - ✅ Webhook endpoint responds in <10ms (before task enqueueing)
   - ✅ Email metadata extraction completes in <2 seconds per email

2. **Classification Accuracy:**
   - ✅ Tier 1 classifier achieves ≥80% accuracy on test dataset (100+ emails)
   - ✅ Exception keywords prevent 0 false positive deletions (job offers, medical emails protected)
   - ✅ Starred emails always classified as `keep`

3. **Reliability:**
   - ✅ 0 database records contain email body content (verify with schema inspection)
   - ✅ 0 OAuth tokens logged in plaintext (verify with log audits)
   - ✅ Celery processes 100+ emails without failures
   - ✅ Gmail watches renew automatically before expiration

4. **System Health:**
   - ✅ `/health` endpoint shows all services green (database, Redis, Gmail API, Celery)
   - ✅ No Sentry errors for 24 hours of continuous operation
   - ✅ Railway deployment succeeds with 0 downtime

### Qualitative Metrics

1. **Developer Experience:**
   - ✅ Can manually trigger email processing via Celery CLI for testing
   - ✅ Railway logs clearly show email processing flow (webhook → task → classify → store)
   - ✅ Can query `email_actions` table to see classification history

2. **Security Validation:**
   - ✅ Code review confirms no `format=full` or `format=raw` Gmail API calls
   - ✅ PostgreSQL trigger blocks body column additions
   - ✅ All security tests pass (from testing-requirements.md skill)

---

## Open Questions

1. **Gmail Watch Renewal Strategy:**
   - Should we renew watches for inactive users (no login in 30+ days)? Or let them expire to save quota?
   - **Recommendation:** Renew only for active mailboxes (`is_active=true` and `last_used_at` within 30 days)

2. **Pub/Sub vs Direct Push:**
   - Should we use Google Cloud Pub/Sub (more complex setup) or Gmail's direct push (simpler but less reliable)?
   - **Recommendation:** Start with direct push for MVP, migrate to Pub/Sub if webhook reliability issues arise

3. **Fallback Polling Frequency:**
   - Is 10-minute polling sufficient to catch missed webhooks? Or should we poll more frequently?
   - **Recommendation:** Start with 10 minutes, monitor webhook miss rate, adjust if needed

4. **Classification Confidence Thresholds:**
   - Are the hardcoded thresholds (0.85 trash, 0.55 archive) optimal? Should we A/B test different values?
   - **Recommendation:** Start with these values, log all classifications for analysis, tune in Week 2 based on data

5. **Rate Limiting per User:**
   - Is 10 emails/min/user too conservative? Gmail API allows 250 quota units/user/second (1 email = ~5 units = ~50 emails/second theoretical max).
   - **Recommendation:** Start conservative (10/min), increase if processing lag occurs with normal usage

---

## Next Steps

1. **Review this PRD** with user (Sebastian) for approval
2. **Generate task list** using `@ai-dev-tasks/generate-tasks.md` skill
3. **Execute tasks** step-by-step with user review checkpoints
4. **Create feature branch** following git-workflow.md (`git checkout -b feature/email-processing-pipeline`)
5. **Security testing** before merge (run all tests from testing-requirements.md)
6. **Deploy to Railway** via pull request workflow
7. **Manual testing** on sebastianames3@gmail.com (sandbox mode)

---

**PRD Status:** ✅ Ready for Review
