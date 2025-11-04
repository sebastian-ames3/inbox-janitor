# Inbox Janitor - Development Context

**Last Updated:** 2025-10-25
**Status:** Pre-MVP Development
**Current Phase:** Week 1 - Foundation & Railway Deployment

---

## 🚨 CRITICAL GIT WORKFLOW RULE 🚨

**NEVER PUSH DIRECTLY TO MAIN BRANCH**

**REQUIRED workflow for ALL changes:**
1. Create feature branch: `git checkout -b feature/description`
2. Make changes and commit
3. Push feature branch: `git push -u origin feature/description`
4. Create pull request: `gh pr create ...`
5. WAIT for CI/CD checks to pass
6. WAIT for Railway deployment to succeed
7. User reviews and approves PR
8. Merge PR (only after all checks pass)

**No exceptions. All changes via pull requests.**

See `skills/git-workflow.md` for complete workflow.

---

## AI Dev Workflow Commands

When building new features, use this 3-step structured workflow for better control and reviewable progress:

### Step 1: Create PRD
```
I want to build [feature name].
Use @ai-dev-tasks/create-prd.md to create a PRD.

[Describe your feature here - be specific about problem, users, functionality]

Reference @CLAUDE.md for architecture context.
```

### Step 2: Generate Tasks
```
Take @tasks/[your-prd-file].md and create tasks using @ai-dev-tasks/generate-tasks.md
```

### Step 3: Execute Tasks (One at a Time)
```
Start on task 1.1 from the generated task list and work through it step-by-step.
After I review each sub-task, I'll say "yes" to continue or provide feedback.
```

**All PRDs and task lists save to `/tasks` directory.**

**When to use:** Complex features (>50 lines), multiple files, Week 1-6 roadmap items
**When NOT to use:** Bug fixes, single-line changes, documentation updates

---

## Claude Skills Reference

This project uses Claude Skills in `/skills/` for consistent development patterns.

**Core Skills:**
- **security-first.md** ⭐ CRITICAL - OAuth token encryption, no email body storage, no permanent deletion
- **fastapi-module-builder.md** - Modular monolith structure, database patterns, async sessions
- **email-classification.md** - 3-tier classification system, safety rails, exception keywords

**Workflow Skills:**
- **railway-deployment.md** - Environment variables, deployment verification, debugging failed deploys
- **testing-requirements.md** - Security tests (run before every commit), safety tests, coverage requirements
- **git-workflow.md** - Commit patterns, Railway verification, pull request workflow
- **ai-dev-workflow.md** - PRD → Tasks → Execute workflow for complex features

**How Skills Work:**
- Auto-triggered when relevant (creating modules → fastapi-module-builder.md)
- Explicitly invoke: "Using the security-first skill, add OAuth endpoint"
- Cross-referenced: Skills link to each other for related patterns

**See `/skills/README.md` for complete documentation.**

---

## Project Vision

**Headless email hygiene SaaS** that keeps important mail visible while automatically cleaning promotional spam. Privacy-first, email-only UX, reversible by design.

**Target Users:** Gmail users (MVP) → Microsoft 365 (V1) → Teams (V2)

**Key Differentiators:**
1. Email-first UX (no app required for daily use)
2. Backlog cleanup (instant value for 5K+ email inboxes)
3. Privacy-first (no email body storage, encrypted tokens)
4. Delete vs Archive distinction (trash spam, keep receipts)
5. Reversible automation (7-day quarantine, 30-day undo)

---

## Architecture Decisions

### Pattern: Modular Monolith (NOT Microservices)
**Rationale:** Solo founder velocity, shared DB transactions, lower costs, easier debugging.

**Structure:**
```
app/
├── core/           # Config, security, DB, Celery
├── modules/        # Domain modules (future "agents")
│   ├── auth/       # OAuth, token storage
│   ├── ingest/     # Webhooks, Gmail watch
│   ├── classifier/ # Metadata + AI classification
│   ├── executor/   # Actions, quarantine, undo
│   ├── digest/     # Email templates, magic links
│   ├── commands/   # Reply-to-configure (V1)
│   ├── billing/    # Stripe integration
│   └── analytics/  # Metrics, audit log
├── models/         # SQLAlchemy models
├── tasks/          # Celery background jobs
└── api/            # FastAPI routers
```

**Migration Path:**
- Week 0: Migrate from Google Apps Script
- Weeks 1-6: Build modular monolith
- Month 6+: Extract high-load modules if needed (1K+ users)

---

## Tech Stack

| Component | Choice | Rationale |
|-----------|--------|-----------|
| **Backend** | FastAPI | Already familiar, async support, auto docs |
| **Database** | PostgreSQL | Relational data, ACID transactions, JSON support |
| **Queue** | Celery + Redis | Self-hosted, rich features, proven at scale |
| **Email Send** | Postmark | Deliverability (99.8%), transactional focus, templates |
| **OAuth** | Authlib | Unified API for Gmail + M365, self-hosted |
| **Deployment** | Railway | Current platform, simple, good DX |
| **Encryption** | Fernet (symmetric) | Fast, secure, rotate to KMS at 500+ users |
| **Monitoring** | Sentry.io (free tier) | Error tracking, critical for debugging |

**Cost (Beta, 50 users):**
- Railway (web + worker + Postgres + Redis): $20/mo
- Postmark (10K emails): $15/mo
- OpenAI API (3K classifications): $10/mo
- Domain: $1/mo
- **Total: $46/mo**

---

## Security Architecture

### Critical Risks & Mitigations

**Risk 1: OAuth Token Theft** (CATASTROPHIC)
- **Mitigation:** Fernet encryption, keys in env vars, never log tokens, rotation on breach
- **Testing:** `test_token_encryption()`, `test_token_not_in_logs()`, `test_sql_injection()`
- **Monitoring:** Multi-IP usage, unusual activity, auto-revoke on anomaly

**Risk 2: Accidental Email Deletion** (SEVERE)
- **Mitigation:** NEVER call `.delete()`, 7-day quarantine, 30-day undo, all actions logged
- **Testing:** `test_archive_not_delete()`, `test_undo_flow()`, manual testing on own Gmail
- **Failsafe:** Starred emails never touched, contacts kept, critical keywords protected

**Risk 3: Privacy Violation - Body Storage** (CATASTROPHIC)
- **Mitigation:** Database schema prohibits body columns, in-memory processing only
- **Testing:** `test_no_body_in_database()`, `test_no_body_in_logs()`
- **Enforcement:** Code review on every PR, PostgreSQL triggers block body columns

**Risk 4: AI Misclassification** (HIGH PROBABILITY)
- **Mitigation:** Conservative thresholds (0.90+ for trash), metadata signals first, review mode
- **Testing:** Test on 1000+ real emails before launch, job offer safety tests, medical email tests
- **Recovery:** Easy undo in digest, weekly "borderline cases" review

**Risk 5: Database Loss** (CATASTROPHIC)
- **Mitigation:** Railway auto-backups (7 days) + S3 offsite backups (encrypted)
- **Testing:** Monthly restore test to staging
- **Schedule:** Daily S3 backup at 2 AM UTC

**Risk 6: Gmail API Quota Exhaustion** (MEDIUM)
- **Mitigation:** Rate limiting (10 emails/min/user), exponential backoff, fallback polling
- **Testing:** Load test with 10K email backlog
- **Monitoring:** Alert if retry count >3 per user

---

## Classification System

### Three-Tier Approach

**Tier 1: Metadata Signals (80% accuracy, free, instant)**
- Gmail category (CATEGORY_PROMOTIONS = 90% delete-worthy)
- List-Unsubscribe header (99% = marketing)
- Bulk mail headers (Precedence: bulk, Auto-Submitted)
- Marketing platform domains (sendgrid.net, mailchimp)
- Subject patterns (% off, limited time, emojis)
- User behavior (sender_open_rate <5% = never reads)

**Tier 2: AI Classification (95% accuracy, $0.003/call)**
- GPT-4o-mini with enhanced prompt
- Minimal data sent (domain, subject, 200-char snippet)
- Distinguishes: trash vs archive vs keep vs review
- Only called if metadata confidence <90%

**Tier 3: User Rules (100% accuracy, user-controlled)**
- Always trash: blocked senders/domains
- Always keep: allowed senders/domains (@work.com)
- Per-sender preferences (learned from undo actions)

### Delete vs Archive Logic

**TRASH** (delete-worthy):
- Generic marketing blasts (Old Navy 50% off)
- Social notifications (LinkedIn "you appeared in searches")
- Re-engagement campaigns ("We miss you!")
- Emails user never opens (open_rate <5%)
- Promotional category + has_unsubscribe + confidence >0.85

**ARCHIVE** (future value):
- Receipts, order confirmations, invoices
- Financial statements, bank notices
- Shipping notifications, booking confirmations
- Newsletters from subscribed sources
- Service notifications (password reset, security alerts)

**KEEP** (important):
- Personal emails from real people
- Starred or marked important by user
- From known contacts (in address book)
- Critical keywords: interview, job, medical, bank, tax, legal
- Recent (<3 days) + uncertainty

**Exception Keywords** (never trash even if classified as promo):
```python
['receipt', 'invoice', 'order', 'payment', 'booking',
 'reservation', 'ticket', 'shipped', 'tracking',
 'password', 'security', 'tax', 'medical', 'bank']
```

---

## User Experience Design

### Email-First + Minimal Web Portal (Hybrid)

**Email Handles (90% of interactions):**
- Welcome email (post-OAuth, sandbox mode explanation)
- Weekly digest (top 5 important, auto-handled count, borderline cases)
- Backlog analysis ("Found 6,200 old emails, clean them up?")
- Progress updates (during long cleanup)
- Action receipts (daily/weekly counts, undo links)
- Magic links (one-click actions, no login required)

**Web Portal Handles (10% of interactions):**
- Settings (confidence thresholds, digest schedule, block/allow lists)
- Account (subscription, billing, export data, delete account)
- Audit log viewer (browse history, search actions)
- OAuth landing page ("Connect Gmail" button)

**No Mobile App for MVP** (add after 100+ paying users if requested)

### Magic Link Architecture
```python
# JWT-encoded, 24-hour expiration
payload = {
    'user_id': uuid,
    'action': 'undo_24h' | 'enable_action_mode' | 'cleanup_backlog',
    'exp': datetime.utcnow() + timedelta(hours=24)
}
token = jwt.encode(payload, SECRET_KEY)
link = f"https://app.inboxjanitor.com/a/{token}"
```

**No password login** - Magic links from email grant temporary session.

---

## Feature Roadmap

### MVP (Weeks 1-6): First Paying Customer

**Week 1-2: Foundation**
- [ ] OAuth flow (Gmail only, Authlib)
- [ ] PostgreSQL schema (users, mailboxes, email_actions, audit_log)
- [ ] Gmail watch + Pub/Sub webhook receiver
- [ ] Celery + Redis queue setup
- [ ] Token encryption (Fernet, env vars)
- [ ] Basic email templates (Postmark)

**Week 3: Backlog Cleanup (Mom's Feature)**
- [ ] Backlog analysis (count old emails by category)
- [ ] User-controlled batch cleanup (magic links)
- [ ] Progress emails during cleanup
- [ ] Rate limiting (10 emails/min/user)

**Week 4: Classification**
- [ ] Metadata extraction (Gmail category, headers, sender analysis)
- [ ] Enhanced AI prompt (delete vs archive distinction)
- [ ] Conservative safety rails (starred, contacts, critical keywords)
- [ ] Logging for learning

**Week 5: Action Mode + Safety**
- [ ] Archive/trash execution (Gmail API)
- [ ] 7-day quarantine (Janitor/Quarantine label)
- [ ] 30-day undo flow (restore from quarantine)
- [ ] Emergency stop (email stop@inboxjanitor.app)

**Week 6: Billing + Polish**
- [ ] Stripe Checkout (hosted)
- [ ] Subscription webhooks
- [ ] Weekly digest email (summary, borderline cases, undo)
- [ ] Settings web portal (3 pages: landing, settings, account)
- [ ] Test with mom + sister

**Success Metric:** 1-2 paying customers at $6/mo

### V1 (Weeks 7-12): Scale to 100 Users

- [ ] Microsoft 365 integration (OAuth + webhooks)
- [ ] Reply-to-configure commands (parse email replies)
- [ ] User rules (block/allow lists, per-sender actions)
- [ ] Daily action receipts (optional)
- [ ] Confidence threshold tuning (sliders in web portal)
- [ ] Multi-account support (connect 2+ Gmail accounts)
- [ ] Adaptive learning (improve from undo actions)

**Success Metric:** 100 paying customers, $600-1200 MRR

### V2 (Months 4-6): Advanced Features

- [ ] Team features (shared policies, admin oversight)
- [ ] Slack integration (critical email alerts)
- [ ] Follow-up detection ("No reply in 7 days")
- [ ] Thread summarization (long email chains)
- [ ] Mobile app (iOS first, push notifications)
- [ ] Advanced analytics (visual dashboard)

**Success Metric:** 500 users, $6K MRR

---

## Testing Strategy

### Security Tests (Run Before Every Commit)
```bash
pytest tests/security/test_token_encryption.py
pytest tests/security/test_sql_injection.py
pytest tests/security/test_no_body_storage.py
pytest tests/security/test_key_not_in_codebase.py
bandit -r app/  # Detect vulnerabilities
git-secrets --scan  # Prevent secret commits
mypy app/  # Type checking
```

### Safety Tests (Prevent Data Loss)
```bash
pytest tests/safety/test_archive_not_delete.py
pytest tests/safety/test_undo_flow.py
pytest tests/safety/test_job_offer_safety.py
pytest tests/safety/test_medical_email_safety.py
pytest tests/safety/test_no_permanent_delete_method.py
```

### Manual Testing Phases

**Phase 1: Developer (Week 1-2)**
- Test on YOUR OWN Gmail for 7 days (dry-run mode)
- Review every decision daily
- Log false positives (important emails wrongly classified)
- Tune thresholds based on real data

**Phase 2: Internal (Week 3)**
- 5 trusted users (friends with tech knowledge)
- Sandbox mode only
- Written consent required
- Daily feedback calls

**Phase 3: Closed Beta (Week 4-5)**
- Mom, sister, 3 non-technical friends
- Monitor accounts daily
- Watch for complaints about missing emails

**Phase 4: Limited Beta (Week 6-8)**
- 50 users (Google Form applications)
- Sandbox mode default, action mode opt-in
- Weekly check-ins
- Emergency kill switch ready

**Launch Criteria (Must Pass):**
- [ ] 0 reports of lost emails
- [ ] 0 reports of privacy violations
- [ ] <1% undo rate (quality metric)
- [ ] >80% user satisfaction
- [ ] 0 OAuth token leaks
- [ ] 0 database incidents

---

## Git Workflow & Deployment

### GitHub Pull Request Workflow (REQUIRED)

**CRITICAL: NEVER push directly to main. ALL changes via pull requests.**

**Required Workflow:**

1. **Create Feature Branch**
   ```bash
   git checkout main
   git pull origin main
   git checkout -b feature/your-feature-name
   ```

2. **Make Changes and Commit**
   ```bash
   git add .
   git commit -m "Your commit message"
   git push -u origin feature/your-feature-name
   ```

3. **Create Pull Request**
   ```bash
   gh pr create --title "Feature title" --body "Description"
   ```

4. **Wait for Checks** (REQUIRED before merge)
   - [ ] GitHub Actions/checks pass
   - [ ] Railway preview deployment succeeds (if configured)
   - [ ] All automated tests pass
   - [ ] Security scans complete

5. **User Review and Approval**
   - User reviews changes in PR
   - User approves or requests changes

6. **Merge PR** (only after approval + checks pass)
   ```bash
   gh pr merge --squash
   ```

7. **Verify Production Deployment**
   - [ ] Railway production deployment succeeds
   - [ ] Health check returns 200 OK: https://inbox-janitor-production-03fc.up.railway.app/health
   - [ ] No errors in Railway logs

**If deployment fails after merge:**
- Create hotfix branch immediately
- Fix issue
- Create new PR for hotfix
- Follow same workflow

---

## Database Schema

```sql
-- Users
CREATE TABLE users (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    email TEXT UNIQUE NOT NULL,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Mailboxes (OAuth connections)
CREATE TABLE mailboxes (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID REFERENCES users(id) ON DELETE CASCADE,
    provider TEXT NOT NULL,  -- 'gmail' | 'microsoft365'
    email_address TEXT NOT NULL,
    encrypted_access_token TEXT NOT NULL,
    encrypted_refresh_token TEXT NOT NULL,
    token_expires_at TIMESTAMPTZ,
    watch_expiration TIMESTAMPTZ,  -- Gmail watch renewal
    last_history_id TEXT,  -- Gmail delta sync
    is_active BOOLEAN DEFAULT true,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Email Actions (audit log, immutable)
CREATE TABLE email_actions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    mailbox_id UUID REFERENCES mailboxes(id),
    message_id TEXT NOT NULL,  -- Gmail message ID
    from_address TEXT,
    subject TEXT,
    snippet TEXT,  -- First 200 chars only (NO FULL BODY)
    action TEXT NOT NULL,  -- 'keep' | 'archive' | 'trash' | 'review' | 'undo'
    reason TEXT,
    confidence FLOAT,
    classification_metadata JSONB,  -- Classification signals
    created_at TIMESTAMPTZ DEFAULT NOW(),
    undone_at TIMESTAMPTZ,
    can_undo_until TIMESTAMPTZ  -- 30 days from action
);

-- Immutability trigger
CREATE OR REPLACE FUNCTION prevent_email_action_modification()
RETURNS TRIGGER AS $$
BEGIN
    RAISE EXCEPTION 'email_actions table is append-only (immutable audit log)';
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER email_actions_immutable
BEFORE UPDATE OR DELETE ON email_actions
FOR EACH ROW EXECUTE FUNCTION prevent_email_action_modification();

-- User Settings
CREATE TABLE user_settings (
    user_id UUID PRIMARY KEY REFERENCES users(id) ON DELETE CASCADE,
    confidence_auto_threshold FLOAT DEFAULT 0.85,
    confidence_review_threshold FLOAT DEFAULT 0.55,
    digest_schedule TEXT DEFAULT 'weekly',  -- 'daily' | 'weekly' | 'off'
    action_mode_enabled BOOLEAN DEFAULT false,
    auto_trash_promotions BOOLEAN DEFAULT true,
    auto_trash_social BOOLEAN DEFAULT true,
    keep_receipts BOOLEAN DEFAULT true,
    blocked_senders TEXT[] DEFAULT '{}',
    allowed_domains TEXT[] DEFAULT '{}'
);

-- Sender Stats (learning)
CREATE TABLE sender_stats (
    user_id UUID REFERENCES users(id),
    sender_address TEXT,
    total_received INT DEFAULT 0,
    opened_count INT DEFAULT 0,
    replied_count INT DEFAULT 0,
    last_received_at TIMESTAMPTZ,
    PRIMARY KEY (user_id, sender_address)
);
```

**Retention Policy:**
- `email_actions`: 30 days (metadata only, no bodies)
- `sender_stats`: 90 days
- Audit exports: 1 year (then archive to S3)

---

## Deployment Configuration

### Railway Services

1. **Web Service** (FastAPI + Celery Beat)
   - Handles webhooks, API endpoints
   - Runs Celery beat scheduler (cron jobs)
   - Environment: Production
   - Scale: 1 instance (start), autoscale at 100+ users

2. **Worker Service** (Celery Worker)
   - Processes background jobs (email classification, actions)
   - Same codebase as web (different command)
   - Environment: Production
   - Scale: 1 worker (start), add workers at quota issues

3. **PostgreSQL Database**
   - Managed by Railway
   - Daily backups (7-day retention)
   - Encryption at rest enabled

4. **Redis Cache**
   - Celery message broker
   - Rate limiting cache
   - Magic link session storage

### Environment Variables (Railway Secrets)
```bash
# Database
DATABASE_URL=postgresql://...  # Auto-set by Railway

# Encryption
ENCRYPTION_KEY=<44-char Fernet key>  # Generate once, rotate annually

# OAuth
GOOGLE_CLIENT_ID=...
GOOGLE_CLIENT_SECRET=...
MICROSOFT_CLIENT_ID=...  # V1
MICROSOFT_CLIENT_SECRET=...  # V1

# APIs
OPENAI_API_KEY=sk-...
POSTMARK_API_KEY=...

# Security
SECRET_KEY=<random 32-char>  # For JWT signing

# App
APP_URL=https://app.inboxjanitor.com
ENVIRONMENT=production
```

### Celery Beat Schedule
```python
celery.conf.beat_schedule = {
    # Renew Gmail watches (every 6 days, watches expire in 7)
    'renew-gmail-watches': {
        'task': 'app.tasks.renew_gmail_watches',
        'schedule': crontab(hour='3', minute='0', day_of_week='*/6')
    },

    # Fallback polling (every 10 min, catch missed webhooks)
    'fallback-poll': {
        'task': 'app.tasks.fallback_poll_missed_emails',
        'schedule': crontab(minute='*/10')
    },

    # Send weekly digests (Sundays at 9 AM user timezone)
    'send-weekly-digests': {
        'task': 'app.tasks.send_weekly_digests',
        'schedule': crontab(hour='9', minute='0', day_of_week='0')
    },

    # Database cleanup (daily at 2 AM UTC)
    'cleanup-old-data': {
        'task': 'app.tasks.cleanup_old_data',
        'schedule': crontab(hour='2', minute='0')
    },

    # S3 backup (daily at 3 AM UTC)
    'backup-database': {
        'task': 'app.tasks.backup_database_to_s3',
        'schedule': crontab(hour='3', minute='0')
    },

    # Monitor undo rate (every 5 min)
    'monitor-undo-rate': {
        'task': 'app.tasks.monitor_undo_rate',
        'schedule': crontab(minute='*/5')
    }
}
```

---

## Pricing Strategy

**Starter ($6/mo):**
- 1 Gmail account
- Sandbox mode + weekly digest
- 30-day action history
- Email support

**Pro ($12/mo):**
- 2 accounts (Gmail or M365)
- Action mode + undo/quarantine
- Per-sender rules (block/allow lists)
- 90-day history + data export
- Priority support

**Team ($20/user/mo):**
- Unlimited accounts per user
- Shared team policies
- Admin dashboard
- 1-year audit logs
- Dedicated support

**Free Trial:** 7 days (all Pro features)

**Stripe:** Hosted Checkout (no custom UI), webhooks for subscription lifecycle

---

## Distribution Strategy (No App Store)

### Month 1 (MVP): Friends & Family
- Mom, sister, you = 3 users
- Post in personal social media
- Ask 5 friends to test
- **Cost:** $0
- **Target:** 10 users

### Month 2: Public Launch
- Product Hunt (Tuesday 12:01am PST)
- Reddit (r/productivity, r/gmail, r/minimalism)
- Hacker News "Show HN"
- Twitter build-in-public thread
- **Cost:** $0
- **Target:** 50 signups, 10 paying ($60 MRR)

### Month 3: Content Marketing
- Blog posts: "How to Clean 10K Emails in One Day", "SaneBox vs Inbox Janitor"
- YouTube tutorial
- Indie Hackers journey posts
- **Cost:** $0-100
- **Target:** 100 users, 30 paying ($180-300 MRR)

### Month 4-6: SEO + Partnerships
- SEO traffic from blog posts
- Guest posts (Lifehacker, Fast Company)
- Referral program ("Give 1 month, get 1 month")
- **Cost:** $200-500
- **Target:** 500 users, 150 paying ($900 MRR)

**Mobile app:** Consider at $900+ MRR (retention tool, not acquisition)

---

## Monitoring & Alerts

### Sentry.io (Error Tracking)
- Python exceptions
- OAuth failures (401 errors)
- Gmail API quota errors (429)
- Database connection issues

### Custom Alerts (Email to Admin)
- High undo rate (>5% in 24h = classifier broken)
- OAuth failures (>10 in 1h = token leak or API issue)
- Processing lag (>5 min = quota or worker issue)
- Database body query attempts (security violation)
- No webhooks received in 30 min (Pub/Sub issue)

### Health Check Endpoint
```python
@app.get("/health")
def health():
    return {
        'database': check_db_connection(),
        'redis': check_redis_connection(),
        'gmail_api': check_gmail_api(),
        'openai_api': check_openai_api(),
        'last_webhook': seconds_since_last_webhook()
    }
```

---

## Emergency Procedures

### Security Breach Response
1. Engage global kill switch: `redis.set('KILL_SWITCH', '1')`
2. Revoke ALL OAuth tokens at Google
3. Email all users (reconnect required)
4. Rotate encryption keys
5. Export audit logs
6. Notify GDPR authorities if confirmed breach (within 72h)

### Accidental Deletion Response
1. Immediately pause user's mailbox
2. Restore ALL emails from last 30 days to inbox
3. Log emergency restore event
4. Email user (restoration complete, account paused)
5. Investigate root cause

### Database Loss Response
1. Restore from latest Railway backup (7 days available)
2. If Railway backups corrupted, restore from S3
3. Verify data integrity
4. Email all users (service interruption, data recovered)
5. Offer free month compensation

---

## Migration Status

**Legacy System:**
- `scripts/InboxJanitor.gs` - Google Apps Script (deprecated)
- `API/main.py` - FastAPI classifier (to migrate to app/modules/classifier/)

**Migration:** Week 1-2 foundation complete. Week 3+ execute full cutover.

---

## Known Limitations & Future Work

**MVP Limitations:**
- Gmail only (no M365 until V1)
- No mobile app (web portal on mobile browser)
- No reply-to-configure (manual support for first 10 users)
- No team features (individual users only)
- No Slack integration
- English only (no i18n)

**Technical Debt (Acceptable for MVP):**
- Hardcoded email templates (refactor to database in V1)
- Manual Stripe subscription setup (automate in Week 6)
- No A/B testing framework (add at 100+ users)
- No advanced analytics (basic metrics only)

**Scalability Limits (Re-assess at 1K users):**
- Monolith handles 1-10K users
- PostgreSQL connection pooling needed at 500+ users
- Extract high-load modules (ingest, executor) at 1K+ users
- Consider read replicas at 5K+ users

---

**For current project status, blockers, and next priorities, see CHANGELOG.md "Current Status" section.**
