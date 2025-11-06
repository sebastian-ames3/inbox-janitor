# PRD 0004: Action Execution Engine

**Status:** Draft
**Created:** 2025-11-05
**Author:** Claude (AI Assistant)

---

## 1. Introduction/Overview

Inbox Janitor currently has OAuth, database models, and a web portal UI, but it doesn't actually process emails yet. This PRD defines the core email processing pipeline: fetching emails from Gmail, classifying them using metadata and AI, and executing actions (trash, archive, keep) with safety rails and undo capabilities.

**Problem:** The app authenticates users but provides no value - it doesn't clean inboxes or automate email management.

**Goal:** Build the complete action execution engine that safely processes emails, reducing inbox clutter while preserving important messages.

---

## 2. Goals

1. **Fetch emails from Gmail** via Gmail API with proper pagination and rate limiting
2. **Classify emails accurately** using metadata-first approach (>90% confidence before AI fallback)
3. **Execute safe actions** (trash promotional spam, archive receipts, keep important emails)
4. **Auto-label archived emails** by document type (Receipt, Invoice, Research, etc.) for easy retrieval
5. **Provide complete undo capability** with 30-day recovery window
6. **Run in sandbox mode first** to validate classification accuracy before enabling actions
7. **Process backlog emails** (opt-in bulk cleanup for thousands of old promotional emails)
8. **Log all decisions** in immutable audit trail for transparency and learning

---

## 3. User Stories

**As a user with 34,000 promotional emails:**
- I want the app to classify each email as trash (ads), archive (receipts), or keep (important)
- I want old promotional emails automatically trashed to clean my inbox
- I want receipts and invoices archived with labels so I can find them for taxes
- I want important emails (job offers, bills) to never be touched by automation
- I want to review "uncertain" emails before action is taken

**As a privacy-conscious user:**
- I want the app to only read email metadata (subject, sender, headers) and minimal snippets
- I want full email bodies to never be stored in the database
- I want all my OAuth tokens encrypted
- I want to see exactly what the app did and why

**As a cautious user:**
- I want to test classification accuracy in sandbox mode before enabling real actions
- I want a 30-day undo window for any automated action
- I want starred emails and contacts to never be touched
- I want to manually approve backlog cleanup before it runs

---

## 4. Functional Requirements

### 4.1 Gmail API Integration

**FR-1:** Fetch emails from Gmail API using `users.messages.list()` with pagination
- Support `maxResults` parameter (default 100 emails per page)
- Handle `nextPageToken` for large mailboxes
- Filter by `labelIds`: `['INBOX', 'CATEGORY_PROMOTIONS']` for promotional emails
- Filter by `q` query parameter: `newer_than:7d` for recent emails

**FR-2:** Fetch individual message metadata using `users.messages.get()` with `format=metadata`
- Extract headers: `From`, `Subject`, `List-Unsubscribe`, `Precedence`, `Auto-Submitted`
- Extract labels: `CATEGORY_PROMOTIONS`, `STARRED`, `IMPORTANT`, `UNREAD`
- Extract snippet (first 200 characters only, no full body)
- Extract `internalDate` (timestamp)

**FR-3:** Implement rate limiting to respect Gmail API quotas
- 250 quota units per user per second
- `messages.list()` = 5 units, `messages.get()` = 5 units, `messages.modify()` = 5 units
- Exponential backoff on 429 (quota exceeded) errors
- Default limit: 10 emails processed per minute per user (configurable in settings)

**FR-4:** Handle Gmail API errors gracefully
- 401 Unauthorized → Refresh OAuth token, retry once
- 403 Forbidden → Log error, pause user's mailbox, notify user to reconnect
- 429 Quota Exceeded → Exponential backoff (1s, 2s, 4s, 8s, 16s max)
- 500/503 Server Error → Retry with exponential backoff (max 3 retries)

### 4.2 Email Classification Engine

**FR-5:** Implement metadata-first classification (Tier 1)

Classify as **TRASH** if ANY of:
- `CATEGORY_PROMOTIONS` label + `List-Unsubscribe` header present (confidence: 0.90)
- `Precedence: bulk` or `Auto-Submitted: auto-generated` header (confidence: 0.85)
- Sender domain in marketing platform list (sendgrid.net, mailchimp.com, etc.) (confidence: 0.80)
- Subject contains promotional patterns: `%`, `off`, `sale`, `limited time`, `act now`, emojis (confidence: 0.75)
- Sender open rate <5% (user never reads emails from this sender) (confidence: 0.85)

Classify as **ARCHIVE** if ANY of:
- Subject contains keywords: `receipt`, `invoice`, `order`, `booking`, `confirmation`, `shipped`, `tracking` (confidence: 0.90)
- `CATEGORY_UPDATES` label + transactional sender (Amazon, Uber, airlines) (confidence: 0.85)
- Financial sender domains: banks, PayPal, Stripe, Venmo (confidence: 0.90)

Classify as **KEEP** if ANY of:
- `STARRED` label present (confidence: 1.0)
- `IMPORTANT` label present (confidence: 0.95)
- Sender in user's contacts/address book (confidence: 0.95)
- Subject contains critical keywords: `interview`, `job`, `offer`, `medical`, `urgent`, `tax`, `legal` (confidence: 1.0)
- Email age <3 days (confidence: 0.70, recency bias for safety)
- `CATEGORY_PERSONAL` label (confidence: 0.90)

**FR-6:** Implement AI classification (Tier 2) - only if metadata confidence <0.90

Call OpenAI GPT-4o-mini with prompt:
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

- Only send minimal data (no full email body)
- Cache AI responses by sender domain + subject pattern to reduce API costs
- Cost tracking: Log OpenAI API usage per user

**FR-7:** Implement classification decision logic

```python
def classify_email(email_metadata):
    # Try metadata first
    metadata_result = classify_metadata(email_metadata)

    if metadata_result.confidence >= 0.90:
        return metadata_result  # High confidence, skip AI

    # Check exception keywords (override even low confidence)
    if has_critical_keywords(email_metadata.subject):
        return ClassificationResult(action='keep', confidence=1.0, reason='Critical keyword detected')

    # Fall back to AI
    ai_result = classify_with_ai(email_metadata)

    # Combine metadata + AI (weighted average)
    final_confidence = (metadata_result.confidence * 0.4) + (ai_result.confidence * 0.6)

    # Require high threshold for trash action
    if ai_result.action == 'trash' and final_confidence < 0.85:
        return ClassificationResult(action='review', confidence=final_confidence, reason='Low confidence, needs review')

    return ai_result
```

**FR-8:** Classify emails into review queue if confidence <0.85 for trash or <0.70 for archive
- Store in `email_actions` table with `action='review'`
- Show in weekly digest for manual user decision
- User can click "Archive" or "Trash" or "Keep" in digest email

### 4.3 Action Execution

**FR-9:** Implement sandbox mode (default for new users)
- Classification runs normally
- Decisions logged in `email_actions` table
- NO Gmail API modification calls executed
- User sees "what would happen" in audit log UI
- Setting: `action_mode_enabled = false` (default)

**FR-10:** Implement action mode (opt-in after sandbox validation)
- User enables via web portal settings toggle
- Shows warning: "Action mode will modify emails in Gmail. You have 30 days to undo. Continue?"
- Requires confirmation click
- Setting: `action_mode_enabled = true`

**FR-11:** Execute TRASH action via Gmail API
```python
def trash_email(message_id):
    service.users().messages().trash(
        userId='me',
        id=message_id
    ).execute()

    # Result: Email gets TRASH label, auto-deletes after 30 days
    # User can recover from Gmail Trash within 30 days
```

**FR-12:** Execute ARCHIVE action via Gmail API
```python
def archive_email(message_id):
    service.users().messages().modify(
        userId='me',
        id=message_id,
        body={'removeLabelIds': ['INBOX']}
    ).execute()

    # Result: Email removed from inbox (all tabs), still in All Mail
```

**FR-13:** Execute KEEP action (no-op)
- Log decision in `email_actions` table with `action='keep'`
- No Gmail API call needed
- Email remains in inbox unchanged

**FR-14:** NEVER implement permanent delete
- Do NOT use `users.messages.delete()` API method
- Trash action uses `users.messages.trash()` only (30-day recovery window)
- Add code review check: Block PRs containing `.delete()` calls

### 4.4 Auto-Labeling for Archived Emails

**FR-15:** Detect document type when archiving emails with confidence >0.85

Document type detection rules:
- **Receipt** - Subject/snippet contains: "receipt", "your order", "purchase confirmation", "thank you for your order"
- **Invoice** - Subject/snippet contains: "invoice", "payment due", "bill", "statement"
- **Shipping** - Subject/snippet contains: "shipped", "tracking", "delivery", "out for delivery", "package"
- **Booking** - Subject/snippet contains: "reservation", "booking confirmed", "check-in", "itinerary", "ticket"
- **Financial** - Sender domain: banks, paypal.com, stripe.com, venmo.com, OR subject contains: "statement", "balance", "tax", "W-2", "1099"
- **Newsletter** - Subject/snippet contains: "newsletter", "digest", "weekly roundup", "this week", sender domain: substack.com, medium.com
- **Research** - Subject/snippet contains: "research", "analysis", "report", "market update", "analyst", "whitepaper"
- **Other** - Archived but no clear document type detected

**FR-16:** Create Gmail labels if they don't exist
```python
def ensure_label_exists(label_name):
    existing_labels = get_user_labels()

    if label_name not in existing_labels:
        service.users().labels().create(
            userId='me',
            body={
                'name': label_name,
                'labelListVisibility': 'labelShow',
                'messageListVisibility': 'show'
            }
        ).execute()
```

**FR-17:** Apply document type label when archiving
```python
def archive_with_label(message_id, document_type):
    # First, ensure label exists
    ensure_label_exists(document_type)

    # Get label ID
    label_id = get_label_id(document_type)

    # Archive + add document type label in one API call
    service.users().messages().modify(
        userId='me',
        id=message_id,
        body={
            'removeLabelIds': ['INBOX'],
            'addLabelIds': [label_id]
        }
    ).execute()
```

**FR-18:** Make auto-labeling optional in settings
- Setting: `auto_label_archived_emails` (boolean, default `true`)
- If disabled, archive action only removes INBOX label (no document type label added)
- User can toggle in web portal settings

**FR-19:** Log document type in audit trail
- `email_actions.classification_metadata` JSONB column stores:
  ```json
  {
    "document_type": "Receipt",
    "document_type_confidence": 0.92,
    "label_applied": "Receipts"
  }
  ```

### 4.5 Undo and Recovery

**FR-20:** Store original state before action in `email_actions` table
```sql
CREATE TABLE email_actions (
    id UUID PRIMARY KEY,
    mailbox_id UUID REFERENCES mailboxes(id),
    message_id TEXT NOT NULL,  -- Gmail message ID
    from_address TEXT,
    subject TEXT,
    snippet TEXT,  -- First 200 chars only
    action TEXT NOT NULL,  -- 'keep' | 'archive' | 'trash' | 'review' | 'undo'
    reason TEXT,  -- Classification reason
    confidence FLOAT,
    original_label_ids TEXT[],  -- Labels before action (for undo)
    classification_metadata JSONB,  -- Metadata + AI signals
    created_at TIMESTAMPTZ DEFAULT NOW(),
    undone_at TIMESTAMPTZ,
    can_undo_until TIMESTAMPTZ  -- 30 days from action
);
```

**FR-21:** Implement undo action via Gmail API
```python
def undo_action(email_action_id):
    action = db.query(EmailAction).filter_by(id=email_action_id).first()

    if action.can_undo_until < datetime.utcnow():
        raise UndoExpiredError("Undo window expired (30 days)")

    # Restore original labels
    if action.action == 'trash':
        # Remove from trash, restore to inbox
        service.users().messages().untrash(
            userId='me',
            id=action.message_id
        ).execute()

    elif action.action == 'archive':
        # Re-add INBOX label
        service.users().messages().modify(
            userId='me',
            id=action.message_id,
            body={'addLabelIds': ['INBOX']}
        ).execute()

    # Log undo action
    action.undone_at = datetime.utcnow()
    db.commit()

    # Create new email_action record
    EmailAction(
        mailbox_id=action.mailbox_id,
        message_id=action.message_id,
        action='undo',
        reason=f"User undid {action.action} action",
        created_at=datetime.utcnow()
    )
```

**FR-22:** Provide undo links in weekly digest email
- Show borderline decisions: "We archived 15 emails this week. Not sure about these 3?"
- Each email has "Undo" magic link
- Magic link format: `https://app.inboxjanitor.com/undo/{jwt_token}`
- JWT token contains: `{email_action_id, user_id, exp: 24h}`

**FR-23:** Show undo capability in audit log UI
- Display "Undo" button for actions <30 days old
- After 30 days, show "Cannot undo (expired)"
- After Gmail auto-deletes trashed emails (30 days), show "Permanently deleted by Gmail"

### 4.6 Backlog Cleanup

**FR-24:** Analyze backlog on first OAuth connection
- Count emails by category and age:
  ```python
  {
    "total_inbox": 20287,
    "promotions": 33927,
    "social": 4346,
    "updates": 20408,
    "promotions_older_than_90_days": 28000,
    "promotions_older_than_30_days": 32000
  }
  ```

**FR-25:** Send backlog cleanup email (opt-in prompt)
```
Subject: Inbox Janitor found 33,927 promotional emails

Hi Sebastian,

We analyzed your Gmail and found:
- 33,927 promotional emails (ads, marketing, re-engagement)
- 28,000 are older than 90 days
- Estimated cleanup time: 2-3 hours (we'll send progress updates)

Want us to clean them up?
[Yes, clean up old promotions] [No, just handle new emails]

Settings:
- Emails older than [90] days → Trash
- Receipts/invoices → Archive with labels (not trashed)
- Important emails (starred, contacts) → Keep (never touched)

You can undo any action within 30 days.
```

**FR-26:** Process backlog in batches with progress emails
- Batch size: 100 emails per Celery task
- Send progress email every 1,000 emails processed
- Rate limit: 10 emails/min (avoid Gmail quota issues)
- Estimated time for 33,000 emails: ~55 hours (spread over days)

**FR-27:** Make backlog age threshold configurable in settings
- Setting: `backlog_cleanup_age_days` (integer, default 90)
- User can adjust: 30, 60, 90, 180, 365 days
- Only applies to backlog cleanup, not ongoing classification

**FR-28:** Apply same classification rules to backlog emails
- Metadata-first classification
- AI fallback if needed
- Safety rails (starred, contacts, keywords)
- Archive receipts with document type labels
- Trash promotional spam

### 4.7 Background Job Processing

**FR-29:** Implement Celery task for email processing
```python
@celery.task
def process_mailbox(mailbox_id, mode='recent'):
    """
    mode: 'recent' (last 7 days) | 'backlog' (all old emails)
    """
    mailbox = db.query(Mailbox).filter_by(id=mailbox_id).first()

    if mode == 'recent':
        query = 'in:inbox category:promotions newer_than:7d'
        max_emails = 500
    else:  # backlog
        query = 'in:inbox category:promotions older_than:90d'
        max_emails = 100  # Process in batches

    emails = fetch_emails(mailbox, query, max_emails)

    for email in emails:
        classify_and_execute(mailbox, email)
```

**FR-30:** Implement polling-based scheduler (Celery Beat)
```python
celery.conf.beat_schedule = {
    'process-recent-emails': {
        'task': 'app.tasks.process_recent_emails',
        'schedule': crontab(minute='*/10')  # Every 10 minutes
    }
}
```

**FR-31:** Process new emails every 10 minutes
- Fetch emails from last 7 days with `newer_than:7d`
- Skip already-processed emails (check `email_actions` table for existing `message_id`)
- Process only new/unprocessed emails

### 4.8 Safety Rails

**FR-32:** NEVER touch starred emails
- If `STARRED` label present, classify as `keep` with confidence 1.0
- Log reason: "Starred by user"
- No Gmail API action

**FR-33:** NEVER touch emails from contacts
- Fetch user's contacts via Google People API
- Cache contact email addresses in Redis (24-hour TTL)
- If sender in contacts, classify as `keep` with confidence 0.95

**FR-34:** NEVER touch emails with critical keywords
```python
CRITICAL_KEYWORDS = [
    'interview', 'job', 'offer', 'employment',
    'medical', 'health', 'doctor', 'prescription',
    'urgent', 'important', 'action required',
    'tax', 'irs', '1099', 'w-2', 'w2',
    'legal', 'court', 'lawsuit', 'subpoena',
    'bank', 'fraud', 'security alert', 'password reset'
]

def has_critical_keywords(subject, snippet):
    text = f"{subject} {snippet}".lower()
    return any(keyword in text for keyword in CRITICAL_KEYWORDS)
```

**FR-35:** NEVER touch recent emails (<3 days old) with low confidence
- If email age <3 days AND confidence <0.85, classify as `review`
- Gives user time to see important emails before automation

**FR-36:** Implement emergency stop mechanism
- User can email `stop@inboxjanitor.com` to immediately pause processing
- Webhook receives email, sets Redis flag: `emergency_stop:{user_id} = 1`
- All Celery tasks check flag before processing, abort if set
- User gets confirmation email: "Processing paused. Re-enable in settings."

### 4.9 Audit Logging

**FR-37:** Log ALL classification decisions in `email_actions` table
- Even `keep` actions (no Gmail modification) are logged
- Immutable append-only log (UPDATE/DELETE triggers block modifications)
- Retention: 30 days (then archive to S3)

**FR-38:** Store classification signals in `classification_metadata` JSONB column
```json
{
  "metadata_signals": {
    "has_unsubscribe": true,
    "gmail_category": "CATEGORY_PROMOTIONS",
    "sender_open_rate": 0.02,
    "subject_has_promo_pattern": true
  },
  "metadata_confidence": 0.92,
  "ai_used": false,
  "ai_response": null,
  "document_type": "Receipt",
  "document_type_confidence": 0.88,
  "label_applied": "Receipts"
}
```

**FR-39:** Display audit log in web portal
- Show recent 100 actions (paginated)
- Filters: action type (trash/archive/keep), date range, sender
- Search by sender or subject
- Download CSV export

---

## 5. Non-Goals (Out of Scope)

1. **Microsoft 365 integration** - Gmail only for MVP
2. **Reply-to-configure commands** - Requires email parsing, add in V1
3. **Per-sender user rules** - Block/allow lists add in V1 after learning system
4. **Real-time Gmail webhooks (Pub/Sub)** - Polling is simpler for MVP, upgrade later
5. **Follow-up detection** - "No reply in 7 days" is V2 feature
6. **Thread summarization** - V2 feature
7. **Mobile app** - Web portal only for MVP
8. **Multi-account support** - Single Gmail account for MVP
9. **Custom label prefix** - No "Janitor/" prefix for MVP, add setting later if requested
10. **Scheduled backlog cleanup** - Manual opt-in only for MVP, no recurring auto-cleanup

---

## 6. Design Considerations

### 6.1 Classification Accuracy Targets

**Target Metrics:**
- Overall accuracy: >95% (correct classification)
- False positive rate (important email marked trash): <0.1% (1 in 1000)
- False negative rate (spam marked keep): <5% (acceptable, user can manually trash)
- AI usage rate: ~30% of emails (70% classified by metadata alone)

**How to measure:**
- User manually reviews 100 decisions in sandbox mode
- Track undo rate (target <1% = high quality)
- Compare classifications to user's manual decisions over 1 week

### 6.2 Cost Estimation

**OpenAI API costs (100 emails/day, 30% use AI):**
- 30 emails × $0.003/call = $0.09/day
- $2.70/month per user

**Gmail API quota (100 emails/day):**
- Fetch list: 1 call × 5 units = 5
- Fetch metadata: 100 calls × 5 units = 500
- Modify emails: 50 calls × 5 units = 250
- Total: 755 units/day (well under 10,000/day free quota)

**Backlog cleanup (33,000 emails one-time):**
- OpenAI: 10,000 emails × $0.003 = $30 (one-time)
- Gmail API: Within quota if spread over days

### 6.3 User Settings Schema

```sql
CREATE TABLE user_settings (
    user_id UUID PRIMARY KEY REFERENCES users(id),

    -- Classification thresholds
    confidence_auto_threshold FLOAT DEFAULT 0.85,
    confidence_review_threshold FLOAT DEFAULT 0.70,

    -- Action mode
    action_mode_enabled BOOLEAN DEFAULT false,
    auto_trash_promotions BOOLEAN DEFAULT true,
    auto_archive_updates BOOLEAN DEFAULT false,

    -- Auto-labeling
    auto_label_archived_emails BOOLEAN DEFAULT true,

    -- Backlog cleanup
    backlog_cleanup_enabled BOOLEAN DEFAULT false,
    backlog_cleanup_age_days INTEGER DEFAULT 90,

    -- Digest emails
    digest_schedule TEXT DEFAULT 'weekly',  -- 'daily' | 'weekly' | 'off'

    -- Future: User rules
    blocked_senders TEXT[] DEFAULT '{}',
    allowed_domains TEXT[] DEFAULT '{}'
);
```

### 6.4 Gmail API Permissions Required

**OAuth Scopes:**
```
https://www.googleapis.com/auth/gmail.modify
https://www.googleapis.com/auth/gmail.labels
https://www.googleapis.com/auth/contacts.readonly
```

**NOT using:**
- `gmail.readonly` - Too limited, can't modify emails
- `gmail.compose` - Don't need to send emails
- `gmail.send` - Don't need to send emails
- **NEVER use permanent delete** - Only trash (reversible)

---

## 7. Technical Considerations

### 7.1 Database Indexes for Performance

```sql
-- Fast lookup: Has this email been processed?
CREATE INDEX idx_email_actions_message_id ON email_actions(message_id);

-- Fast lookup: User's recent actions (audit log)
CREATE INDEX idx_email_actions_mailbox_created ON email_actions(mailbox_id, created_at DESC);

-- Fast lookup: Undo-eligible actions
CREATE INDEX idx_email_actions_undo ON email_actions(can_undo_until) WHERE undone_at IS NULL;

-- Fast lookup: Sender stats
CREATE INDEX idx_sender_stats_lookup ON sender_stats(user_id, sender_address);
```

### 7.2 Redis Caching Strategy

**Cache Keys:**
```python
# Contact list (24-hour TTL)
f"contacts:{user_id}" → Set[email_addresses]

# Sender open rate (7-day TTL)
f"sender_stats:{user_id}:{sender_address}" → {"open_rate": 0.05, "total": 200}

# AI classification (30-day TTL, keyed by sender + subject pattern)
f"ai_classification:{sender_domain}:{subject_pattern_hash}" → {"action": "trash", "confidence": 0.92}

# Emergency stop flag (no TTL, user must manually clear)
f"emergency_stop:{user_id}" → "1"
```

### 7.3 Celery Task Retries

```python
@celery.task(
    bind=True,
    max_retries=3,
    default_retry_delay=60,  # 1 minute
    autoretry_for=(GmailAPIError, OpenAIAPIError)
)
def process_mailbox(self, mailbox_id):
    try:
        # Process emails
    except GmailQuotaExceeded as exc:
        # Exponential backoff for quota errors
        raise self.retry(exc=exc, countdown=60 * (2 ** self.request.retries))
```

### 7.4 Monitoring and Alerts

**Metrics to track:**
- Classification decisions per hour (detect processing stalls)
- AI usage rate (cost monitoring)
- Undo rate (quality metric - alert if >5%)
- Gmail API errors (alert if >10 per hour)
- Processing lag (alert if >1 hour behind)

**Sentry integration:**
- Log all classification errors
- Log Gmail API 403/429 errors
- Log OpenAI API failures

---

## 8. Success Metrics

**MVP Success Criteria (Week 1 - Sandbox Mode):**
- [ ] Fetch and classify 1,000 emails from user's own Gmail
- [ ] Classification accuracy >95% (manual review)
- [ ] Zero false positives on important emails (job offers, bills, personal)
- [ ] AI fallback working (<30% of emails need AI)
- [ ] Audit log shows all decisions with clear reasoning

**Week 2 - Action Mode:**
- [ ] User enables action mode after sandbox validation
- [ ] 100 emails processed with real Gmail actions (trash/archive)
- [ ] Zero unintended deletions
- [ ] Undo flow tested and working
- [ ] Auto-labeling creates correct labels (Receipt, Invoice, etc.)

**Week 3 - Backlog Cleanup:**
- [ ] User opts into backlog cleanup via email
- [ ] 1,000+ old promotional emails processed
- [ ] Inbox count reduced significantly
- [ ] Progress emails sent during processing
- [ ] User satisfied with results (<1% undo rate)

**Production Ready (Week 4):**
- [ ] 7 days of continuous action mode without issues
- [ ] Undo rate <1% (indicates high quality)
- [ ] No Gmail API quota issues
- [ ] No classification errors in logs
- [ ] User ready to recommend to friends/family

---

## 9. Open Questions

1. **Should we implement quarantine labels before trashing?**
   - Option A: Trash immediately (Gmail's 30-day recovery is sufficient)
   - Option B: Move to "Quarantine" label for 7 days, THEN trash (extra safety = 37 days total)
   - **Decision needed:** User preference (A is simpler, B is safer)

2. **Should backlog cleanup run automatically on schedule?**
   - Option A: One-time opt-in only (safer for MVP)
   - Option B: Weekly auto-cleanup of emails older than threshold (higher velocity)
   - **Decision:** Start with A, add B in settings later

3. **Should we show classification confidence scores to users?**
   - Option A: Show in audit log UI ("Confidence: 92%")
   - Option B: Hide scores, only show reason
   - **Decision:** A (transparency builds trust)

4. **Should we fetch contacts on every classification or cache?**
   - Option A: Fetch once per day, cache in Redis (faster, slight staleness)
   - Option B: Fetch on-demand per email (slower, always fresh)
   - **Decision:** A (contacts change rarely)

5. **Should we apply document type labels to emails that are already archived (before app existed)?**
   - Option A: Yes, scan All Mail and retroactively label receipts/invoices
   - Option B: No, only label new archived emails going forward
   - **Decision needed:** A adds value but increases complexity

---

## 10. Implementation Plan (High-Level Phases)

### Phase 1: Foundation (Week 1, PRs #1-3)
**Goal:** Fetch emails and classify in sandbox mode (no actions yet)

**PR #1: Gmail API Integration**
- OAuth scope verification
- Fetch emails with pagination
- Rate limiting middleware
- Error handling and retries
- Unit tests

**PR #2: Metadata Classification**
- Implement Tier 1 classification (metadata signals)
- Exception keywords safety rails
- Sender stats tracking
- Log decisions in `email_actions` table
- Security tests (no body storage)

**PR #3: AI Classification**
- OpenAI API integration
- Tier 2 classification (AI fallback)
- Response caching
- Cost tracking
- Combine metadata + AI confidence

**Validation:** Run on user's own Gmail in sandbox mode, review 100 decisions

---

### Phase 2: Action Execution (Week 2, PRs #4-6)

**PR #4: Archive/Trash Actions**
- Action mode toggle in settings
- Gmail API modify/trash calls
- Undo action implementation
- Store original state before action
- Safety tests (no permanent delete)

**PR #5: Auto-Labeling**
- Document type detection
- Gmail label creation
- Apply labels when archiving
- Setting toggle for auto-labeling
- E2E tests for labeled emails

**PR #6: Audit Log UI**
- Display email_actions in web portal
- Pagination and filters
- Undo button (magic links)
- CSV export
- E2E tests

**Validation:** Enable action mode on 100 test emails, verify undo works

---

### Phase 3: Backlog Cleanup (Week 3, PRs #7-8)

**PR #7: Backlog Analysis**
- Count emails by category and age
- Send opt-in email with analysis
- Magic link to approve cleanup
- Settings for age threshold

**PR #8: Batch Processing**
- Celery task for backlog processing
- Progress email every 1,000 emails
- Rate limiting (10 emails/min)
- Pause/resume capability

**Validation:** Run on user's 33,000 promotional emails, monitor progress

---

### Phase 4: Polish & Production (Week 4, PRs #9-10)

**PR #9: Weekly Digest Email**
- Template with summary (emails processed, undo links)
- Borderline cases for review
- Magic links for actions
- Postmark integration

**PR #10: Monitoring & Alerts**
- Sentry error tracking
- Custom alerts (high undo rate, API errors)
- Health check endpoint updates
- Documentation updates

**Validation:** 7 days of continuous production use, <1% undo rate

---

**Estimated Timeline:** 4 weeks (3-4 PRs per week, ~12 total PRs)

**Next Steps:** Create task list from this PRD using `generate-tasks.md` skill

---

## 11. Dependencies

**External APIs:**
- Gmail API (Google Cloud project already configured)
- OpenAI API (GPT-4o-mini)
- Google People API (for contacts)

**Internal Systems:**
- PostgreSQL (email_actions table, user_settings table)
- Redis (caching, rate limiting)
- Celery (background jobs)
- Postmark (progress emails, digest emails)

**Security Requirements:**
- All OAuth tokens encrypted (Fernet)
- No email bodies stored in database
- All actions logged in immutable audit trail
- CSRF protection on settings forms
- Rate limiting on API endpoints

---

**Status:** Ready for task generation → Use `@ai-dev-tasks/generate-tasks.md` to break down into actionable tasks
