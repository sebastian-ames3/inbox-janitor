# Google Cloud Pub/Sub Setup for Gmail Push Notifications

This document explains how to set up Google Cloud Pub/Sub to receive Gmail push notifications via webhooks.

## Overview

Gmail Push Notifications allow real-time email processing without polling:

1. Your app registers a "watch" on a Gmail account
2. Gmail publishes notifications to a Google Cloud Pub/Sub topic
3. Pub/Sub pushes messages to your webhook endpoint
4. Your app processes new emails in real-time

**Benefits:**
- Real-time email processing (notifications within seconds)
- Lower API quota usage (no polling required)
- Automatic email detection

**Requirements:**
- Google Cloud Platform project (same as OAuth credentials)
- Cloud Pub/Sub API enabled
- Webhook endpoint accessible from internet (Railway provides this)

---

## Step 1: Enable Cloud Pub/Sub API

1. Go to [Google Cloud Console](https://console.cloud.google.com/)
2. Select your project (same project as OAuth credentials)
3. Go to **APIs & Services** → **Library**
4. Search for **"Cloud Pub/Sub API"**
5. Click **Enable**

---

## Step 2: Create Pub/Sub Topic

The topic receives notifications from Gmail.

### Option A: Using gcloud CLI

```bash
# Set your project ID
export PROJECT_ID="your-gcp-project-id"

# Create topic
gcloud pubsub topics create inbox-janitor-gmail --project=$PROJECT_ID

# Verify
gcloud pubsub topics list --project=$PROJECT_ID
```

### Option B: Using Cloud Console

1. Go to **Pub/Sub** → **Topics**
2. Click **Create Topic**
3. **Topic ID:** `inbox-janitor-gmail`
4. Leave other settings as default
5. Click **Create**

**Topic name format:**
```
projects/<PROJECT_ID>/topics/inbox-janitor-gmail
```

This is the value for `GOOGLE_PUBSUB_TOPIC` environment variable.

---

## Step 3: Create Push Subscription

The subscription pushes messages to your webhook endpoint.

### Get your Railway webhook URL

Your webhook URL will be:
```
https://inbox-janitor-production-03fc.up.railway.app/webhooks/gmail
```

Replace `inbox-janitor-production-03fc` with your Railway service URL.

### Option A: Using gcloud CLI

```bash
# Set variables
export PROJECT_ID="your-gcp-project-id"
export WEBHOOK_URL="https://inbox-janitor-production-03fc.up.railway.app/webhooks/gmail"

# Create push subscription
gcloud pubsub subscriptions create inbox-janitor-gmail-sub \
  --topic=inbox-janitor-gmail \
  --push-endpoint=$WEBHOOK_URL \
  --ack-deadline=30 \
  --message-retention-duration=7d \
  --project=$PROJECT_ID

# Verify
gcloud pubsub subscriptions describe inbox-janitor-gmail-sub --project=$PROJECT_ID
```

### Option B: Using Cloud Console

1. Go to **Pub/Sub** → **Subscriptions**
2. Click **Create Subscription**
3. **Subscription ID:** `inbox-janitor-gmail-sub`
4. **Select a Cloud Pub/Sub topic:** `inbox-janitor-gmail`
5. **Delivery type:** Push
6. **Endpoint URL:** `https://inbox-janitor-production-03fc.up.railway.app/webhooks/gmail`
7. **Acknowledgement deadline:** 30 seconds
8. **Message retention duration:** 7 days
9. Click **Create**

---

## Step 4: Grant Gmail Permissions (Automatic)

Gmail needs permission to publish to your Pub/Sub topic.

**Good news:** This happens automatically when you call `users().watch()` API!

When you register a Gmail watch (via `register_gmail_watch()` function), Gmail automatically:
1. Grants itself publish permission on the topic
2. Starts sending notifications

**You don't need to manually configure permissions.**

---

## Step 5: Set Environment Variables

Add these to your Railway services (both web and worker):

```bash
# Google Cloud Project
GOOGLE_PROJECT_ID=your-gcp-project-id

# Pub/Sub Topic (full name)
GOOGLE_PUBSUB_TOPIC=projects/your-gcp-project-id/topics/inbox-janitor-gmail

# Pub/Sub Subscription (optional, for monitoring)
GOOGLE_PUBSUB_SUBSCRIPTION=projects/your-gcp-project-id/subscriptions/inbox-janitor-gmail-sub
```

**How to get your PROJECT_ID:**
1. Go to [Google Cloud Console](https://console.cloud.google.com/)
2. Click the project dropdown at the top
3. Copy the **Project ID** (not the Project Name)

---

## Step 6: Test Webhook Endpoint

Before registering watches, verify your webhook endpoint is accessible:

```bash
# Test endpoint is live
curl https://inbox-janitor-production-03fc.up.railway.app/webhooks/gmail

# Should return 405 Method Not Allowed (it only accepts POST)
# This confirms endpoint exists
```

Test with a POST request:

```bash
curl -X POST https://inbox-janitor-production-03fc.up.railway.app/webhooks/gmail \
  -H "Content-Type: application/json" \
  -d '{
    "message": {
      "data": "eyJlbWFpbEFkZHJlc3MiOiJ0ZXN0QGdtYWlsLmNvbSIsImhpc3RvcnlJZCI6IjEyMzQ1In0=",
      "messageId": "test-message-id",
      "publishTime": "2025-11-04T12:00:00Z"
    }
  }'

# Should return 200 OK
```

---

## Step 7: Register First Watch

After Pub/Sub is set up, register a Gmail watch:

### Option A: Automatic (via OAuth flow)

When a user connects their Gmail account, the watch is registered automatically.

### Option B: Manual (Python shell)

```python
# Open Python shell on Railway
import asyncio
from app.modules.ingest.gmail_watch import register_gmail_watch

# Replace with actual mailbox ID from database
mailbox_id = "your-mailbox-uuid"

# Register watch
watch_data = asyncio.run(register_gmail_watch(mailbox_id))
print(f"Watch registered! Expires at: {watch_data['expiration']}")
```

### Option C: Manual (Celery task)

```bash
# From Railway CLI or local terminal
celery -A app.core.celery_app call app.tasks.ingest.renew_all_gmail_watches
```

---

## Step 8: Verify Webhooks are Working

### Check Railway Logs

After registering a watch, send yourself a test email:

1. Send email to the connected Gmail account
2. Check Railway logs for webhook activity:
   ```
   [INFO] Webhook received: mailbox_id=..., history_id=...
   [INFO] Processing Gmail history...
   ```

### Check Pub/Sub Metrics

In Google Cloud Console:
1. Go to **Pub/Sub** → **Subscriptions**
2. Click `inbox-janitor-gmail-sub`
3. View **Metrics** tab
4. Should see:
   - **Message publish rate** (messages coming from Gmail)
   - **Push success rate** (successful deliveries to webhook)

---

## Troubleshooting

### Webhook returns 404 Not Found

**Cause:** Endpoint not deployed or wrong URL

**Fix:**
1. Verify Railway deployment succeeded
2. Check correct URL: `https://<your-service>.up.railway.app/webhooks/gmail`
3. Verify FastAPI router includes webhook routes

### No webhooks received after registering watch

**Cause:** Pub/Sub subscription not configured correctly

**Fix:**
1. Verify subscription exists: `gcloud pubsub subscriptions list`
2. Check endpoint URL in subscription matches Railway URL
3. Send test email to Gmail account
4. Check Pub/Sub metrics for delivery failures

### Pub/Sub returns "Permission denied"

**Cause:** Gmail doesn't have publish permission on topic

**Fix:**
1. Re-register watch: `await register_gmail_watch(mailbox_id)`
2. Gmail will auto-grant itself permission
3. Verify in IAM: `gcloud pubsub topics get-iam-policy inbox-janitor-gmail`

### Watch expires after 7 days

**Cause:** Watch renewal task not running

**Fix:**
1. Verify Celery worker is running on Railway
2. Check worker logs for `renew_all_gmail_watches` task
3. Verify beat schedule is configured correctly
4. Manually trigger: `celery -A app.core.celery_app call app.tasks.ingest.renew_all_gmail_watches`

### Webhooks timeout (504 Gateway Timeout)

**Cause:** Webhook processing takes >30 seconds

**Fix:**
1. Webhook must return 200 OK within 10ms (before enqueuing tasks)
2. All processing should be asynchronous (Celery tasks)
3. Check logs for slow database queries

---

## Monitoring

### Health Check

Add Pub/Sub status to health endpoint:

```bash
curl https://inbox-janitor-production-03fc.up.railway.app/health | jq .
```

Should include:
```json
{
  "gmail_watches_active": 42,
  "last_webhook_received_at": "2025-11-04T12:34:56Z"
}
```

### Alerts

Set up alerts for:
- No webhooks received in 30 minutes (Pub/Sub down or watch expired)
- High webhook error rate (>5% failed deliveries)
- Watch expiration approaching (renew within 24 hours)

---

## Cost

**Free tier:**
- First 10 GB of messages: Free
- First 10,000 operations: Free

**At scale (100 users, ~50 emails/day each):**
- 5,000 emails/day = ~5 MB/day
- ~150 MB/month = **Free**

**At 1000 users:**
- 50,000 emails/day = ~50 MB/day
- ~1.5 GB/month = **Free**

Pub/Sub is effectively free for this use case.

---

## Security

### Webhook Authentication (Optional)

For additional security, verify Pub/Sub messages:

1. **Enable JWT verification** in Pub/Sub subscription
2. **Add verification to webhook endpoint:**

```python
from google.auth import jwt

def verify_pubsub_jwt(token: str) -> bool:
    """Verify Pub/Sub JWT token."""
    try:
        claims = jwt.decode(token, verify=True)
        return claims.get('email') == 'gmail-api-push@system.gserviceaccount.com'
    except:
        return False
```

---

## Alternative: Direct Push (No Pub/Sub)

For simpler setup, Gmail supports direct push without Pub/Sub:

**Not recommended because:**
- Less reliable (no retry mechanism)
- No message queuing (lost if webhook down)
- Harder to debug

**Use Pub/Sub for production.**

---

## Next Steps

After Pub/Sub is set up:

1. ✅ Deploy webhook endpoint (Task 3.0)
2. ✅ Register watches for all connected mailboxes
3. ✅ Monitor webhook delivery in Railway logs
4. ✅ Set up alerts for failed deliveries
5. ✅ Verify watch renewal works (check logs after 6 days)
