# Security-First Development Skill

## Purpose
Ensure all development on Inbox Janitor follows critical security requirements to protect user data and OAuth tokens.

## Core Security Principles

### 1. Token Protection (CRITICAL)
**NEVER log OAuth tokens in any circumstances**

Before writing any code that touches tokens:
- Check for `logger.info()`, `print()`, or `Logger.log()` statements
- Verify tokens are encrypted before database storage using `encrypt_token()`
- Use `sanitize_for_logging()` for any user data logging
- Tokens should only be decrypted right before Gmail API calls

Example patterns to AVOID:
```python
# ❌ WRONG - logs token
logger.info(f"Got token: {access_token}")

# ❌ WRONG - stores plaintext
mailbox.access_token = token

# ❌ WRONG - returns token in API response
return {"token": access_token}
```

Example patterns to FOLLOW:
```python
# ✅ CORRECT - encrypt before storage
mailbox.encrypted_access_token = encrypt_token(access_token)

# ✅ CORRECT - decrypt only when needed
token = decrypt_token(mailbox.encrypted_access_token)
gmail_service = build_gmail_service(token)

# ✅ CORRECT - sanitized logging
safe_data = sanitize_for_logging(email.from, email.subject, snippet)
logger.info("Processed email", extra=safe_data)
```

### 2. Email Body Storage (CRITICAL)
**NEVER store full email bodies in the database**

Rules:
- Only store: `message_id`, `from_address`, `subject`, `snippet` (200 chars max)
- Database schema PROHIBITS body columns
- Process email bodies in-memory only (fetch → classify → discard)
- OpenAI receives only: domain (not full email), truncated subject, 200-char snippet

Before writing any model or endpoint:
- Check that no `body`, `html_body`, or `content` fields exist
- Verify snippet truncation to 200 chars
- Ensure no email content caching

### 3. Data Deletion Safety (CRITICAL)
**NEVER permanently delete emails**

Rules:
- Gmail `.delete()` method is BANNED from codebase
- All trash actions use `.moveToTrash()` (30-day recovery)
- 7-day quarantine before trash
- 30-day undo window for all actions
- Starred emails NEVER touched
- Exception keywords protect important emails

Before implementing any email action:
- Verify no `.delete()` calls
- Check for quarantine label application
- Ensure undo deadline calculation
- Validate exception keyword checks

### 4. SQL Injection Protection
**ALWAYS use parameterized queries**

SQLAlchemy ORM handles this, but verify:
- No raw SQL string concatenation
- No `text()` queries with user input
- Use SQLAlchemy filters, not f-strings

### 5. Pre-Commit Checklist

Before suggesting ANY code change:
1. ✅ No tokens logged or exposed
2. ✅ No email bodies stored
3. ✅ No permanent delete methods
4. ✅ Encryption used for sensitive data
5. ✅ Parameterized queries only

## Testing Requirements

Every security-related change must include tests:
- `test_token_encryption()` - Verify Fernet encryption
- `test_token_not_in_logs()` - Ensure no token leakage
- `test_no_body_in_database()` - Schema validation
- `test_sql_injection()` - Parameterized query check
- `test_no_permanent_delete_method()` - No .delete() calls

## Common Mistakes to Avoid

1. **Logging for debugging**: Even in dev, never log tokens
2. **Temporary storage**: "I'll just store the body temporarily" - NO
3. **API responses**: Never return decrypted tokens in responses
4. **Error messages**: Don't expose tokens in error messages

## When Unsure

If you're not sure whether something violates security requirements:
1. Reference `/app/core/security.py` for encryption patterns
2. Check `/CHANGELOG.md` for security decisions
3. Ask the developer to review before implementing

## Integration with Other Skills

When building security-critical features:
- Use **ai-dev-workflow.md** for complex features (OAuth, encryption, webhooks)
- Follow **testing-requirements.md** to write security tests
- Reference **fastapi-module-builder.md** for secure module patterns
- Use **git-workflow.md** to ensure security tests pass before commit

## Emergency Response

If a security violation is discovered:
1. Stop all processing immediately
2. Document the violation type
3. Notify the developer
4. Propose remediation steps

## Related Skills

- **testing-requirements.md** - Security tests to write
- **fastapi-module-builder.md** - Secure module patterns
- **git-workflow.md** - Pre-commit security checks
- **ai-dev-workflow.md** - Structured approach for security features
