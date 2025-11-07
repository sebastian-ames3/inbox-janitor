# Deployment Checklist: AI Classification + Usage Tracking

**PRs to Deploy:**
- PR #52: AI Classification with OpenAI GPT-4o-mini
- PR #53: Usage Tracking and Monthly Limits

**Estimated Time:** 3-5 hours (including testing)

**Status:** Ready for testing phase

---

## Phase 1: Local Testing (30-45 min)

**Goal:** Verify all unit tests pass locally before trusting CI/CD.

### 1.1 Run Usage Tracking Tests
```bash
pytest tests/unit/test_usage_tracking.py -v
```

**Expected Output:**
```
test_has_not_reached_limit PASSED
test_has_reached_limit_exactly PASSED
test_usage_percentage_zero PASSED
test_is_approaching_limit_at_80 PASSED
...
========== 20 passed in 2.5s ==========
```

**If Tests Fail:**
- [ ] Read error messages carefully
- [ ] Check `app/models/user_settings.py` for property logic
- [ ] Fix issues and re-run
- [ ] Don't proceed until ALL tests pass

---

### 1.2 Run AI Classification Tests
```bash
pytest tests/unit/test_tier2_ai.py -v
pytest tests/security/test_ai_no_body.py -v
```

**Expected Output:**
```
test_cache_hit_no_api_call PASSED
test_confidence_reduction PASSED
test_no_full_body_in_prompt PASSED
test_snippet_truncated_to_200_chars PASSED
...
========== 15 passed in 3.2s ==========
```

**If Tests Fail:**
- [ ] Check OpenAI API key is set in `.env`
- [ ] Verify Redis is running (`redis-cli ping` → PONG)
- [ ] Check `app/modules/classifier/openai_client.py` for errors
- [ ] Don't proceed until ALL tests pass

---

### 1.3 Run Full Test Suite
```bash
pytest tests/ -v --tb=short
```

**Expected Output:**
```
========== XXX passed in XX.Xs ==========
```

**If Any Tests Fail:**
- [ ] Review failures by category (unit, integration, security, safety)
- [ ] Fix regressions (new code broke old tests)
- [ ] Re-run full suite
- [ ] **CRITICAL:** All tests must pass before proceeding

---

## Phase 2: Database Migration Testing (20-30 min)

**Goal:** Ensure migration runs cleanly without breaking production database.

### 2.1 Preview Migration SQL
```bash
cd /mnt/c/Users/14102/Documents/Sebastian\ Ames/Projects/inbox-janitor
source venv/bin/activate
alembic upgrade head --sql > migration_preview.sql
cat migration_preview.sql
```

**Expected Output:**
```sql
ALTER TABLE user_settings ADD COLUMN plan_tier VARCHAR NOT NULL DEFAULT 'starter';
ALTER TABLE user_settings ADD COLUMN monthly_email_limit INTEGER NOT NULL DEFAULT 10000;
ALTER TABLE user_settings ADD COLUMN emails_processed_this_month INTEGER NOT NULL DEFAULT 0;
ALTER TABLE user_settings ADD COLUMN ai_cost_this_month DOUBLE PRECISION NOT NULL DEFAULT 0.0;
ALTER TABLE user_settings ADD COLUMN current_billing_period_start DATE NOT NULL DEFAULT CURRENT_DATE;
CREATE INDEX ix_user_settings_billing_period ON user_settings (current_billing_period_start);
CREATE INDEX ix_user_settings_plan_tier ON user_settings (plan_tier);
```

**Review Checklist:**
- [ ] No DROP TABLE statements (would lose data)
- [ ] Columns have safe defaults (`starter`, `10000`, `0`, `CURRENT_DATE`)
- [ ] Indexes created on correct columns
- [ ] SQL syntax looks correct

**If Preview Looks Wrong:**
- [ ] Review migration file: `alembic/versions/006_add_usage_tracking_to_user_settings.py`
- [ ] Fix issues in migration file
- [ ] Re-generate preview SQL
- [ ] Don't proceed until SQL is safe

---

### 2.2 Test Migration Locally
```bash
# Check current migration version
alembic current

# Run migration
alembic upgrade head

# Verify columns exist
psql $DATABASE_URL -c "\d user_settings"
```

**Expected Output:**
```
                                       Table "public.user_settings"
 Column                           | Type              | Nullable | Default
----------------------------------+-------------------+----------+----------
 user_id                          | uuid              | not null |
 plan_tier                        | varchar           | not null | 'starter'
 monthly_email_limit              | integer           | not null | 10000
 emails_processed_this_month      | integer           | not null | 0
 ai_cost_this_month               | double precision  | not null | 0.0
 current_billing_period_start     | date              | not null | CURRENT_DATE
...

Indexes:
    "ix_user_settings_billing_period" btree (current_billing_period_start)
    "ix_user_settings_plan_tier" btree (plan_tier)
```

**Verification Checklist:**
- [ ] All 5 new columns exist
- [ ] Columns have correct types and defaults
- [ ] Both indexes created
- [ ] No errors in migration output

**If Migration Fails:**
- [ ] Read error message
- [ ] Rollback: `alembic downgrade -1`
- [ ] Fix migration file
- [ ] Re-test migration

---

### 2.3 Test Migration Rollback (Safety Check)
```bash
# Rollback migration
alembic downgrade -1

# Verify columns removed
psql $DATABASE_URL -c "\d user_settings"

# Re-apply migration
alembic upgrade head
```

**Expected Output:**
- After downgrade: Columns should be gone
- After upgrade: Columns should be back

**Verification:**
- [ ] Rollback removes columns cleanly
- [ ] Re-apply restores columns
- [ ] No data loss during rollback/re-apply

---

## Phase 3: CI/CD Checks (15-30 min)

**Goal:** Wait for GitHub Actions to validate all tests in CI environment.

### 3.1 Check PR #52 (AI Classification)
```bash
gh pr checks 52
```

**Expected Output:**
```
✓ Run Tests                  passed
✓ E2E Tests                  passed
✓ Lint and Format            passed
All checks passed
```

**If Checks Fail:**
- [ ] View failure details: `gh pr checks 52 --watch`
- [ ] Click "Details" link to see logs
- [ ] Common issues:
  - Missing environment variable (add to GitHub Secrets)
  - Redis not available in CI (check workflow config)
  - OpenAI API key not set (add to secrets)
- [ ] Fix issues and push new commit
- [ ] Wait for checks to re-run

**Do Not Proceed Until PR #52 Checks Pass**

---

### 3.2 Check PR #53 (Usage Tracking)
```bash
gh pr checks 53
```

**Expected Output:**
```
✓ Run Tests                  passed
✓ E2E Tests                  passed
✓ Lint and Format            passed
All checks passed
```

**If Checks Fail:**
- [ ] Same troubleshooting as 3.1
- [ ] Review any migration-related errors
- [ ] Push fixes and wait for re-run

**Do Not Proceed Until PR #53 Checks Pass**

---

## Phase 4: Production Database Backup (10-15 min)

**Goal:** Create safety net for rollback if deployment goes wrong.

### 4.1 Backup Railway Database
```bash
# Get database URL from Railway
railway variables --service postgres

# Create timestamped backup
pg_dump $RAILWAY_DATABASE_URL > backups/backup_$(date +%Y%m%d_%H%M%S).sql

# Verify backup file size (should be >0 bytes)
ls -lh backups/backup_*.sql
```

**Expected Output:**
```
-rw-r--r-- 1 user user 1.2M Nov 6 10:30 backups/backup_20251106_103045.sql
```

**Verification:**
- [ ] Backup file created
- [ ] File size >0 bytes (not empty)
- [ ] File contains SQL statements (open in editor)

**If Backup Fails:**
- [ ] Check `$RAILWAY_DATABASE_URL` is set
- [ ] Ensure `pg_dump` is installed
- [ ] Check database connection: `psql $RAILWAY_DATABASE_URL -c "SELECT 1"`
- [ ] Don't proceed without valid backup

---

### 4.2 Document Rollback Strategy
```bash
# Save this command for emergency rollback
echo "psql $RAILWAY_DATABASE_URL < backups/backup_$(date +%Y%m%d)_*.sql" > ROLLBACK_COMMAND.txt
```

**Rollback Plan:**
1. Stop Railway web service
2. Restore database from backup (command above)
3. Rollback code: `git revert <commit-hash>`
4. Deploy rollback: `git push origin main`
5. Restart Railway web service

---

## Phase 5: Merge and Deploy (20-30 min)

**Goal:** Deploy changes to production in correct order.

### 5.1 Merge PR #52 (AI Classification) First
```bash
# Ensure you're on main and up-to-date
git checkout main
git pull origin main

# Merge PR #52 (squash merge to keep history clean)
gh pr merge 52 --squash --delete-branch

# Wait for Railway auto-deploy
railway logs --tail 100
```

**Expected Output:**
```
[Railway] Deployment started...
[Railway] Building...
[Railway] Deploying...
[Railway] Deployment successful
```

**Verification Checklist:**
- [ ] PR #52 merged successfully
- [ ] Railway deployment succeeded
- [ ] No errors in logs
- [ ] Health check: `curl https://inbox-janitor-production-03fc.up.railway.app/health`

**If Deployment Fails:**
- [ ] Check Railway logs for error messages
- [ ] Common issues:
  - Missing environment variable (add to Railway)
  - Import error (check module paths)
  - Redis connection error (verify Redis service)
- [ ] Fix issues and re-deploy
- [ ] Don't proceed until deployment succeeds

---

### 5.2 Rebase PR #53 (Usage Tracking) on Latest Main
```bash
# Checkout PR #53 branch
git fetch origin
git checkout usage-tracking  # Or whatever branch name

# Rebase on latest main (includes PR #52)
git rebase origin/main

# Resolve merge conflicts in app/tasks/classify.py
# You'll need to manually merge:
# - AI classification code from PR #52 (tier1/tier2 logic)
# - Usage tracking code from PR #53 (limit checking, counter increment)
```

**Merge Conflict Resolution:**

Open `app/tasks/classify.py` and combine both features:

```python
# CORRECT: Combined version
async def _classify():
    # ... existing code ...

    # AI fallback (from PR #52)
    if tier1_result.confidence < settings.AI_CONFIDENCE_THRESHOLD:
        tier2_result = await classify_email_tier2(metadata)
        result = combine_tier1_tier2_results(tier1_result, tier2_result)
    else:
        result = tier1_result

    # Usage limit checking (from PR #53)
    if user_settings.has_reached_monthly_limit:
        await send_usage_limit_reached_email(mailbox.user_id, user_settings)
        return {"status": "limit_reached", ...}

    # ... store email_action ...

    # Increment usage counters (from PR #53)
    user_settings.emails_processed_this_month += 1

    # Track AI cost if AI was used (from PR #52)
    if tier2_result:  # AI was used
        user_settings.ai_cost_this_month += tier2_result.cost
```

**After Resolving Conflicts:**
```bash
# Verify no syntax errors
python3 -m py_compile app/tasks/classify.py

# Continue rebase
git add app/tasks/classify.py
git rebase --continue

# Force push rebased branch
git push origin usage-tracking --force

# Verify tests still pass after rebase
pytest tests/unit/test_usage_tracking.py -v
```

**Verification:**
- [ ] Rebase completed without errors
- [ ] Merge conflicts resolved
- [ ] Tests still pass
- [ ] CI checks re-run and pass on rebased PR

---

### 5.3 Merge PR #53 (Usage Tracking)
```bash
# Merge PR #53 (squash merge)
gh pr merge 53 --squash --delete-branch

# Wait for Railway auto-deploy
railway logs --tail 100
```

**Expected Output:**
```
[Railway] Deployment started...
[Railway] Building...
[Railway] Deploying...
[Railway] Deployment successful
```

**Verification:**
- [ ] PR #53 merged successfully
- [ ] Railway deployment succeeded
- [ ] Health check: `curl https://inbox-janitor-production-03fc.up.railway.app/health`

---

### 5.4 Run Database Migration on Production
```bash
# SSH into Railway or run migration via Railway CLI
railway run alembic upgrade head

# Verify migration applied
railway run alembic current
```

**Expected Output:**
```
INFO  [alembic.runtime.migration] Running upgrade 005 -> 006, add usage tracking to user_settings
006_add_usage_tracking_to_user_settings (head)
```

**Verification:**
- [ ] Migration ran successfully
- [ ] No errors in output
- [ ] `alembic current` shows version 006

**If Migration Fails:**
- [ ] Check Railway logs for error details
- [ ] Verify database connection
- [ ] Check if migration already applied: `railway run alembic current`
- [ ] If stuck, rollback: `railway run alembic downgrade -1`

---

### 5.5 Post-Deployment Health Check
```bash
# Test health endpoint
curl https://inbox-janitor-production-03fc.up.railway.app/health

# Expected response
{
  "status": "ok",
  "database": "connected",
  "redis": "connected",
  "version": "0.2.0"
}
```

**Verification Checklist:**
- [ ] Health endpoint returns 200 OK
- [ ] Database connected
- [ ] Redis connected
- [ ] No errors in Railway logs (past 10 minutes)

**If Health Check Fails:**
- [ ] Check Railway logs: `railway logs --tail 100`
- [ ] Verify environment variables set
- [ ] Test database connection
- [ ] If critical failure, execute rollback plan (Phase 4.2)

---

## Phase 6: Real-World Testing (1-2 hours)

**Goal:** Test as first real user to verify everything works end-to-end.

### 6.1 Initial Setup Testing
- [ ] Navigate to landing page: https://inbox-janitor-production-03fc.up.railway.app/
- [ ] Click "Connect Gmail" button
- [ ] Complete OAuth flow
- [ ] Verify redirect to dashboard
- [ ] Check database: User and Mailbox records created

```bash
railway run psql $DATABASE_URL -c "SELECT id, email FROM users ORDER BY created_at DESC LIMIT 1;"
railway run psql $DATABASE_URL -c "SELECT id, user_id, email_address, is_active FROM mailboxes ORDER BY created_at DESC LIMIT 1;"
```

---

### 6.2 Email Processing Testing (Sandbox Mode)

**Important:** Verify you're in sandbox mode first!
```bash
railway run psql $DATABASE_URL -c "SELECT user_id, action_mode_enabled FROM user_settings WHERE user_id = '<your-user-id>';"
# action_mode_enabled should be FALSE (sandbox mode)
```

**Test 1: Process a Real Email**
- [ ] Send yourself a promotional email (or wait for one to arrive)
- [ ] Trigger webhook (or wait for Gmail push notification)
- [ ] Check Railway logs for classification task
- [ ] Verify email_action record created

```bash
# Check logs for classification
railway logs --filter "Classifying email" | tail -20

# Check email_actions table
railway run psql $DATABASE_URL -c "SELECT message_id, action, confidence, created_at FROM email_actions ORDER BY created_at DESC LIMIT 5;"
```

**Expected:**
- [ ] Email classified (TRASH/ARCHIVE/KEEP)
- [ ] email_actions record exists
- [ ] Confidence score logged
- [ ] AI tier logged (tier_1 or tier_2)
- [ ] No actual Gmail action taken (sandbox mode)

---

### 6.3 Usage Tracking Testing

**Test 1: Counter Increments**
```bash
# Check initial counter
railway run psql $DATABASE_URL -c "SELECT emails_processed_this_month, ai_cost_this_month FROM user_settings WHERE user_id = '<your-user-id>';"

# Process 5-10 emails (send yourself test emails or wait)

# Check counter incremented
railway run psql $DATABASE_URL -c "SELECT emails_processed_this_month, ai_cost_this_month FROM user_settings WHERE user_id = '<your-user-id>';"
```

**Expected:**
- [ ] Counter increments by 1 for each email processed
- [ ] AI cost increments when Tier 2 AI used
- [ ] No overflow or negative values

---

**Test 2: 80% Warning Email**
```bash
# Manually set counter to 8,000 (80% of 10K limit)
railway run psql $DATABASE_URL -c "UPDATE user_settings SET emails_processed_this_month = 8000 WHERE user_id = '<your-user-id>';"

# Process 1 more email (trigger warning at multiple of 100)
# Send yourself an email

# Check logs for warning email
railway logs --filter "approaching monthly limit" | tail -10
```

**Expected:**
- [ ] Warning logged at 80% usage
- [ ] Email notification attempted (check logs)
- [ ] Processing continues (not blocked)

---

**Test 3: 100% Limit Reached**
```bash
# Set counter to 10,000 (100% of limit)
railway run psql $DATABASE_URL -c "UPDATE user_settings SET emails_processed_this_month = 10000 WHERE user_id = '<your-user-id>';"

# Try to process 1 more email
# Send yourself an email

# Check logs for limit reached
railway logs --filter "limit_reached" | tail -10

# Check email_actions - should NOT have new record
railway run psql $DATABASE_URL -c "SELECT COUNT(*) FROM email_actions WHERE mailbox_id = '<your-mailbox-id>' AND created_at > NOW() - INTERVAL '5 minutes';"
```

**Expected:**
- [ ] Email classification stops at limit
- [ ] Limit reached email notification attempted
- [ ] No new email_action record created
- [ ] Status returned: `{"status": "limit_reached"}`

---

**Test 4: Reset Counter**
```bash
# Reset counter back to 0
railway run psql $DATABASE_URL -c "UPDATE user_settings SET emails_processed_this_month = 0 WHERE user_id = '<your-user-id>';"

# Verify processing resumes
# Send yourself an email

# Check logs and database
railway logs --filter "Classifying email" | tail -10
railway run psql $DATABASE_URL -c "SELECT emails_processed_this_month FROM user_settings WHERE user_id = '<your-user-id>';"
```

**Expected:**
- [ ] Processing resumes after reset
- [ ] Counter increments normally again

---

### 6.4 AI Classification Testing

**Test 1: Tier 1 Classification (High Confidence)**
- [ ] Send yourself an obvious promotional email (e.g., marketing blast from Old Navy)
- [ ] Check logs for Tier 1 classification

```bash
railway logs --filter "tier_1" | tail -10
```

**Expected:**
- [ ] Classified as TRASH
- [ ] Confidence >= 0.90
- [ ] No AI API call made (Tier 1 only)
- [ ] No AI cost added

---

**Test 2: Tier 2 AI Fallback (Low Confidence)**
- [ ] Send yourself an ambiguous email (e.g., newsletter from Medium or Substack)
- [ ] Check logs for AI classification

```bash
railway logs --filter "tier_2" | tail -10
railway logs --filter "OpenAI API" | tail -10
```

**Expected:**
- [ ] Tier 1 confidence < 0.90
- [ ] Tier 2 AI called
- [ ] Combined result logged
- [ ] AI cost added to user_settings.ai_cost_this_month

---

**Test 3: AI Cache Hit**
- [ ] Send another email from same sender with similar subject
- [ ] Check logs for cache hit

```bash
railway logs --filter "cache_hit" | tail -10
```

**Expected:**
- [ ] Cache hit logged
- [ ] No OpenAI API call made
- [ ] No additional AI cost
- [ ] Classification still accurate

---

### 6.5 Monthly Reset Testing

**Test 1: Manual Trigger Reset Task**
```bash
# Trigger monthly reset task manually
railway run python -c "from app.tasks.usage_reset import reset_monthly_usage; reset_monthly_usage()"

# Check logs
railway logs --filter "Monthly usage reset" | tail -20

# Verify counters reset
railway run psql $DATABASE_URL -c "SELECT emails_processed_this_month, ai_cost_this_month, current_billing_period_start FROM user_settings WHERE user_id = '<your-user-id>';"
```

**Expected:**
- [ ] Counters reset to 0
- [ ] billing_period_start updated to today
- [ ] Usage summary email attempted (check logs)
- [ ] Task completes without errors

---

**Test 2: Billing Period Check Task**
```bash
# Set billing period to 35 days ago (stale)
railway run psql $DATABASE_URL -c "UPDATE user_settings SET current_billing_period_start = CURRENT_DATE - INTERVAL '35 days' WHERE user_id = '<your-user-id>';"

# Trigger check task
railway run python -c "from app.tasks.usage_reset import check_billing_periods; check_billing_periods()"

# Check logs
railway logs --filter "stale billing period" | tail -20

# Verify reset happened
railway run psql $DATABASE_URL -c "SELECT current_billing_period_start, emails_processed_this_month FROM user_settings WHERE user_id = '<your-user-id>';"
```

**Expected:**
- [ ] Stale billing period detected
- [ ] Counters reset
- [ ] billing_period_start updated to today
- [ ] Warning logged

---

## Phase 7: Risky Steps (Optional but Recommended)

**Goal:** Wire up critical features that are currently placeholders.

### 7.1 Postmark Email Integration (60-90 min)

**Current State:** Email functions just log to console (no actual emails sent)

**Why This Matters:**
- Users won't know when they hit 80% limit
- Users won't know when processing stops at 100%
- Manual intervention required to notify users

**Implementation Steps:**
- [ ] Sign up for Postmark (free tier: 100 emails/month)
- [ ] Create email templates in Postmark UI
- [ ] Add `POSTMARK_API_KEY` to Railway environment variables
- [ ] Implement actual email sending in `app/core/email_service.py`
- [ ] Test all 3 email types:
  - Usage warning (80%)
  - Limit reached (100%)
  - Monthly usage summary

**Mitigation if Skipped:**
- Monitor Railway logs daily
- Manually email users who hit limits (check logs)
- Add to backlog for Week 2

---

### 7.2 Build Upgrade Flow (2-3 hours)

**Current State:** Users can't upgrade from Starter (10K) to Pro (25K) or Business (100K)

**Why This Matters:**
- High-volume users will hit limit and churn
- Revenue loss from users willing to pay more

**Implementation Steps:**
- [ ] Create `/account/upgrade` page
- [ ] Integrate Stripe Checkout
- [ ] Handle subscription webhooks
- [ ] Update `user_settings.plan_tier` and `monthly_email_limit` on upgrade
- [ ] Test upgrade flow end-to-end

**Mitigation if Skipped:**
- Manually upgrade users via Stripe dashboard when they email
- Direct users to Stripe payment link
- Add to backlog for Week 2

---

### 7.3 Add Usage Monitoring Dashboard (1-2 hours)

**Current State:** No visibility into usage patterns across all users

**Why This Matters:**
- Can't detect if >10% users hitting limits (pricing problem)
- Can't see AI cost trends (budget risk)
- Can't identify high-value users to upsell

**Implementation Steps:**
- [ ] Create `/admin/usage` page (admin-only)
- [ ] Add usage charts (emails processed, AI costs, limit hits)
- [ ] Add alerts if >10% users hit limits
- [ ] Add daily summary email to admin

**Mitigation if Skipped:**
- Run manual SQL queries weekly
- Check Railway logs for limit_reached events
- Add to backlog for Month 2

---

## Success Criteria

**Deployment is successful if:**
- [x] All unit tests pass locally
- [x] All CI/CD checks pass
- [x] Database migration runs cleanly
- [x] Production backup created
- [x] Both PRs merged in correct order
- [x] Railway deployment succeeds
- [x] Health check returns 200 OK
- [ ] Email processing works (sandbox mode)
- [ ] Usage tracking increments correctly
- [ ] 80% warning triggers
- [ ] 100% limit blocks processing
- [ ] AI classification works (both Tier 1 and Tier 2)
- [ ] Cache hits reduce API costs
- [ ] Monthly reset task works

**Ready for production when:**
- All success criteria above are met
- At least 1 week of real-world testing complete
- No critical bugs discovered
- Postmark integration tested (or manual email process documented)

---

## Emergency Procedures

### If Deployment Breaks Production

**Immediate Actions:**
1. Check health endpoint: `curl https://inbox-janitor-production.../health`
2. Check Railway logs: `railway logs --tail 100`
3. If database error, restore from backup (Phase 4.2)
4. If code error, rollback:
   ```bash
   git revert HEAD
   git push origin main
   ```
5. Monitor Railway auto-deploy
6. Verify health endpoint returns 200 OK

---

### If Users Report Missing Emails

**Investigation:**
1. Check `email_actions` table for their emails
2. Verify sandbox mode (action_mode_enabled = false)
3. Check Gmail API logs for any delete/archive calls
4. If real deletion occurred:
   - Pause their mailbox immediately
   - Restore from Gmail Trash (30-day window)
   - Email user with apology and explanation
   - Investigate root cause before resuming

---

### If Usage Tracking Goes Wrong

**Common Issues:**
- Counter increments incorrectly: Check `classify.py` logic
- Limit not enforced: Check `has_reached_monthly_limit` property
- AI cost not tracked: Verify Tier 2 classifier returns cost
- Monthly reset fails: Check Celery Beat schedule and task execution

**Mitigation:**
- Manual SQL fixes for incorrect counters
- Emergency reset: `UPDATE user_settings SET emails_processed_this_month = 0`

---

## Next Session Preparation

**Before starting next session, have ready:**
1. This checklist (print or open in browser)
2. Railway CLI authenticated
3. Database backup confirmed
4. All PRs showing green checks
5. Coffee/water (3-5 hour session)

**What to tell Claude in next session:**
> "I'm ready to begin testing deployment. Please guide me through DEPLOYMENT_CHECKLIST.md step-by-step, starting with Phase 1. Wait for my confirmation after each phase before proceeding."

---

**Good luck! This is a big milestone. Take your time and don't skip critical steps.**
