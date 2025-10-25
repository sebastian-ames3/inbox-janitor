# Changelog

All notable decisions and changes to the Inbox Janitor project.

---

## [Unreleased] - 2025-10-25

### Major Architectural Decisions

#### Modular Monolith (NOT Microservices)
- **Decision:** Build as single FastAPI app with modular structure
- **Rationale:** Solo founder velocity, shared transactions, lower costs ($20/mo vs $50+), easier debugging
- **Migration Path:** Extract modules to services only if needed at 1K+ users
- **Alternative Rejected:** Microservices (11 separate agents) - too complex for solo founder

#### Tech Stack Finalized
- **Backend:** FastAPI (keep existing, async support)
- **Database:** PostgreSQL (ACID transactions, relational data)
- **Queue:** Celery + Redis (self-hosted, proven)
- **Email:** Postmark (deliverability 99.8%, transactional focus)
- **OAuth:** Authlib (unified Gmail + M365 API)
- **Deployment:** Railway (current platform, simple DX)
- **Encryption:** Fernet symmetric (fast, secure; migrate to KMS at 500+ users)

#### Email-First + Minimal Web Portal (Hybrid UX)
- **Decision:** Not "email-only" but "email-first"
- **Rationale:** User (mom/sister) feedback - managing settings via email magic links is too cumbersome
- **Implementation:**
  - Email for: notifications, digests, quick actions (90% of interactions)
  - Web portal for: settings, list management, account (10% of interactions)
  - No mobile app for MVP (add after 100+ users if requested)
- **Alternative Rejected:** Pure email-only - confusing for multiple settings changes

#### No App Store for Launch
- **Decision:** Web-first launch, skip iOS/Android apps initially
- **Rationale:**
  - App Store discovery is poor (0-5 organic installs/day)
  - 30% Apple tax (lose $1.80 of $6/mo revenue)
  - Competitor research: SaneBox, Superhuman, Leave Me Alone all launched web-first
  - Acquisition via: Product Hunt, Reddit, HN, content marketing ($0 cost)
- **Mobile App Timing:** After 100+ paying users (retention tool, not acquisition)

### Security Architecture

#### OAuth Token Security (CRITICAL)
- **Risk:** Token theft = full Gmail access for attacker
- **Mitigation:**
  - Fernet encryption (tokens encrypted at rest)
  - Encryption key in Railway env vars (never in code)
  - HTTPS-only (Railway enforces)
  - Never log tokens (tested in CI)
  - SQL injection protection (parameterized queries only)
  - Monitoring: Multi-IP usage detection, auto-revoke on anomaly
- **Testing:** `test_token_encryption()`, `test_token_not_in_logs()`, `test_sql_injection()`

#### Data Loss Prevention (CRITICAL)
- **Risk:** Accidental permanent email deletion
- **Mitigation:**
  - NEVER call Gmail `.delete()` API (banned from codebase)
  - 7-day quarantine before trash
  - 30-day undo window
  - All actions logged to immutable audit table
  - Starred emails never touched
  - Critical keywords protected (job, medical, bank, tax, legal)
- **Testing:** `test_archive_not_delete()`, `test_undo_flow()`, `test_no_permanent_delete_method()`
- **Manual Testing:** Test on own Gmail for 7 days before any user

#### Privacy - No Email Body Storage (CRITICAL)
- **Risk:** Database leak exposes private conversations, medical records, SSNs
- **Mitigation:**
  - Database schema prohibits body columns (no `body`, `html_body`, `content` fields)
  - PostgreSQL trigger blocks body column creation
  - In-memory processing only (fetch → classify → discard)
  - Minimal data to OpenAI (domain, subject, 200-char snippet)
- **Testing:** `test_no_body_in_database()`, `test_no_body_in_logs()`, `test_schema_no_body_column()`

#### AI Misclassification (HIGH PROBABILITY)
- **Risk:** Important email (job offer) classified as trash
- **Mitigation:**
  - Conservative thresholds (0.90+ for auto-trash, 0.85+ for archive)
  - Metadata signals first (80% accuracy, no AI cost)
  - Critical keyword protection: job, interview, medical, doctor, bank, tax, legal, court
  - Starred emails always kept
  - Known contacts always kept
  - Low confidence → review mode (not auto-act)
- **Testing:** `test_job_offer_safety()`, `test_medical_email_safety()`, test on 1000+ real emails

### Classification System Design

#### Three-Tier Classification
1. **Metadata Signals (Tier 1):** 80% accuracy, free, instant
   - Gmail category (CATEGORY_PROMOTIONS = 90% delete-worthy)
   - List-Unsubscribe header (99% = marketing by law)
   - Bulk mail headers (Precedence: bulk, Auto-Submitted)
   - Marketing platforms (sendgrid.net, mailchimp)
   - Subject patterns (% off, limited time, emojis)
   - User behavior (sender_open_rate <5% = never reads)

2. **AI Classification (Tier 2):** 95% accuracy, $0.003/call
   - GPT-4o-mini with enhanced prompt
   - Only called if metadata confidence <90% (cost optimization)
   - Minimal data sent (domain, subject, 200-char snippet)

3. **User Rules (Tier 3):** 100% accuracy, user-controlled
   - Block/allow lists
   - Per-sender preferences
   - Learned from undo actions

#### Delete vs Archive Distinction
- **TRASH (delete-worthy):**
  - Generic marketing blasts (Old Navy 50% off)
  - Social notifications (LinkedIn spam)
  - Re-engagement campaigns
  - Emails user never opens (open_rate <5%)
  - Promotional category + has_unsubscribe + confidence >0.85

- **ARCHIVE (future value):**
  - Receipts, invoices, order confirmations
  - Financial statements, bank notices
  - Shipping notifications, booking confirmations
  - Service notifications (password reset, security)

- **KEEP (important):**
  - Personal emails from real people
  - Starred or marked important
  - From known contacts
  - Critical keywords detected
  - Recent (<3 days) + uncertainty

- **Exception Keywords (never trash):**
  - receipt, invoice, order, payment, booking, reservation, ticket
  - shipped, tracking, password, security, tax, medical, bank

### Backlog Cleanup Feature

#### User Request
- **Source:** Mom and sister feedback - need to clean existing 5K-8K email backlogs
- **Problem:** Current script only processes last 7 days (`newer_than:7d`)
- **Impact:** No value for users with overflowing inboxes

#### Implementation Decision
- **Add to Week 3 roadmap** (not Week 1)
- **Rationale:** Needs core OAuth + classification working first
- **Approach:** User-controlled batch cleanup (not automatic)
  1. Analyze backlog ("Found 6,200 promotional emails older than 30 days")
  2. Send email with breakdown + magic links
  3. User clicks "Archive Promotions (6,200)"
  4. Process in batches (500 emails/hour, rate limiting)
  5. Progress updates every 1,000 emails
  6. Completion email with undo option

#### Safety Measures
- Batch size: 500 emails max per batch
- Rate limiting: 10 emails/min/user (avoid Gmail quota)
- Confidence threshold: 0.70+ for backlog (more conservative)
- Skip critical keywords even in old emails
- Category-specific: promotions first, then social, then updates
- User-initiated only (no surprise bulk deletions)

### Roadmap Revisions

#### Timeline Adjustments
- **Week 7-8 Change:** Defer Microsoft 365 integration to Week 9+
- **Rationale:** Gmail has 1.8B users (5x larger market), need validation first
- **New Week 7-8 Focus:** Polish, beta feedback, Product Hunt launch, 25 beta users
- **M365 Timing:** After 10+ paying Gmail users (validates product-market fit)

#### MVP Scope (Weeks 1-6)
**Must-Have:**
- OAuth (Gmail only)
- Backlog cleanup (Week 3)
- Real-time email processing (Pub/Sub webhooks)
- Classification (metadata + AI)
- Action mode (archive/trash)
- Quarantine + undo
- Weekly digest
- Stripe subscriptions
- Settings web portal (3 pages)

**Deferred to V1:**
- Microsoft 365 integration
- Reply-to-configure commands
- Mobile app
- Slack integration
- Team features
- Advanced analytics

#### Success Metrics
- **MVP (Week 6):** 1-2 paying customers (mom, sister, or early adopters)
- **V1 (Week 12):** 100 paying customers, $600-1200 MRR
- **V2 (Month 6):** 500 users, $6K MRR

### Testing Strategy

#### Pre-Launch Requirements
**Must pass before ANY user (even mom):**
- [ ] All security tests passing (token encryption, SQL injection, no secrets in logs)
- [ ] All safety tests passing (no delete, undo flow, critical keywords)
- [ ] Tested on own Gmail for 7 days (dry-run mode)
- [ ] Tested on 5 friends' Gmails (with written consent)
- [ ] 0 false positives in 1000+ test emails
- [ ] <1% undo rate in beta
- [ ] Manual testing checklist complete (starred, labeled, threaded emails)

#### Testing Phases
1. **Developer (Week 1-2):** Own Gmail, dry-run mode, 7 days
2. **Internal (Week 3):** 5 tech-savvy friends, sandbox only, daily feedback
3. **Closed Beta (Week 4-5):** Mom, sister, 3 non-tech friends, closely supervised
4. **Limited Beta (Week 6-8):** 50 users (Google Form), sandbox default, emergency kill switch ready

### Distribution Strategy

#### Acquisition Channels (Web-First)
**Month 1 (MVP):** Friends & family ($0 cost, 10 users)
**Month 2 (Launch):** Product Hunt, Reddit, Hacker News, Twitter ($0 cost, 50 signups, 10 paying)
**Month 3:** Content marketing, blog posts, YouTube ($0-100 cost, 100 users, 30 paying)
**Month 4-6:** SEO traffic, guest posts, referrals ($200-500 cost, 500 users, 150 paying)

#### App Store Decision
- **Not primary acquisition channel** (discovery is poor, 30% Apple tax)
- **Competitors:** SaneBox, Superhuman, Leave Me Alone all grew without App Store
- **Timing:** Consider mobile app at $900+ MRR (retention tool, not acquisition)

### Database Design

#### Key Schema Decisions
- **Immutable Audit Log:** PostgreSQL trigger blocks UPDATE/DELETE on `email_actions` table
- **No Email Bodies:** Schema prohibits body columns, enforced by code review
- **Encrypted Tokens:** `encrypted_access_token`, `encrypted_refresh_token` fields
- **Sender Stats:** Track open_rate, reply_rate per sender for learning
- **Retention:** 30-day metadata, 90-day decisions, 1-year audit (then S3 archive)

#### Data Minimization
- Store only: message_id, from, subject, snippet (200 chars)
- Never store: full body, HTML, attachments, recipient lists
- OpenAI receives: domain (not full email), subject (truncated), snippet (200 chars)

### Monitoring & Alerts

#### Critical Alerts (Email to Admin)
- High undo rate (>5% in 24h) = classifier broken
- OAuth failures (>10 in 1h) = token leak or API issue
- Processing lag (>5 min) = quota or worker issue
- Database body query attempt = security violation
- No webhooks in 30 min = Pub/Sub issue

#### Error Tracking
- Sentry.io (free tier)
- Track: Python exceptions, OAuth failures, Gmail API quota errors, DB connection issues

### Cost Projections

#### Beta (50 users)
- Railway: $20/mo
- Postmark: $15/mo
- OpenAI: $10/mo
- Domain: $1/mo
- **Total: $46/mo**

#### Revenue Targets
- 50 users × $6/mo = $300/mo (break-even at 50 users)
- 100 users × $12/mo = $1,200/mo (profitable)
- 500 users × $12/mo = $6,000/mo (sustainable solo business)

### Migration from Google Apps Script

#### Current State
- `scripts/InboxJanitor.gs`: Google Apps Script (processes inbox, calls API)
- `API/main.py`: FastAPI classifier (GPT-4o-mini)
- Railway deployment: https://inbox-janitor-production.up.railway.app

#### Migration Plan
- **Week 1:** Keep Apps Script running, build OAuth in new app
- **Week 2:** Build webhook receiver, run in parallel (both log, neither acts)
- **Week 3:** Test new app on personal Gmail (disable Apps Script)
- **Week 4+:** Full cutover, deprecate Apps Script

---

## Questions Resolved

### Q: "Should I build the 11 sub-agents as separate microservices?"
**A:** No. Build as modules in monolith. Extract later only if needed (1K+ users).

### Q: "How do I deploy/market without App Store?"
**A:** Web-first launch. Acquisition via Product Hunt, Reddit, HN, content ($0 cost). Mobile app is retention tool for later (after 100+ users).

### Q: "Can email-only UX handle complex settings?"
**A:** No. Hybrid approach: email-first (90% interactions) + minimal web portal (10%, for settings). Magic links grant temporary web sessions.

### Q: "Can the script identify ads vs important emails?"
**A:** Yes. Three-tier system: metadata signals (80% accuracy, free), AI (95%, $0.003/call), user rules (100%, learned). Gmail category + List-Unsubscribe header are strong signals.

### Q: "Should emails be archived or deleted?"
**A:** Depends. Trash = generic marketing spam. Archive = receipts, confirmations (future value). Exception keywords prevent trashing important categories.

### Q: "How to avoid deleting important emails?"
**A:** Multiple safeguards: starred always kept, contacts kept, critical keywords (job, medical, bank), 7-day quarantine, 30-day undo, conservative thresholds (0.90+), review mode for uncertainty.

### Q: "When to add Microsoft 365 support?"
**A:** Week 9+ (after Gmail validation). Gmail is 5x larger market. Need 10+ paying users before expanding platforms.

### Q: "What if Gmail API quota is exceeded?"
**A:** Rate limiting (10 emails/min/user), exponential backoff, fallback polling every 10 min (catches missed webhooks).

---

## Decisions Pending

None. Architecture finalized. Ready to start Week 1 development.

---

## Next Session Priorities

1. Set up FastAPI project structure (modular monolith)
2. Create PostgreSQL schema (users, mailboxes, email_actions)
3. Implement OAuth flow with Authlib (Gmail only)
4. Set up Google Cloud Pub/Sub for webhooks
5. Encrypt token storage (Fernet + env vars)

**Reference `claude.md` for full context.**
