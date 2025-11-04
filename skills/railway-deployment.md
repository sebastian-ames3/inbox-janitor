# Railway Deployment Skill

## Purpose
Ensure successful deployments to Railway with proper environment setup, verification, and debugging.

## Overview

Railway deployments for Inbox Janitor must follow a strict verification process to prevent downtime and ensure all services start correctly.

**Critical Rule**: ALWAYS wait for Railway deployment to succeed before considering a push complete.

## Pre-Deployment Checklist

Before pushing to GitHub:

1. ✅ All tests pass locally (`pytest`)
2. ✅ Security tests pass (`pytest tests/security/`)
3. ✅ No secrets in code (check `.env` is gitignored)
4. ✅ Database migrations created (if models changed)
5. ✅ Dependencies updated (`requirements.txt`)
6. ✅ Local server starts without errors

## Environment Variables

### Required Variables (Production)

Railway auto-injects some variables, but these must be manually set:

```bash
# Security Keys (NEVER commit to git)
SECRET_KEY=<random 32-char string>  # For JWT signing
ENCRYPTION_KEY=<44-char Fernet key>  # For token encryption

# Application
APP_NAME=Inbox Janitor
ENVIRONMENT=production
DEBUG=false
APP_URL=https://your-app.up.railway.app  # Replace with actual domain

# Google OAuth
GOOGLE_CLIENT_ID=your-client-id.apps.googleusercontent.com
GOOGLE_CLIENT_SECRET=your-secret
GOOGLE_REDIRECT_URI=https://your-app.up.railway.app/auth/google/callback

# OpenAI
OPENAI_API_KEY=sk-proj-...

# Postmark
POSTMARK_API_KEY=your-server-token
POSTMARK_FROM_EMAIL=noreply@inboxjanitor.com

# Database (auto-set by Railway PostgreSQL)
DATABASE_URL=postgresql://...  # Auto-injected

# Redis (auto-set by Railway Redis)
REDIS_URL=redis://...  # Auto-injected
```

### How to Set Variables in Railway

1. Go to https://railway.app
2. Open your project
3. Click on the service (Web Service)
4. Click "Variables" tab
5. Click "+ New Variable"
6. Add each variable (name + value)
7. Save (Railway auto-redeploys)

### Validating Environment Variables

After deployment, check variables are loaded:

```bash
# Method 1: Check Railway logs
railway logs

# Look for startup messages:
# "Starting Inbox Janitor..."
# "Environment: production"

# Method 2: Hit health endpoint
curl https://your-app.up.railway.app/health

# Should return:
# {"status": "healthy", "service": "Inbox Janitor", "environment": "production"}
```

## Deployment Verification Workflow

### Step 1: Push to GitHub

```bash
git add .
git commit -m "Your commit message

🤖 Generated with [Claude Code](https://claude.com/claude-code)

Co-Authored-By: Claude <noreply@anthropic.com>"
git push
```

### Step 2: Monitor Railway Build

Railway auto-deploys on push to main. Monitor build progress:

1. Go to Railway dashboard
2. Click on your service
3. Click "Deployments" tab
4. Watch the latest deployment

**Build phases:**
- 🔵 Building... (installing dependencies)
- 🟢 Deployed (build succeeded)
- 🔴 Failed (build error - debug required)

### Step 3: Check Build Logs

If build fails, read logs for errors:

**Common Build Errors:**

| Error | Cause | Fix |
|-------|-------|-----|
| `ModuleNotFoundError` | Missing dependency | Add to `requirements.txt` |
| `SyntaxError` | Python syntax error | Fix locally, test, push again |
| `Package not found` | Wrong package name | Check PyPI for correct name |
| `Permission denied` | File permissions issue | Check file permissions in git |

### Step 4: Check Runtime Logs

After build succeeds, check if app starts:

```bash
railway logs --limit 50
```

**Look for:**
- ✅ "Starting Inbox Janitor..."
- ✅ "Environment: production"
- ✅ "Uvicorn running on..."
- ❌ "Field required" → Missing env var
- ❌ "Database connection failed" → DATABASE_URL not set
- ❌ "Invalid ENCRYPTION_KEY" → Wrong key format

### Step 5: Verify Health Endpoint

Test the deployed app:

```bash
curl https://your-app.up.railway.app/health
```

**Expected response (200 OK):**
```json
{
  "status": "healthy",
  "service": "Inbox Janitor",
  "environment": "production"
}
```

**Error responses:**
- 502 Bad Gateway → App failed to start (check logs)
- 503 Service Unavailable → App starting (wait 30 seconds, retry)
- 404 Not Found → Wrong URL or route not registered

### Step 6: Test Core Endpoints

After health check passes:

```bash
# Test root endpoint
curl https://your-app.up.railway.app/

# Test OAuth initiation (should redirect)
curl -I https://your-app.up.railway.app/auth/connect?user_email=test@example.com

# Test docs (if DEBUG=true)
curl https://your-app.up.railway.app/docs
```

## Database Migrations

### Creating Migrations

When database models change:

```bash
# Create migration
alembic revision --autogenerate -m "Add new column to users table"

# Review migration file
cat alembic/versions/xxx_add_new_column.py

# Test locally
alembic upgrade head

# Commit migration
git add alembic/versions/
git commit -m "Add database migration: new user column"
git push
```

### Running Migrations on Railway

Railway runs migrations automatically on deploy if configured in `Procfile`:

```
# Procfile (should already exist)
web: alembic upgrade head && uvicorn app.main:app --host 0.0.0.0 --port $PORT
```

**Migration order:**
1. Railway runs `alembic upgrade head`
2. Migrations apply to PostgreSQL
3. Then starts web server with `uvicorn`

**Verify migrations ran:**

```bash
# Check logs for migration messages
railway logs | grep "alembic"

# Should see:
# "Running upgrade xxx -> yyy, Add new column"
# "Migration complete"
```

### Rolling Back Migrations

If deployment fails due to migration:

```bash
# Downgrade one migration
alembic downgrade -1

# Check current revision
alembic current

# Deploy again
git push
```

## Debugging Failed Deployments

### 502 Bad Gateway

**Cause:** App failed to start

**Debug steps:**
1. Check runtime logs: `railway logs`
2. Look for Python exceptions
3. Check env vars are set
4. Verify DATABASE_URL exists
5. Test locally: `uvicorn app.main:app --reload`

### Missing Environment Variables

**Error in logs:** `pydantic_core._pydantic_core.ValidationError: Field required`

**Fix:**
1. Identify missing variable from error
2. Add in Railway Variables tab
3. Railway auto-redeploys
4. Check logs again

### Database Connection Errors

**Error in logs:** `could not connect to server` or `database "railway" does not exist`

**Fix:**
1. Verify PostgreSQL service is running in Railway
2. Check DATABASE_URL is auto-injected (should start with `postgresql://`)
3. Test connection from logs
4. If needed, restart PostgreSQL service

### Build Timeout

**Error:** `Build timed out after 10 minutes`

**Cause:** Large dependencies or slow download

**Fix:**
1. Reduce dependencies if possible
2. Use `--no-cache-dir` in pip install
3. Split large dependencies into separate step

## Rollback Procedure

If deployment breaks production:

### Option 1: Revert Git Commit

```bash
git revert HEAD
git push
# Railway auto-deploys previous version
```

### Option 2: Redeploy Previous Version in Railway

1. Go to Railway dashboard
2. Click "Deployments"
3. Find last working deployment
4. Click "..." → "Redeploy"

### Option 3: Emergency Rollback (Database)

If migration broke database:

```bash
# Downgrade migration
alembic downgrade -1

# Deploy rollback
git add alembic/
git commit -m "Rollback migration"
git push
```

## Monitoring After Deployment

### First 10 Minutes

Watch for:
- Error rate spike in Railway logs
- OAuth failures (401 errors)
- Database connection issues
- Missing env var errors

### Health Check Monitoring

Set up periodic health checks:

```bash
# Use cron or external service (UptimeRobot, etc.)
*/5 * * * * curl -f https://your-app.up.railway.app/health || alert
```

## Railway Services Architecture

Inbox Janitor uses multiple Railway services:

1. **Web Service** (FastAPI + Celery Beat)
   - Handles HTTP requests
   - Runs Celery beat scheduler

2. **Worker Service** (Celery Worker) - Not yet implemented
   - Processes background jobs
   - Same codebase, different command

3. **PostgreSQL Database**
   - Managed by Railway
   - Auto-backups (7 days)

4. **Redis Cache**
   - Celery message broker
   - Rate limiting cache

## Quick Reference

### Common Railway Commands

```bash
# View logs
railway logs

# View logs (last 100 lines)
railway logs --limit 100

# View logs (follow mode)
railway logs --follow

# Check service status
railway status

# Link to Railway project (first time)
railway link
```

### Environment Variable Checklist

```bash
# Quick check: these should all return values in Railway
echo $DATABASE_URL
echo $REDIS_URL
echo $SECRET_KEY
echo $ENCRYPTION_KEY
echo $GOOGLE_CLIENT_ID
echo $GOOGLE_CLIENT_SECRET
echo $OPENAI_API_KEY
echo $POSTMARK_API_KEY
```

## When Unsure

Before deploying if uncertain:

1. Test locally: `uvicorn app.main:app --reload`
2. Run tests: `pytest`
3. Check for secrets: `git secrets --scan`
4. Review CHANGELOG.md for recent deployment changes
5. Ask for review if security-critical changes

## Related Skills

- **git-workflow.md** - Commit patterns and Railway verification
- **testing-requirements.md** - Tests to run before deploy
- **security-first.md** - Secrets management
