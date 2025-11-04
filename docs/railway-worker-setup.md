# Railway Worker Service Setup

This document explains how to set up the Celery worker service on Railway.

## Overview

The Inbox Janitor application requires TWO Railway services:

1. **Web Service** - Handles HTTP traffic (FastAPI, webhooks, API endpoints)
2. **Worker Service** - Processes background tasks (Celery worker + beat scheduler)

Both services use the same codebase but different start commands.

---

## Step 1: Create Redis Service

If not already created:

1. Go to Railway dashboard
2. Click **"New"** → **"Database"** → **"Add Redis"**
3. Note the `REDIS_URL` environment variable (automatically created)

---

## Step 2: Create Worker Service

1. In Railway project, click **"New Service"**
2. Select **"GitHub Repo"** → Choose `inbox-janitor` repository
3. Name the service: **"inbox-janitor-worker"**
4. Configure start command:
   - **Custom Start Command:** `celery -A app.core.celery_app worker --loglevel=info --beat --scheduler=celery.beat:PersistentScheduler`
   - Or use Procfile: Set **"Procfile Path"** to `Procfile.worker`

---

## Step 3: Configure Environment Variables

The worker service needs the **SAME environment variables** as the web service:

### Required Variables

```bash
# Database
DATABASE_URL=<from Railway PostgreSQL service>

# Redis (Celery broker)
REDIS_URL=<from Railway Redis service>

# Security & Encryption
SECRET_KEY=<same as web service>
ENCRYPTION_KEY=<same as web service>

# OAuth - Google
GOOGLE_CLIENT_ID=<same as web service>
GOOGLE_CLIENT_SECRET=<same as web service>

# OpenAI API
OPENAI_API_KEY=<same as web service>

# Postmark Email
POSTMARK_API_KEY=<same as web service>
POSTMARK_FROM_EMAIL=<same as web service>

# Google Cloud Pub/Sub (for Gmail webhooks)
GOOGLE_PROJECT_ID=<your GCP project ID>
GOOGLE_PUBSUB_TOPIC=projects/<PROJECT_ID>/topics/inbox-janitor-gmail
GOOGLE_PUBSUB_SUBSCRIPTION=projects/<PROJECT_ID>/subscriptions/inbox-janitor-gmail-sub

# App Configuration
APP_URL=https://inbox-janitor-production-03fc.up.railway.app
ENVIRONMENT=production
DEBUG=False

# Optional: Sentry Monitoring
SENTRY_DSN=<your Sentry DSN>
```

### Copy Variables from Web Service

The easiest way:
1. Go to your web service settings
2. Copy all environment variables
3. Paste into worker service environment variables
4. Verify `REDIS_URL` points to Redis service

---

## Step 4: Verify Deployment

After deploying the worker service:

1. **Check logs** for successful startup:
   ```
   [2025-11-04 12:00:00,000: INFO/MainProcess] Connected to redis://...
   [2025-11-04 12:00:00,000: INFO/MainProcess] celery@... ready.
   [2025-11-04 12:00:00,000: INFO/Beat] beat: Starting...
   ```

2. **Verify beat schedule** in logs:
   ```
   [2025-11-04 12:00:00,000: INFO/Beat] Scheduler: Sending due task renew-gmail-watches
   [2025-11-04 12:00:00,000: INFO/Beat] Scheduler: Sending due task fallback-poll-gmail
   ```

3. **Check health endpoint** on web service:
   ```bash
   curl https://inbox-janitor-production-03fc.up.railway.app/health
   ```
   Should show `celery_queue_length` metric.

---

## Step 5: Scale Configuration

### Initial Setup (MVP)
- **Worker instances:** 1
- **Memory:** 512 MB
- **CPU:** Shared

### Scale at 100+ Users
- **Worker instances:** 2-3
- **Memory:** 1 GB
- **Add priority worker:** Dedicated worker for priority queue

---

## Troubleshooting

### Worker won't start

**Error:** `ModuleNotFoundError: No module named 'celery'`
- **Fix:** Verify `requirements.txt` includes `celery[redis]>=5.4.0`
- **Fix:** Ensure Railway is installing dependencies (check build logs)

### Redis connection failed

**Error:** `Error: Cannot connect to redis://...`
- **Fix:** Verify `REDIS_URL` environment variable is set
- **Fix:** Verify Redis service is running in Railway
- **Fix:** Check Redis service is in same Railway project

### Tasks not executing

**Issue:** Tasks enqueued but not processed
- **Check:** Worker service is running (not crashed)
- **Check:** Worker logs show `celery@... ready.`
- **Check:** Redis connection healthy
- **Fix:** Restart worker service

### Beat schedule not running

**Issue:** Periodic tasks not executing at scheduled times
- **Check:** Worker started with `--beat` flag
- **Check:** Logs show `beat: Starting...`
- **Check:** PersistentScheduler is used (prevents duplicate schedules)

---

## Commands for Local Testing

### Start worker locally:
```bash
celery -A app.core.celery_app worker --loglevel=info
```

### Start worker + beat locally:
```bash
celery -A app.core.celery_app worker --loglevel=info --beat
```

### Monitor Celery tasks:
```bash
celery -A app.core.celery_app inspect active
celery -A app.core.celery_app inspect scheduled
celery -A app.core.celery_app inspect stats
```

### Purge all tasks (clear queue):
```bash
celery -A app.core.celery_app purge
```

---

## Cost Estimate

**Railway Pricing (November 2025):**
- Worker service (512 MB, always running): ~$10/month
- Redis (256 MB): ~$5/month
- **Total additional cost:** ~$15/month

**At scale (100+ users):**
- 2-3 worker instances: ~$25-30/month
- Redis (512 MB): ~$10/month
- **Total:** ~$35-40/month

---

## Next Steps

After worker service is deployed:

1. ✅ Verify worker logs show successful startup
2. ✅ Test task execution with test task (Task 1.4)
3. ✅ Check health endpoint includes Celery metrics
4. ✅ Monitor Sentry for worker errors
5. ✅ Set up alerts for worker crashes
