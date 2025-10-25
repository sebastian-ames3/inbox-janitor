# Railway Deployment Setup Guide

## How to Set Environment Variables in Railway

### Step 1: Access Your Railway Project
1. Go to https://railway.app
2. Log in to your account
3. Click on your `inbox-janitor` project

### Step 2: Open Variables Settings
1. Click on your **Web Service** (or the service you want to configure)
2. Click on the **Variables** tab at the top
3. Click **+ New Variable** button

### Step 3: Add Each Variable
For each variable below, click **+ New Variable** and add:
- **Variable name** (left field): The key (e.g., `SECRET_KEY`)
- **Value** (right field): The actual value

---

## Required Environment Variables

### 1. Security Keys (CRITICAL - Generate New for Production)

```bash
SECRET_KEY=6a6c4f255667cedf00f230d2fc1c0c369f94ae8d73c2c9d41922a056ef162b27
ENCRYPTION_KEY=IK3W-mWINkf9-gv5UX2RvpZ3NFlfGkj0zCnjG1Z9V6o=
```

**NOTE:** Copy these values EXACTLY as shown above. They've been freshly generated.

---

### 2. Application Settings

```bash
APP_NAME=Inbox Janitor
ENVIRONMENT=production
DEBUG=false
APP_URL=https://your-app-name.up.railway.app
```

**ACTION REQUIRED:** Replace `your-app-name` with your actual Railway domain.

To find your Railway domain:
- In Railway, click on your Web Service
- Click on the **Settings** tab
- Look for **Domains** section
- Copy the `.up.railway.app` URL

---

### 3. Database (Auto-configured by Railway)

Railway automatically sets `DATABASE_URL` when you add a PostgreSQL database.

**Check if it exists:**
- Go to Variables tab
- Look for `DATABASE_URL`
- If missing, add a PostgreSQL database:
  - Click **+ New** in your project
  - Select **Database** → **Add PostgreSQL**
  - Railway will auto-inject `DATABASE_URL`

---

### 4. Google OAuth (Gmail API)

```bash
GOOGLE_CLIENT_ID=your-google-client-id.apps.googleusercontent.com
GOOGLE_CLIENT_SECRET=your-google-client-secret
GOOGLE_REDIRECT_URI=https://your-app-name.up.railway.app/auth/google/callback
```

**ACTION REQUIRED:**
1. Go to https://console.cloud.google.com/apis/credentials
2. Create OAuth 2.0 Client ID (if you haven't already)
3. Add authorized redirect URI: `https://your-app-name.up.railway.app/auth/google/callback`
4. Copy Client ID and Client Secret
5. Replace values above

---

### 5. OpenAI API

```bash
OPENAI_API_KEY=sk-proj-your-openai-api-key-here
```

**ACTION REQUIRED:** Copy this from your `.env` file (you already have it).

---

### 6. Postmark (Email Service)

```bash
POSTMARK_API_KEY=your-postmark-server-token
POSTMARK_FROM_EMAIL=noreply@inboxjanitor.com
```

**ACTION REQUIRED:**
1. Sign up at https://account.postmarkapp.com/
2. Create a new server
3. Copy the **Server API Token**
4. Add a verified sender email address
5. Replace values above

**NOTE:** For testing, you can use Postmark's free tier (100 emails/month).

---

### 7. Redis (For Celery - Optional for MVP)

```bash
REDIS_URL=redis://redis:6379/0
```

**To add Redis:**
1. Click **+ New** in your Railway project
2. Select **Database** → **Add Redis**
3. Railway will auto-inject `REDIS_URL`

**NOTE:** You can skip Redis for initial testing. The app will still start without Celery.

---

### 8. Optional Variables (Can skip for now)

These are not required for initial testing:

```bash
# Google Cloud Pub/Sub (for Gmail webhooks - Week 2)
GOOGLE_PROJECT_ID=your-gcp-project-id
GOOGLE_PUBSUB_TOPIC=gmail-notifications
GOOGLE_PUBSUB_SUBSCRIPTION=gmail-notifications-sub

# Stripe (Week 6 - billing)
STRIPE_SECRET_KEY=sk_test_your-stripe-key
STRIPE_WEBHOOK_SECRET=whsec_your-webhook-secret

# Sentry (error monitoring)
SENTRY_DSN=https://your-sentry-dsn@sentry.io/project-id
```

---

## Quick Checklist

Before deploying, verify you have these in Railway Variables:

- [ ] `SECRET_KEY` (generated above)
- [ ] `ENCRYPTION_KEY` (generated above)
- [ ] `APP_URL` (your Railway domain)
- [ ] `ENVIRONMENT=production`
- [ ] `DEBUG=false`
- [ ] `DATABASE_URL` (auto-set by Railway PostgreSQL)
- [ ] `GOOGLE_CLIENT_ID`
- [ ] `GOOGLE_CLIENT_SECRET`
- [ ] `GOOGLE_REDIRECT_URI` (with your Railway domain)
- [ ] `OPENAI_API_KEY`
- [ ] `POSTMARK_API_KEY`
- [ ] `POSTMARK_FROM_EMAIL`

---

## After Setting Variables

1. **Save all variables** in Railway
2. **Redeploy** your service (Railway may auto-deploy when you add variables)
3. **Check logs** to ensure no missing variable errors:
   - Click on your Web Service
   - Click on the **Deployments** tab
   - Click on the latest deployment
   - View logs for any errors

---

## Troubleshooting

### Error: "Field required" in logs
**Cause:** Missing required environment variable

**Fix:** Check the error message for which variable is missing, then add it in Railway Variables.

### Error: "Database connection failed"
**Cause:** `DATABASE_URL` not set or PostgreSQL not added

**Fix:** Add PostgreSQL database to your Railway project.

### Error: "Invalid ENCRYPTION_KEY"
**Cause:** ENCRYPTION_KEY must be exactly 44 characters (Fernet key format)

**Fix:** Use the key generated above (do not modify it).

---

## Getting Your Railway Domain

If you don't know your Railway domain:

1. Go to Railway project
2. Click on your Web Service
3. Click **Settings** tab
4. Scroll to **Domains**
5. You'll see: `your-service.up.railway.app`
6. Copy this URL (with `https://`)

---

## Video Tutorial (Railway Variables)

If you prefer a video guide:
- Railway Docs: https://docs.railway.app/guides/variables

---

## Need Help?

If you get stuck:
1. Check Railway logs for specific error messages
2. Verify all variables are spelled correctly (case-sensitive!)
3. Ensure no extra spaces in variable values
4. Check that DATABASE_URL exists (should be auto-set)
