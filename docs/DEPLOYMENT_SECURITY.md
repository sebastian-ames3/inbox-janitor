# Security Middleware & Session Management - Deployment Guide

**Created:** 2025-11-04
**Feature Branch:** `feature/web-portal-security-middleware`
**Related PRD:** 0002 - Web Portal Foundation + Email Templates

---

## Overview

This document describes the security middleware and session management infrastructure added for the web portal foundation. All changes follow security-first principles from `/skills/security-first.md`.

---

## New Environment Variables

### Required for Production (Railway)

Add these to Railway environment variables before deploying:

#### 1. SESSION_SECRET_KEY (NEW - REQUIRED)

```bash
# Generate with:
python -c "import secrets; print(secrets.token_urlsafe(32))"

# Add to Railway:
SESSION_SECRET_KEY=<generated-value>
```

**Purpose:** Encrypts session cookies for web portal authentication.

**IMPORTANT:**
- Use a DIFFERENT key from `SECRET_KEY` for defense in depth
- Rotating this key will log out all users (plan accordingly)
- Minimum 32 bytes (43 characters base64-encoded)

#### 2. Verify Existing Variables

Ensure these are already set in Railway (required for new email features):

```bash
POSTMARK_API_KEY=<your-postmark-server-token>
POSTMARK_FROM_EMAIL=noreply@inboxjanitor.com
REDIS_URL=<auto-set-by-railway>
```

---

## New Dependencies

Added to `requirements.txt`:

```txt
# Security Middleware
starlette-csrf==2.1.0      # CSRF protection
slowapi==0.1.9             # Rate limiting
itsdangerous==2.1.2        # Session signing

# Email Service
postmarker==1.0            # Postmark API client (replaced python-postmark)

# Utilities
python-dateutil==2.8.2     # Date parsing for digest emails
jinja2==3.1.4              # HTML template rendering
```

**To Install:**
```bash
pip install -r requirements.txt
```

---

## Security Features Implemented

### 1. Session Management

**File:** `app/core/session.py`

- Cookie-based sessions (encrypted, signed)
- 24-hour expiration (auto-logout)
- Session regeneration after login (prevents session fixation)
- Session validation on every authenticated request

**Session Configuration:**
- Cookie name: `session`
- Max age: 86400 seconds (24 hours)
- SameSite: `Lax` (CSRF protection)
- HttpOnly: `True` (JavaScript cannot access)
- Secure: `True` (HTTPS only in production)

### 2. CSRF Protection

**File:** `app/core/middleware.py`

- Token-based CSRF protection on all state-changing requests
- Cookie + header validation (double-submit pattern)
- Exempted endpoints: `/health`, `/webhooks/*` (external services)

**Client Implementation:**
- All forms must include CSRF token (hidden input)
- HTMX automatically sends `X-CSRF-Token` header
- Token available in cookie: `csrf_token`

### 3. Rate Limiting

**Implementation:** SlowAPI with Redis backend

**Default Limits:**
- General endpoints: 200 requests/minute per IP
- OAuth endpoints: 5 requests/minute per IP (set in routes)
- Settings updates: 30 requests/minute per user (set in routes)

**Headers Sent:**
- `X-RateLimit-Limit`: Maximum requests allowed
- `X-RateLimit-Remaining`: Remaining requests
- `X-RateLimit-Reset`: Time when limit resets

**Response on Exceeded:**
- Status: `429 Too Many Requests`
- JSON: `{"error": "Rate limit exceeded"}`

### 4. Security Headers

**File:** `app/core/middleware.py` - `SecurityHeadersMiddleware`

All responses include:

```http
X-Content-Type-Options: nosniff
X-Frame-Options: DENY
X-XSS-Protection: 1; mode=block
Referrer-Policy: strict-origin-when-cross-origin
Permissions-Policy: geolocation=(), microphone=(), camera=()
Content-Security-Policy: [see below]
```

**Production Only:**
```http
Strict-Transport-Security: max-age=31536000; includeSubDomains
```

**Content Security Policy:**
```
default-src 'self';
script-src 'self' 'unsafe-inline' https://unpkg.com https://cdn.jsdelivr.net;
style-src 'self' 'unsafe-inline' https://fonts.googleapis.com https://cdn.jsdelivr.net;
font-src 'self' https://fonts.gstatic.com;
img-src 'self' data: https:;
connect-src 'self';
frame-ancestors 'none';
base-uri 'self';
form-action 'self';
```

**Note:** `'unsafe-inline'` is temporarily allowed for Alpine.js and HTMX. In V1, consider using CSP nonces for better security.

### 5. Authentication Dependency

**File:** `app/modules/portal/dependencies.py`

**Function:** `get_current_user()`

- Validates session contains `user_id`
- Checks session age (expires after 24 hours)
- Queries database for user
- Returns `User` object or raises `401 Unauthorized`

**Usage in Routes:**
```python
from app.modules.portal.dependencies import get_current_user

@router.get("/dashboard")
async def dashboard(user: User = Depends(get_current_user)):
    return {"email": user.email}
```

**Optional Authentication:**
```python
from app.modules.portal.dependencies import get_current_user_optional

@router.get("/")
async def landing(user: User | None = Depends(get_current_user_optional)):
    if user:
        # Redirect logged-in users to dashboard
        return RedirectResponse("/dashboard")
    else:
        # Show landing page
        return templates.TemplateResponse("landing.html", {...})
```

---

## Middleware Order (CRITICAL)

Middleware is applied in this order (from `app/main.py`):

1. **CORS** - Allow cross-origin requests (development only)
2. **SessionMiddleware** - Parse session cookies
3. **CSRFMiddleware** - Validate CSRF tokens
4. **Rate Limiting** - Check request limits
5. **SecurityHeadersMiddleware** - Add security headers to responses

**Why Order Matters:**
- Session must be parsed before CSRF (CSRF uses session)
- Rate limiting before business logic (protect resources)
- Security headers last (applied to all responses)

---

## Testing the Security Setup

### 1. Session Management

```bash
# Test session creation (login)
curl -c cookies.txt http://localhost:8000/auth/google/callback

# Test authenticated endpoint
curl -b cookies.txt http://localhost:8000/dashboard

# Test session expiration (24 hours later)
# Should return 401 Unauthorized
```

### 2. CSRF Protection

```bash
# Test POST without CSRF token (should fail)
curl -X POST http://localhost:8000/api/settings/update
# Expected: 403 Forbidden

# Test POST with valid CSRF token (should succeed)
curl -X POST http://localhost:8000/api/settings/update \
  -H "X-CSRF-Token: <token-from-cookie>" \
  -b cookies.txt
```

### 3. Rate Limiting

```bash
# Test rate limit (send 10 rapid requests)
for i in {1..10}; do
  curl http://localhost:8000/auth/google/login
done
# 6th request should return 429
```

### 4. Security Headers

```bash
# Check headers are present
curl -I http://localhost:8000/
# Should see X-Frame-Options, CSP, etc.
```

---

## Railway Deployment Checklist

Before deploying to production:

- [ ] Add `SESSION_SECRET_KEY` to Railway environment variables
- [ ] Verify `REDIS_URL` is set (required for rate limiting)
- [ ] Verify `POSTMARK_API_KEY` is set (required for email)
- [ ] Set `ENVIRONMENT=production` (enables HTTPS-only cookies, HSTS header)
- [ ] Run `pip install -r requirements.txt` in Railway build
- [ ] Verify health check: `https://inbox-janitor-production-03fc.up.railway.app/health`
- [ ] Test login flow: Landing → OAuth → Dashboard
- [ ] Verify session persists across page refreshes
- [ ] Test logout clears session
- [ ] Verify CSRF protection (check browser DevTools for csrf_token cookie)

---

## Security Considerations

### Token Separation

We now have THREE different keys:

1. **SECRET_KEY** - JWT tokens for OAuth state, magic links
2. **SESSION_SECRET_KEY** - Session cookie encryption (NEW)
3. **ENCRYPTION_KEY** - Fernet encryption for OAuth access/refresh tokens

**Why separate keys?**
- Defense in depth: If one key is compromised, others remain secure
- Different rotation schedules: Session keys can rotate more frequently
- Different scopes: Session keys only affect logged-in users, not OAuth tokens

### Session Security

**Protections in place:**
- HttpOnly cookies (JavaScript cannot access)
- Secure flag in production (HTTPS only)
- SameSite=Lax (CSRF protection)
- 24-hour expiration (limited attack window)
- Session regeneration after login (prevents session fixation)

**Known limitations (acceptable for MVP):**
- Cookie-based sessions (not Redis-backed)
  - Scaling: Move to Redis at 100+ concurrent users
  - Reason: Simpler deployment, no additional infra
- No session revocation list
  - Mitigation: Short 24-hour expiration
  - V1: Add Redis-backed revocation list for admin-triggered logouts

### CSRF Protection

**Protections in place:**
- Token validation on all POST/PUT/DELETE requests
- Double-submit cookie pattern (cookie + header)
- Token tied to session (expires with session)
- Exempted webhooks (external services can't send CSRF tokens)

**Client requirements:**
- HTMX automatically sends X-CSRF-Token header (reads from cookie)
- Custom forms must include csrf_token hidden input
- AJAX requests must include X-CSRF-Token header

### Rate Limiting

**Why Redis-backed?**
- Shared state across multiple web instances (future horizontal scaling)
- Persistent across app restarts (prevents reset attacks)
- Fast lookup (< 1ms overhead per request)

**Current limits are conservative:**
- General: 200/min (should handle normal usage)
- OAuth: 5/min (prevent brute force, credential stuffing)
- Settings: 30/min (prevent abuse)

**Adjust if needed:**
- Increase general limit if legitimate users hit it
- Use per-user limits (not per-IP) for authenticated endpoints
- Add exponential backoff for repeated violations

---

## Rollback Plan

If deployment fails or security issues found:

### 1. Immediate Rollback

```bash
# Revert to previous Railway deployment
railway rollback

# Or revert git commit
git revert <commit-hash>
git push origin main
```

### 2. Disable Specific Middleware

To disable a specific security feature without full rollback:

```python
# In app/main.py, comment out the problematic middleware:

# configure_csrf(app)  # Temporarily disabled
```

### 3. Emergency Session Reset

If sessions are corrupted or SESSION_SECRET_KEY compromised:

```bash
# Rotate SESSION_SECRET_KEY in Railway
# All users will be logged out immediately
# Acceptable for beta with < 10 users
```

---

## Monitoring & Alerts

### Sentry Integration

Security events to monitor:

- 401 errors (authentication failures)
- 403 errors (CSRF failures)
- 429 errors (rate limit exceeded)
- Session validation errors

**Configure Sentry scrubbing** (if not already done):

```python
# In app/core/sentry.py
import sentry_sdk

sentry_sdk.init(
    dsn=settings.SENTRY_DSN,
    environment=settings.ENVIRONMENT,
    before_send=scrub_sensitive_data,
)

def scrub_sensitive_data(event, hint):
    # Remove session cookies from breadcrumbs
    if "request" in event:
        if "cookies" in event["request"]:
            event["request"]["cookies"] = {"session": "[Filtered]"}
    return event
```

### Railway Logs

Watch for:

```bash
# CSRF failures (potential attack)
railway logs | grep "CSRF"

# Rate limit exceeded (potential abuse)
railway logs | grep "429"

# Session errors (configuration issue)
railway logs | grep "session"
```

---

## Next Steps

After this deployment:

1. **Week 2 Task 3.0:** Landing Page & OAuth Flow Enhancement
   - Uses session management implemented here
   - Creates `/welcome` page after OAuth
   - Integrates with authentication dependency

2. **Week 2 Task 4.0:** Settings Dashboard
   - Protected by `get_current_user` dependency
   - CSRF protection on all form submissions
   - Rate limiting on settings updates

3. **Week 2 Task 5.0:** Email Templates & Postmark
   - Uses `postmarker` library added in this task
   - Sends welcome email after OAuth

---

## Support & Troubleshooting

### Common Issues

**Issue:** `SESSION_SECRET_KEY not found`
- **Fix:** Add to Railway environment variables
- **Command:** `railway variables set SESSION_SECRET_KEY=<value>`

**Issue:** `429 Rate limit exceeded` on normal usage
- **Fix:** Increase limit in `app/core/middleware.py`
- **Code:** `default_limits=["500/minute"]`

**Issue:** CSRF token missing in HTMX requests
- **Fix:** Ensure csrf_token cookie is set
- **Debug:** Check browser DevTools → Application → Cookies

**Issue:** Session not persisting across requests
- **Fix:** Check `SESSION_SECRET_KEY` is set correctly
- **Debug:** `railway logs | grep "session"`

---

**Document Status:** ✅ Ready for Deployment

**Last Updated:** 2025-11-04
