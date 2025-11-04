# Manual End-to-End Testing Guide

## Overview

This guide covers manual testing procedures for the email processing pipeline before and after deployment.

**Run these tests:**
1. Before every deployment
2. After Railway deployment completes
3. After database migrations
4. When adding new features

---

## Pre-Deployment Testing

### 1. Run Security Tests (REQUIRED)

```bash
# Activate virtual environment
source venv/bin/activate

# Run all security tests (MUST PASS)
pytest tests/security/ -v

# Individual security tests
pytest tests/security/test_token_encryption.py -v
pytest tests/security/test_no_body_storage.py -v
pytest tests/security/test_sql_injection.py -v
```

**Pass criteria:** ALL tests must pass. Zero failures accepted for security tests.

### 2. Run Classification Tests

```bash
# Run safety rails tests (CRITICAL)
pytest tests/classification/test_safety_rails.py -v

# Run signal calculation tests
pytest tests/classification/test_signals.py -v
```

**Pass criteria:** ALL safety rails tests must pass. Signal tests >95% pass rate.

### 3. Run Integration Tests

```bash
# Run full pipeline tests
pytest tests/test_integration.py -v -s
```

**Pass criteria:** >90% pass rate. Known issues documented.

### 4. Code Quality Checks

```bash
# Static security analysis
bandit -r app/ -f json -o bandit-report.json

# Type checking
mypy app/ --ignore-missing-imports

# Check for secrets in code
git secrets --scan
```

**Pass criteria:**
- Bandit: Zero HIGH or MEDIUM severity issues
- MyPy: Zero errors in critical paths (warnings acceptable)
- Git secrets: Zero secrets detected

---

## Post-Deployment Testing

### 1. Health Check Verification

```bash
# Check health endpoint
curl https://inbox-janitor-production-03fc.up.railway.app/health | jq .
```

**Expected response:**
```json
{
  "service": "Inbox Janitor",
  "version": "0.1.0",
  "environment": "production",
  "status": "healthy",
  "timestamp": "2025-01-04T12:00:00",
  "components": {
    "database": {
      "status": "healthy",
      "latency_ms": 15.2
    },
    "redis": {
      "status": "healthy",
      "latency_ms": 5.1
    },
    "gmail_api": {
      "status": "healthy",
      "configured": true
    },
    "openai_api": {
      "status": "healthy",
      "configured": true
    },
    "last_webhook": {
      "status": "healthy",
      "seconds_since_last": 245
    }
  }
}
```

**Pass criteria:**
- Overall status: "healthy" or "degraded" (not "unhealthy")
- Database latency <100ms
- Redis latency <50ms
- APIs configured: true

### 2. Database Migration Verification

```bash
# Connect to Railway production database
railway run alembic current

# Verify migration 002 is applied
railway run python << EOF
import asyncio
from app.core.database import get_async_session
from sqlalchemy import text

async def check_migration():
    async with get_async_session() as session:
        # Check email_metadata table exists
        result = await session.execute(text("""
            SELECT table_name FROM information_schema.tables
            WHERE table_name = 'email_metadata'
        """))
        assert result.scalar_one_or_none() == 'email_metadata'
        
        # Check event trigger exists
        result = await session.execute(text("""
            SELECT evtname FROM pg_event_trigger
            WHERE evtname = 'prevent_email_body_columns'
        """))
        assert result.scalar_one_or_none() == 'prevent_email_body_columns'
        
        print("✅ Migration 002 verified")

asyncio.run(check_migration())
