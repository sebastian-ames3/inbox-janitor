# Frontend Security Analysis: HTMX + Jinja2

**Last Updated:** 2025-11-04
**Status:** Pre-implementation security review

This document outlines ALL security risks for the HTMX + Jinja2 + Tailwind frontend and required mitigations.

---

## 🔴 CRITICAL Risks (Catastrophic Impact)

### 1. Cross-Site Scripting (XSS)

**Risk:** Attacker injects malicious JavaScript that steals OAuth tokens or session cookies.

**Attack Vector:**
- User-controlled data (email subjects, sender names) rendered in templates
- HTMX responses inject HTML without sanitization
- `| safe` filter bypasses Jinja2 auto-escaping

**Impact:** Full account takeover, token theft, session hijacking

**Mitigations:**

✅ **Jinja2 Auto-Escaping (Enabled by Default)**
```python
# app/main.py - Verify auto-escaping enabled
templates = Jinja2Templates(directory="app/templates")
templates.env.autoescape = True  # CRITICAL: Must be True
```

✅ **Never Use `| safe` Filter**
```jinja2
<!-- ❌ WRONG - bypasses escaping -->
<div>{{ email.subject | safe }}</div>

<!-- ✅ CORRECT - auto-escaped -->
<div>{{ email.subject }}</div>
```

✅ **Sanitize HTMX Responses**
```python
# app/modules/portal/routes.py
from markupsafe import escape

@router.post("/settings/update")
async def update_settings(form: SettingsForm):
    # HTMX returns HTML directly - must escape user input
    message = escape(form.custom_message)
    return f"<p class='text-green-600'>{message}</p>"
```

✅ **Content Security Policy (CSP)**
```python
# app/core/security.py
from fastapi import Response

def add_security_headers(response: Response):
    response.headers["Content-Security-Policy"] = (
        "default-src 'self'; "
        "script-src 'self' 'unsafe-inline'; "  # HTMX needs inline
        "style-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net; "  # Tailwind CDN
        "img-src 'self' data:; "
        "connect-src 'self'; "
        "frame-ancestors 'none'; "  # Prevent clickjacking
    )
    return response
```

✅ **Testing**
```python
# tests/security/test_xss.py
def test_xss_in_email_subject():
    """Verify malicious scripts in email subjects are escaped"""
    malicious_subject = "<script>alert('XSS')</script>"
    response = client.get(f"/audit?subject={malicious_subject}")
    assert "<script>" not in response.text  # Should be escaped
    assert "&lt;script&gt;" in response.text  # Should be HTML entities
```

---

### 2. Cross-Site Request Forgery (CSRF)

**Risk:** Attacker tricks user into submitting forms that change settings, delete data, or revoke access.

**Attack Vector:**
- User visits attacker's site while logged into Inbox Janitor
- Attacker's page makes HTMX POST request to `/settings/update`
- Request includes user's session cookie automatically
- Settings changed without user consent

**Impact:** Account takeover, data loss, unauthorized actions

**Mitigations:**

✅ **CSRF Token Middleware**
```python
# app/core/security.py
from starlette.middleware.sessions import SessionMiddleware
from starlette_csrf import CSRFMiddleware

def configure_security(app: FastAPI):
    # Session middleware (required for CSRF)
    app.add_middleware(
        SessionMiddleware,
        secret_key=settings.SECRET_KEY,
        max_age=86400,  # 24 hours
        same_site="lax",  # CSRF protection
        https_only=True  # Production only
    )

    # CSRF middleware
    app.add_middleware(
        CSRFMiddleware,
        secret=settings.SECRET_KEY,
        cookie_name="csrftoken",
        header_name="X-CSRFToken",
        cookie_secure=True,  # HTTPS only
        cookie_samesite="lax"
    )
```

✅ **CSRF Token in Forms**
```jinja2
<!-- app/templates/dashboard.html -->
<form hx-post="/settings/update" hx-headers='{"X-CSRFToken": "{{ csrf_token }}"}'>
    <input type="hidden" name="csrf_token" value="{{ csrf_token }}">
    <!-- form fields -->
    <button type="submit">Save Settings</button>
</form>
```

✅ **CSRF Token in HTMX Requests**
```html
<!-- Base template - Add CSRF token to all HTMX requests -->
<script>
document.body.addEventListener('htmx:configRequest', (event) => {
    event.detail.headers['X-CSRFToken'] = '{{ csrf_token }}';
});
</script>
```

✅ **Verify CSRF Token in Endpoints**
```python
# app/modules/portal/routes.py
from fastapi import Depends, HTTPException
from starlette_csrf import verify_csrf_token

@router.post("/settings/update")
async def update_settings(
    request: Request,
    csrf_token: str = Depends(verify_csrf_token)  # Automatically validates
):
    # If we reach here, CSRF token is valid
    await save_settings(request)
```

✅ **Testing**
```python
# tests/security/test_csrf.py
def test_csrf_protection():
    """Verify POST requests without CSRF token are rejected"""
    response = client.post("/settings/update", data={"threshold": 0.9})
    assert response.status_code == 403  # Forbidden

def test_csrf_with_valid_token():
    """Verify POST requests with valid CSRF token succeed"""
    csrf_token = client.get("/dashboard").cookies.get("csrftoken")
    response = client.post(
        "/settings/update",
        data={"threshold": 0.9},
        headers={"X-CSRFToken": csrf_token}
    )
    assert response.status_code == 200
```

---

### 3. Session Hijacking

**Risk:** Attacker steals session cookie and impersonates user.

**Attack Vectors:**
- XSS (steals cookie via JavaScript)
- Man-in-the-middle (HTTP instead of HTTPS)
- Session fixation (attacker sets victim's session ID)

**Impact:** Full account takeover, access to OAuth tokens

**Mitigations:**

✅ **Secure Session Configuration**
```python
# app/core/security.py
app.add_middleware(
    SessionMiddleware,
    secret_key=settings.SECRET_KEY,
    max_age=86400,  # 24 hours (short expiry)
    same_site="lax",  # Prevent CSRF
    https_only=True,  # Only over HTTPS
    http_only=True,  # JavaScript cannot access (prevents XSS theft)
    session_cookie="session",  # Custom name (obscurity)
    domain=None  # Don't allow subdomains
)
```

✅ **Session Regeneration After Login**
```python
# app/modules/auth/routes.py
@router.get("/auth/google/callback")
async def oauth_callback(request: Request):
    # Complete OAuth flow
    user = await create_or_update_user(tokens)

    # CRITICAL: Regenerate session after login
    old_session = request.session.copy()
    request.session.clear()
    request.session.update(old_session)
    request.session["user_id"] = str(user.id)

    # Store session creation time
    request.session["created_at"] = datetime.utcnow().isoformat()
```

✅ **Session Expiration**
```python
# app/core/dependencies.py
async def get_current_user(request: Request):
    user_id = request.session.get("user_id")
    created_at = request.session.get("created_at")

    if not user_id or not created_at:
        raise HTTPException(status_code=401, detail="Not authenticated")

    # Check session age (24 hours max)
    created = datetime.fromisoformat(created_at)
    if datetime.utcnow() - created > timedelta(hours=24):
        request.session.clear()
        raise HTTPException(status_code=401, detail="Session expired")

    return await get_user_by_id(user_id)
```

✅ **HTTPS Enforcement**
```python
# app/main.py
from fastapi.middleware.httpsredirect import HTTPSRedirectMiddleware

if settings.ENVIRONMENT == "production":
    app.add_middleware(HTTPSRedirectMiddleware)
```

✅ **HSTS Header**
```python
# app/core/security.py
def add_security_headers(response: Response):
    response.headers["Strict-Transport-Security"] = (
        "max-age=31536000; includeSubDomains; preload"
    )
```

✅ **Testing**
```python
# tests/security/test_sessions.py
def test_session_expires_after_24h():
    """Verify sessions expire after 24 hours"""
    response = client.get("/dashboard")
    session_cookie = response.cookies.get("session")

    # Fast-forward 25 hours (mock time)
    with freeze_time(datetime.utcnow() + timedelta(hours=25)):
        response = client.get("/dashboard", cookies={"session": session_cookie})
        assert response.status_code == 401

def test_session_regeneration_after_login():
    """Verify session ID changes after OAuth login"""
    old_session = client.cookies.get("session")
    client.get("/auth/google/callback?code=test")
    new_session = client.cookies.get("session")
    assert old_session != new_session
```

---

### 4. OAuth Token Exposure in Frontend

**Risk:** Decrypted OAuth tokens appear in HTML, JavaScript, or browser DevTools.

**Attack Vector:**
- Developer accidentally renders token in template
- Token in hidden form field
- Token in data attribute for JavaScript
- Token in error message

**Impact:** Full Gmail access for attacker

**Mitigations:**

✅ **NEVER Pass Tokens to Templates**
```python
# ❌ WRONG - token visible in HTML source
@router.get("/dashboard")
async def dashboard(user: User):
    mailbox = await get_mailbox(user.id)
    return templates.TemplateResponse("dashboard.html", {
        "access_token": decrypt_token(mailbox.encrypted_access_token)  # NEVER DO THIS
    })

# ✅ CORRECT - only pass non-sensitive data
@router.get("/dashboard")
async def dashboard(user: User):
    mailbox = await get_mailbox(user.id)
    return templates.TemplateResponse("dashboard.html", {
        "email_address": mailbox.email_address,
        "is_active": mailbox.is_active,
        "connected_at": mailbox.created_at
    })
```

✅ **Backend-Only Token Access**
```python
# app/modules/executor/service.py
async def archive_email(user_id: UUID, message_id: str):
    """Tokens only decrypted in backend, never sent to frontend"""
    mailbox = await get_mailbox_by_user(user_id)
    token = decrypt_token(mailbox.encrypted_access_token)  # In-memory only

    # Use token immediately, don't store
    gmail = build_gmail_service(token)
    gmail.users().messages().modify(userId='me', id=message_id, ...)

    # Token discarded after function completes
```

✅ **Sentry Scrubbing**
```python
# app/core/monitoring.py
import sentry_sdk

sentry_sdk.init(
    dsn=settings.SENTRY_DSN,
    before_send=scrub_sensitive_data,
)

def scrub_sensitive_data(event, hint):
    """Remove tokens from Sentry events (including DOM snapshots)"""
    if 'request' in event:
        # Remove from request data
        if 'data' in event['request']:
            event['request']['data'] = '[REDACTED]'

        # Remove from cookies
        if 'cookies' in event['request']:
            event['request']['cookies'] = {}

    # Remove from breadcrumbs
    if 'breadcrumbs' in event:
        for crumb in event['breadcrumbs']:
            if 'data' in crumb:
                crumb['data'] = '[REDACTED]'

    return event
```

✅ **Testing**
```python
# tests/security/test_token_exposure.py
def test_no_tokens_in_html():
    """Verify tokens never appear in rendered HTML"""
    response = client.get("/dashboard")
    html = response.text

    # Check for token patterns
    assert "ya29." not in html  # Google token prefix
    assert "access_token" not in html
    assert "refresh_token" not in html
    assert "encrypted_" not in html
```

---

## 🟠 HIGH Risks (Severe Impact)

### 5. Clickjacking

**Risk:** Attacker embeds Inbox Janitor in invisible iframe, tricks user into clicking.

**Attack Vector:**
```html
<!-- Attacker's page -->
<iframe src="https://inboxjanitor.com/settings" style="opacity:0;position:absolute;"></iframe>
<button style="position:absolute;top:200px;left:150px;">
  Click here for free prize!
</button>
<!-- User clicks "prize" button, actually clicks "Delete Account" underneath -->
```

**Impact:** Unauthorized actions (delete account, change settings)

**Mitigations:**

✅ **X-Frame-Options Header**
```python
# app/core/security.py
def add_security_headers(response: Response):
    response.headers["X-Frame-Options"] = "DENY"  # Never allow iframes
    response.headers["Content-Security-Policy"] += "frame-ancestors 'none';"
```

✅ **Testing**
```python
# tests/security/test_clickjacking.py
def test_x_frame_options():
    """Verify X-Frame-Options header prevents embedding"""
    response = client.get("/dashboard")
    assert response.headers["X-Frame-Options"] == "DENY"
```

---

### 6. Open Redirect

**Risk:** OAuth callback redirects to attacker's site, steals authorization code.

**Attack Vector:**
```
https://inboxjanitor.com/auth/google/callback?code=AUTH_CODE&redirect=https://evil.com
```

**Impact:** OAuth token theft

**Mitigations:**

✅ **Whitelist Redirect URLs**
```python
# app/modules/auth/routes.py
ALLOWED_REDIRECTS = [
    "https://inboxjanitor.com/dashboard",
    "https://inboxjanitor.com/settings",
    "/dashboard",  # Relative URLs only
    "/settings"
]

@router.get("/auth/google/callback")
async def oauth_callback(
    request: Request,
    redirect: str = "/dashboard"  # Default
):
    # Validate redirect URL
    if redirect not in ALLOWED_REDIRECTS:
        redirect = "/dashboard"  # Safe default

    # Complete OAuth...
    return RedirectResponse(url=redirect)
```

✅ **Testing**
```python
# tests/security/test_open_redirect.py
def test_open_redirect_blocked():
    """Verify external redirects are blocked"""
    response = client.get(
        "/auth/google/callback?code=test&redirect=https://evil.com"
    )
    assert response.headers["Location"] == "/dashboard"  # Safe default
```

---

### 7. Mass Assignment

**Risk:** User adds extra fields to form, gains unauthorized privileges.

**Attack Vector:**
```http
POST /settings/update
Content-Type: application/x-www-form-urlencoded

confidence_threshold=0.9&is_admin=true&billing_plan=pro
```

**Impact:** Privilege escalation, data manipulation

**Mitigations:**

✅ **Pydantic Models for Validation**
```python
# app/modules/portal/schemas.py
from pydantic import BaseModel, Field

class SettingsUpdate(BaseModel):
    confidence_auto_threshold: float = Field(ge=0.5, le=1.0)
    confidence_review_threshold: float = Field(ge=0.5, le=1.0)
    digest_schedule: str = Field(pattern="^(daily|weekly|off)$")

    # ONLY these fields are accepted
    # Extra fields (is_admin, billing_plan) are ignored

@router.post("/settings/update")
async def update_settings(
    settings: SettingsUpdate,  # Pydantic validates and strips extra fields
    user: User = Depends(get_current_user)
):
    await save_user_settings(user.id, settings)
```

✅ **Testing**
```python
# tests/security/test_mass_assignment.py
def test_mass_assignment_blocked():
    """Verify extra fields are ignored"""
    response = client.post("/settings/update", data={
        "confidence_threshold": 0.9,
        "is_admin": "true",  # Should be ignored
        "billing_plan": "pro"  # Should be ignored
    })

    user = get_user()
    assert user.is_admin == False  # Not changed
    assert user.billing_plan != "pro"  # Not changed
```

---

### 8. Rate Limiting

**Risk:** Brute force attacks on login, OAuth, or form submissions.

**Attack Vector:**
- 1000s of OAuth attempts to DoS Google API
- Brute force session cookies
- Spam form submissions

**Impact:** Account lockout, service disruption, API quota exhaustion

**Mitigations:**

✅ **Rate Limiting Middleware**
```python
# app/core/security.py
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded

limiter = Limiter(key_func=get_remote_address)

def configure_rate_limiting(app: FastAPI):
    app.state.limiter = limiter
    app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
```

✅ **Apply Limits to Endpoints**
```python
# app/modules/auth/routes.py
@router.get("/auth/google/login")
@limiter.limit("5/minute")  # Max 5 OAuth attempts per minute
async def oauth_login(request: Request):
    ...

@router.post("/settings/update")
@limiter.limit("30/minute")  # Max 30 form submissions per minute
async def update_settings(request: Request):
    ...
```

✅ **Testing**
```python
# tests/security/test_rate_limiting.py
def test_oauth_rate_limiting():
    """Verify OAuth endpoint rate limits work"""
    for i in range(6):  # Attempt 6 times (limit is 5)
        response = client.get("/auth/google/login")

    assert response.status_code == 429  # Too Many Requests
```

---

### 9. Email Injection

**Risk:** User-controlled data in email templates executes malicious code in recipient's email client.

**Attack Vector:**
```
User sets display name to: "User\nBcc: attacker@evil.com"
```

**Impact:** Spam sent from your domain, phishing

**Mitigations:**

✅ **Sanitize Email Headers**
```python
# app/modules/digest/service.py
import re

def sanitize_email_header(value: str) -> str:
    """Remove newlines and control characters from email headers"""
    # Remove newlines, carriage returns, null bytes
    value = re.sub(r'[\r\n\0]', '', value)
    return value.strip()

async def send_digest_email(user: User):
    # Sanitize all user-controlled fields
    safe_name = sanitize_email_header(user.display_name or "")
    safe_email = sanitize_email_header(user.email)

    await postmark.send_email(
        to=safe_email,
        from_name=safe_name,
        subject="Your Weekly Inbox Janitor Digest",
        ...
    )
```

✅ **Use Postmark Templates**
```python
# app/modules/digest/service.py
# Postmark templates automatically escape content
await postmark.send_with_template(
    template_id="weekly-digest",
    to=user.email,
    template_data={
        "user_name": user.display_name,  # Escaped by Postmark
        "actions_count": actions_count
    }
)
```

---

## 🟡 MEDIUM Risks (Moderate Impact)

### 10. Subdomain Takeover

**Risk:** If `inboxjanitor.com` points to Railway subdomain via CNAME, and Railway deployment is deleted, attacker can claim the subdomain.

**Mitigations:**

✅ **Use A Records Instead of CNAME**
```
# DNS Configuration
inboxjanitor.com.   A   <Railway IP address>
www.inboxjanitor.com. A   <Railway IP address>
```

✅ **Monitor Domain Configuration**
```python
# app/tasks/monitoring.py
@celery.task
def check_domain_health():
    """Verify domain resolves to our Railway deployment"""
    response = requests.get("https://inboxjanitor.com/health")
    if response.status_code != 200:
        alert_admin("Domain health check failed!")
```

---

### 11. Path Traversal (Static Files)

**Risk:** Attacker requests `/../../../etc/passwd` via static file route.

**Mitigations:**

✅ **Use StaticFiles Middleware (Secure by Default)**
```python
# app/main.py
from fastapi.staticfiles import StaticFiles

# StaticFiles automatically prevents path traversal
app.mount("/static", StaticFiles(directory="app/static"), name="static")
```

✅ **Testing**
```python
# tests/security/test_path_traversal.py
def test_path_traversal_blocked():
    """Verify path traversal attempts are blocked"""
    response = client.get("/static/../../../etc/passwd")
    assert response.status_code == 404  # Not found
```

---

## 🔵 Additional Security Hardening

### 12. Security Headers (Full Set)

```python
# app/core/security.py
def add_security_headers(response: Response) -> Response:
    """Add all security headers to responses"""
    headers = {
        # Prevent XSS
        "X-Content-Type-Options": "nosniff",
        "X-XSS-Protection": "1; mode=block",

        # Prevent clickjacking
        "X-Frame-Options": "DENY",

        # HTTPS enforcement
        "Strict-Transport-Security": "max-age=31536000; includeSubDomains; preload",

        # CSP
        "Content-Security-Policy": (
            "default-src 'self'; "
            "script-src 'self' 'unsafe-inline' https://unpkg.com; "  # HTMX + Alpine
            "style-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net; "  # Tailwind
            "img-src 'self' data:; "
            "connect-src 'self'; "
            "font-src 'self'; "
            "object-src 'none'; "
            "base-uri 'self'; "
            "form-action 'self'; "
            "frame-ancestors 'none'; "
            "upgrade-insecure-requests;"
        ),

        # Referrer policy
        "Referrer-Policy": "strict-origin-when-cross-origin",

        # Permissions policy
        "Permissions-Policy": "geolocation=(), microphone=(), camera=()"
    }

    for header, value in headers.items():
        response.headers[header] = value

    return response

# Apply to all responses
@app.middleware("http")
async def security_headers_middleware(request: Request, call_next):
    response = await call_next(request)
    return add_security_headers(response)
```

### 13. Audit Logging (Security Events)

```python
# app/core/audit.py
import logging

audit_logger = logging.getLogger("security.audit")

async def log_security_event(
    event_type: str,
    user_id: Optional[UUID],
    ip_address: str,
    details: dict
):
    """Log all security-relevant events"""
    audit_logger.info(
        f"Security event: {event_type}",
        extra={
            "event_type": event_type,
            "user_id": str(user_id) if user_id else None,
            "ip_address": ip_address,
            "timestamp": datetime.utcnow().isoformat(),
            **details
        }
    )

# Usage examples
await log_security_event("oauth_success", user.id, request.client.host, {})
await log_security_event("login_failed", None, request.client.host, {"reason": "invalid_session"})
await log_security_event("settings_changed", user.id, request.client.host, {"field": "confidence_threshold"})
```

---

## ✅ Security Checklist (Pre-Launch)

**Before deploying frontend to production:**

- [ ] CSRF protection enabled (starlette-csrf middleware)
- [ ] XSS protection enabled (Jinja2 auto-escaping verified)
- [ ] Session security configured (HTTPOnly, Secure, SameSite)
- [ ] CSP headers configured (default-src, script-src, frame-ancestors)
- [ ] HTTPS enforced (HTTPSRedirectMiddleware + HSTS)
- [ ] Rate limiting configured (slowapi on auth + form endpoints)
- [ ] OAuth redirect whitelist implemented
- [ ] Pydantic models for all form inputs (mass assignment protection)
- [ ] No tokens in templates (verified via tests)
- [ ] Email header sanitization (Postmark templates)
- [ ] Security headers applied (X-Frame-Options, X-Content-Type-Options, etc.)
- [ ] Audit logging enabled (security events tracked)
- [ ] All security tests passing (`pytest tests/security/`)
- [ ] Manual penetration testing complete (OWASP ZAP scan)

---

## 📚 Dependencies to Add

```bash
# requirements.txt
starlette-csrf==2.1.0  # CSRF protection
slowapi==0.1.9  # Rate limiting
python-multipart==0.0.6  # Form parsing
```

---

## 🔗 References

- OWASP Top 10: https://owasp.org/www-project-top-ten/
- HTMX Security: https://htmx.org/docs/#security
- FastAPI Security: https://fastapi.tiangolo.com/tutorial/security/
- CSP Guide: https://developer.mozilla.org/en-US/docs/Web/HTTP/CSP
