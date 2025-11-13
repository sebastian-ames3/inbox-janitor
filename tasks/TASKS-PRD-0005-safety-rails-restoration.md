# Task List: PRD-0005 Safety Rails Restoration

**PRD:** [PRD-0005: Safety Rails Restoration](./PRD-0005-safety-rails-restoration.md)
**Total Estimated Time:** 24 hours (3 days)
**Priority:** P0 (CRITICAL - Block billing launch)

---

## Task Overview

- [ ] **1.0 Collect baseline metrics** (4 hours)
- [ ] **2.0 Implement smart short subject detection** (8 hours)
- [ ] **3.0 Implement phrase-based exception keywords** (6 hours)
- [ ] **4.0 Test on production dataset** (4 hours)
- [ ] **5.0 Deploy and monitor** (2 hours)

---

## 1.0 Collect baseline metrics (4 hours)

### 1.1 Run classifier on 1000 test emails (1 hour)
**Files:** N/A (using production endpoint)

**Commands:**
```bash
# Classify 1000 emails in batches
curl -X POST "https://inbox-janitor-production-03fc.up.railway.app/webhooks/sample-and-classify?batch_size=250"
# Wait 2-3 minutes for processing
curl -X POST "https://inbox-janitor-production-03fc.up.railway.app/webhooks/sample-and-classify?batch_size=250"
# Wait 2-3 minutes
curl -X POST "https://inbox-janitor-production-03fc.up.railway.app/webhooks/sample-and-classify?batch_size=250"
# Wait 2-3 minutes
curl -X POST "https://inbox-janitor-production-03fc.up.railway.app/webhooks/sample-and-classify?batch_size=250"
```

**Acceptance Criteria:**
- [ ] 1000 emails processed
- [ ] Classification distribution recorded
- [ ] No errors during processing

---

### 1.2 Export baseline data (1 hour)
**Files:** N/A (database export)

**Commands:**
```bash
# Connect to Railway Postgres
railway connect postgres

# Export classification results
\copy (
  SELECT
    message_id,
    subject,
    from_address,
    snippet,
    action,
    reason,
    confidence,
    classification_metadata
  FROM email_actions
  WHERE created_at > NOW() - INTERVAL '1 hour'
  ORDER BY created_at DESC
) TO '/tmp/baseline_1000_emails.csv' CSV HEADER;
```

**Acceptance Criteria:**
- [ ] CSV exported with 1000 rows
- [ ] All columns present
- [ ] File saved locally for analysis

---

### 1.3 Analyze short subject emails (1 hour)
**Files:** `/tmp/baseline_1000_emails.csv` (local analysis)

**Analysis:**
1. Filter emails where `LENGTH(subject) < 5`
2. Manually classify 50 random short-subject emails:
   - Important (personal, from contact) = Keep
   - Marketing (promo, spam) = Should trash
3. Calculate current false positive rate:
   - How many important short-subject emails would be flagged?
4. Calculate current false negative rate:
   - How many marketing short-subject emails are kept?

**Deliverable:** Document in `/tmp/short_subject_analysis.md`:
```markdown
# Short Subject Analysis

## Sample Size
- Total emails analyzed: 1000
- Short subject emails (<5 chars): X
- Percentage: X%

## Manual Classification (50 random samples)
- Important (should keep): X
- Marketing (should trash): X

## Current Behavior (check_short_subject disabled)
- All short subjects treated equally (no special handling)

## Findings
- False positive rate if enabled (naive): X%
  (Important emails incorrectly flagged)
- False negative rate (current): X%
  (Marketing emails incorrectly kept)

## Recommendation
[Based on findings, what threshold/logic should we use?]
```

**Acceptance Criteria:**
- [ ] 50 emails manually classified
- [ ] False positive rate calculated
- [ ] Analysis documented

---

### 1.4 Analyze exception keyword "offer" (1 hour)
**Files:** `/tmp/baseline_1000_emails.csv`

**Analysis:**
1. Filter emails where subject or snippet contains "offer"
2. Manually classify 50 random "offer" emails:
   - Job offer = Should protect (keep)
   - Marketing offer = Should NOT protect (trash OK)
3. Calculate current false negative rate:
   - How many marketing offers are incorrectly protected?

**Deliverable:** Document in `/tmp/exception_keyword_analysis.md`:
```markdown
# Exception Keyword "offer" Analysis

## Sample Size
- Total emails with "offer": X
- Percentage: X%

## Manual Classification (50 samples)
- Job offers (should protect): X
- Marketing offers (should NOT protect): X

## Current Behavior
- Substring "offer" matches ALL occurrences
- Job offers: Protected ✅
- Marketing offers: Also protected ❌ (false negative)

## False Negative Rate
- Marketing offers incorrectly protected: X%

## Specific Phrases Found
Job offers:
- "job offer"
- "offer letter"
- "employment offer"
- "offer of employment"

Marketing offers:
- "special offer"
- "limited time offer"
- "exclusive offer"
- "offer expires"
- "50% off offer"

## Recommendation
Use phrase-based matching:
- Protect: "job offer", "offer letter", "employment offer"
- Do NOT protect: "special offer", "limited offer", etc.
```

**Acceptance Criteria:**
- [ ] 50 "offer" emails manually classified
- [ ] False negative rate calculated
- [ ] Specific phrases documented
- [ ] Analysis document saved

---

## 2.0 Implement smart short subject detection (8 hours)

### 2.1 Create smart check_short_subject() function (3 hours)
**Files:** `app/modules/classifier/safety_rails.py`

**Changes:**
Replace line 313 (disabled comment) with new implementation:

```python
def check_short_subject(subject: str, metadata: dict) -> bool:
    """
    Flag short subjects that are likely important.

    Short subjects (<5 chars) are only flagged if:
    - From known contact (metadata['from_contact'] = True)
    - High sender open rate (>50%)
    - All caps (personal urgency: "URGENT", "HELP")
    - Contains personal pronouns ("you", "your", "I", "me")
    - NOT from marketing domain
    - NOT common promo word

    Args:
        subject: Email subject line
        metadata: Email metadata dict with:
            - from_contact: bool (sender in user's contacts)
            - sender_open_rate: float (0-1, user's open rate for this sender)
            - from_domain: str (sender's domain)

    Returns:
        True if short subject should be flagged as potentially important

    Examples:
        >>> check_short_subject("Hi", {"from_contact": True})
        True  # Personal email from contact

        >>> check_short_subject("Sale", {"from_domain": "marketing.store.com"})
        False  # Marketing from known domain

        >>> check_short_subject("URGENT", {"from_contact": False, "sender_open_rate": 0.0})
        True  # All caps suggests personal urgency
    """
    subject_clean = subject.strip()

    # Not short - no concern
    if len(subject_clean) >= 5:
        return False

    # Check if from known contact
    if metadata.get("from_contact", False):
        return True  # Flag: personal email from contact

    # Check sender open rate
    sender_open_rate = metadata.get("sender_open_rate", 0.0)
    if sender_open_rate > 0.5:
        return True  # Flag: user opens this sender's emails

    # Check if all caps (personal urgency)
    if subject_clean.isupper() and len(subject_clean) > 1:
        return True  # Flag: "URGENT", "HELP", "FYI"

    # Check for personal pronouns
    personal_words = ["you", "your", "i", "me", "my", "our"]
    subject_lower = subject_clean.lower()
    if any(word == subject_lower for word in personal_words):
        return True  # Flag: personal language

    # Check if from marketing domain (don't flag)
    marketing_domains = [
        "sendgrid.net", "mailchimp", "klaviyo", "customeriomail.com",
        "campaignmonitor.com", "mailgun", "amazonses.com",
        "mail.", "marketing.", "promo.", "newsletter."
    ]
    from_domain = metadata.get("from_domain", "")
    if any(domain in from_domain.lower() for domain in marketing_domains):
        return False  # Don't flag: known marketing platform

    # Check if subject is common promo word (don't flag)
    promo_words = ["sale", "deal", "offer", "free", "save", "off", "buy"]
    if subject_lower in promo_words:
        return False  # Don't flag: clearly marketing

    # Default: flag unknown short subjects as caution
    # (Conservative approach - better to review than to trash)
    return True
```

**Acceptance Criteria:**
- [ ] Function implemented
- [ ] Docstring with examples
- [ ] Handles all edge cases
- [ ] Uses metadata fields correctly

---

### 2.2 Add metadata fields to extractor (2 hours)
**Files:** `app/modules/classifier/metadata_extractor.py`

**Changes:**
Add three new fields to metadata extraction:

1. **from_contact** - Check if sender in user's contacts
2. **sender_open_rate** - Query sender_stats table
3. **from_domain** - Extract domain from from_address

**Implementation:**
```python
async def extract_metadata(message_data: dict, mailbox_id: str, session: AsyncSession) -> dict:
    """Extract metadata from Gmail message."""
    # ... existing extraction ...

    # NEW: Check if from known contact
    from_contact = await is_sender_in_contacts(from_address, mailbox_id, session)

    # NEW: Get sender open rate
    sender_stats = await get_sender_stats(from_address, mailbox_id, session)
    sender_open_rate = (
        sender_stats.opened_count / sender_stats.total_received
        if sender_stats and sender_stats.total_received > 0
        else 0.0
    )

    # NEW: Extract from_domain
    from_domain = extract_domain(from_address)

    return {
        # ... existing fields ...
        "from_contact": from_contact,
        "sender_open_rate": sender_open_rate,
        "from_domain": from_domain,
    }
```

**Helper Functions:**
```python
async def is_sender_in_contacts(email: str, mailbox_id: str, session: AsyncSession) -> bool:
    """Check if sender is in user's Gmail contacts."""
    # TODO: Implement Gmail People API integration
    # For now, check if sender_stats shows high open rate (>0.8)
    stats = await get_sender_stats(email, mailbox_id, session)
    if stats and stats.total_received > 5:  # At least 5 emails
        return (stats.opened_count / stats.total_received) > 0.8
    return False


async def get_sender_stats(email: str, mailbox_id: str, session: AsyncSession):
    """Get sender statistics from database."""
    result = await session.execute(
        select(SenderStats).where(
            SenderStats.mailbox_id == mailbox_id,
            SenderStats.sender_address == email
        )
    )
    return result.scalar_one_or_none()


def extract_domain(email: str) -> str:
    """Extract domain from email address."""
    if "@" in email:
        return email.split("@")[1].lower()
    return ""
```

**Acceptance Criteria:**
- [ ] All three fields added to metadata
- [ ] Helper functions implemented
- [ ] Handles missing data gracefully
- [ ] No errors if sender_stats missing

---

### 2.3 Write unit tests for check_short_subject() (2 hours)
**Files:** `tests/classification/test_safety_rails.py`

**Changes:**
Add comprehensive tests:

```python
def test_check_short_subject_from_contact():
    """Short subject from contact should be flagged."""
    result = check_short_subject("Hi", {"from_contact": True})
    assert result is True


def test_check_short_subject_high_open_rate():
    """Short subject from high open rate sender should be flagged."""
    result = check_short_subject("FYI", {"from_contact": False, "sender_open_rate": 0.8})
    assert result is True


def test_check_short_subject_all_caps():
    """Short subject in all caps should be flagged (personal urgency)."""
    result = check_short_subject("URGENT", {"from_contact": False, "sender_open_rate": 0.0})
    assert result is True


def test_check_short_subject_personal_pronoun():
    """Short subject with personal pronoun should be flagged."""
    result = check_short_subject("you", {"from_contact": False})
    assert result is True


def test_check_short_subject_marketing_domain():
    """Short subject from marketing domain should NOT be flagged."""
    result = check_short_subject("Sale", {"from_contact": False, "from_domain": "marketing.store.com"})
    assert result is False


def test_check_short_subject_promo_word():
    """Short subject with promo word should NOT be flagged."""
    result = check_short_subject("sale", {"from_contact": False, "from_domain": "store.com"})
    assert result is False


def test_check_short_subject_unknown_sender():
    """Short subject from unknown sender with low open rate should be flagged (cautious)."""
    result = check_short_subject("Test", {"from_contact": False, "sender_open_rate": 0.0})
    assert result is True  # Default to flagging (cautious)


def test_check_short_subject_long_subject():
    """Long subject should NOT be flagged."""
    result = check_short_subject("This is a long subject line", {})
    assert result is False
```

**Acceptance Criteria:**
- [ ] All 8 tests written
- [ ] All tests pass
- [ ] Edge cases covered
- [ ] Test coverage >95% for function

---

### 2.4 Integration test with real emails (1 hour)
**Files:** `tests/classification/test_safety_rails_integration.py`

**Changes:**
Add integration test with realistic email data:

```python
@pytest.mark.asyncio
async def test_short_subject_integration(session):
    """Test short subject detection with realistic email data."""
    # Create test emails
    emails = [
        # Should be flagged (personal from contact)
        {
            "subject": "Hi",
            "from_address": "friend@example.com",
            "metadata": {"from_contact": True, "sender_open_rate": 0.9}
        },
        # Should NOT be flagged (marketing)
        {
            "subject": "Sale",
            "from_address": "promo@store.com",
            "metadata": {"from_contact": False, "from_domain": "store.com", "sender_open_rate": 0.0}
        },
        # Should be flagged (all caps urgency)
        {
            "subject": "HELP",
            "from_address": "unknown@example.com",
            "metadata": {"from_contact": False, "sender_open_rate": 0.0}
        },
    ]

    for email in emails:
        result = check_short_subject(email["subject"], email["metadata"])
        # Verify behavior matches expectation
        # (add assertions based on expected outcomes)
```

**Acceptance Criteria:**
- [ ] Integration test passes
- [ ] Tests realistic email scenarios
- [ ] No false positives in test data

---

## 3.0 Implement phrase-based exception keywords (6 hours)

### 3.1 Replace exception keywords with phrases (2 hours)
**Files:** `app/modules/classifier/safety_rails.py`

**Changes:**
Replace lines 22-107 (EXCEPTION_KEYWORDS list and has_exception_keyword function):

```python
# Exception phrases (specific, not substrings)
EXCEPTION_PHRASES = [
    # Financial
    "receipt", "invoice", "order confirmation", "payment", "billing",
    "subscription", "refund", "credit card",

    # Employment (specific phrases)
    "job offer", "offer letter", "employment offer", "offer of employment",
    "interview invitation", "interview schedule", "interview confirmation",

    # Critical personal
    "medical", "health record", "doctor", "appointment", "prescription",
    "hospital", "emergency",

    # Financial/tax
    "tax", "irs", "w-2", "w2", "1099", "tax return",

    # Legal
    "legal notice", "court", "lawyer", "attorney", "lawsuit",

    # Security
    "password reset", "security alert", "account locked",
    "verify your account", "suspicious activity",

    # Family/personal
    "funeral", "obituary", "birth announcement", "wedding invitation",
]

# Negative keywords (marketing language that disqualifies protection)
NEGATIVE_KEYWORDS = [
    # Marketing offers
    "special offer", "limited offer", "exclusive offer",
    "limited time offer", "offer expires", "offer ends",

    # Promotions
    "discount", "sale", "promo", "deal", "save",
    "% off", "percent off", "clearance",

    # Spam indicators
    "unsubscribe", "click here", "act now", "don't miss",
]


def has_exception_keyword(text: str) -> bool:
    """
    Check if text contains protected exception keywords.

    Uses phrase-based matching (not substring) and negative keyword filtering.

    Returns True if:
    - Contains exception phrase (e.g., "job offer")
    - Does NOT contain negative keyword (e.g., "special offer")

    Args:
        text: Combined subject + snippet (first 200 chars)

    Returns:
        True if email should be protected from classification

    Examples:
        >>> has_exception_keyword("Job offer for Senior Engineer")
        True  # Protected

        >>> has_exception_keyword("Special offer: 50% off")
        False  # Not protected (marketing)

        >>> has_exception_keyword("Your receipt for order #123")
        True  # Protected

        >>> has_exception_keyword("Limited time offer on your order")
        False  # Not protected ("limited time offer" is negative keyword)
    """
    text_lower = text.lower()

    # Check negative keywords first (disqualify marketing)
    for negative in NEGATIVE_KEYWORDS:
        if negative in text_lower:
            return False  # Marketing language - don't protect

    # Check exception phrases (protect important)
    for phrase in EXCEPTION_PHRASES:
        if phrase in text_lower:
            return True  # Protected

    return False  # No exception phrase found - allow classification
```

**Acceptance Criteria:**
- [ ] EXCEPTION_PHRASES list created
- [ ] NEGATIVE_KEYWORDS list created
- [ ] has_exception_keyword() function updated
- [ ] Docstring with examples

---

### 3.2 Write unit tests for phrase-based matching (2 hours)
**Files:** `tests/classification/test_safety_rails.py`

**Changes:**
Un-skip existing test and add new tests:

```python
def test_job_offer_protected():
    """Job offers should be protected."""
    assert has_exception_keyword("Job offer for Senior Engineer") is True
    assert has_exception_keyword("Offer letter - Software Engineer") is True
    assert has_exception_keyword("Employment offer from Acme Corp") is True


def test_marketing_offer_not_protected():
    """Marketing offers should NOT be protected."""
    assert has_exception_keyword("Special offer: 50% off") is False
    assert has_exception_keyword("Limited time offer expires soon") is False
    assert has_exception_keyword("Exclusive offer for members") is False


def test_receipt_protected():
    """Receipts should be protected."""
    assert has_exception_keyword("Your receipt for order #123") is True
    assert has_exception_keyword("Invoice for January services") is True


def test_financial_protected():
    """Financial emails should be protected."""
    assert has_exception_keyword("Your W-2 is ready") is True
    assert has_exception_keyword("Tax return submitted successfully") is True
    assert has_exception_keyword("Credit card statement") is True


def test_medical_protected():
    """Medical emails should be protected."""
    assert has_exception_keyword("Appointment reminder - Dr. Smith") is True
    assert has_exception_keyword("Your prescription is ready") is True


def test_security_protected():
    """Security alerts should be protected."""
    assert has_exception_keyword("Password reset requested") is True
    assert has_exception_keyword("Suspicious activity detected") is True


def test_marketing_with_protected_word_not_protected():
    """Marketing email containing protected word in marketing context should NOT be protected."""
    # "order" is protected, but "limited time offer" is negative keyword
    assert has_exception_keyword("Limited time offer on your order") is False

    # "special offer" trumps any protected words
    assert has_exception_keyword("Special offer: Free shipping on orders") is False


def test_edge_cases():
    """Edge cases should be handled correctly."""
    # Empty string
    assert has_exception_keyword("") is False

    # Only negative keywords
    assert has_exception_keyword("Discount sale clearance") is False

    # Both protected and negative (negative wins)
    assert has_exception_keyword("Special offer: job listings") is False
```

**Acceptance Criteria:**
- [ ] All 8 test categories pass
- [ ] Edge cases covered
- [ ] Test coverage >95%
- [ ] Previously skipped test now passing

---

### 3.3 Add phrase matching performance test (1 hour)
**Files:** `tests/classification/test_safety_rails_performance.py`

**Changes:**
Ensure phrase matching doesn't slow down classification:

```python
import time

def test_has_exception_keyword_performance():
    """Exception keyword checking should be fast (<1ms per call)."""
    # Test data: 100 realistic email subjects/snippets
    test_emails = [
        "Special offer: 50% off all items",
        "Your receipt for order #12345",
        "Job offer - Senior Software Engineer",
        # ... (97 more)
    ]

    start_time = time.time()

    for _ in range(10):  # 10 iterations
        for email in test_emails:
            has_exception_keyword(email)

    elapsed = time.time() - start_time
    avg_per_call = elapsed / (len(test_emails) * 10)

    # Should be <1ms per call (0.001 seconds)
    assert avg_per_call < 0.001, f"Too slow: {avg_per_call*1000:.2f}ms per call"
```

**Acceptance Criteria:**
- [ ] Test passes (<1ms per call)
- [ ] No performance regression

---

### 3.4 Update documentation (1 hour)
**Files:** `CLAUDE.md`, `skills/email-classification.md`

**Changes:**
Update classification system documentation:

**CLAUDE.md (line ~130-170):**
```markdown
### Delete vs Archive Logic

**Exception Keywords (Protected from Auto-Trash):**
- Uses phrase-based matching (not substring)
- Negative keywords filter out marketing language

Protected phrases:
- Financial: receipt, invoice, order confirmation, payment
- Employment: job offer, offer letter, interview invitation
- Medical: doctor, appointment, prescription
- Tax: W-2, 1099, tax return
- Legal: legal notice, court, lawyer
- Security: password reset, security alert

NOT protected (marketing):
- special offer, limited offer, discount, sale
- Triggers exception: "Job offer for Engineer" ✅
- Does NOT trigger: "Special offer on orders" ❌
```

**skills/email-classification.md:**
Add section on exception keywords with examples.

**Acceptance Criteria:**
- [ ] CLAUDE.md updated
- [ ] email-classification.md updated
- [ ] Examples provided

---

## 4.0 Test on production dataset (4 hours)

### 4.1 Deploy to staging branch (1 hour)
**Files:** All modified files

**Commands:**
```bash
git checkout -b feature/safety-rails-restoration
git add .
git commit -m "Restore safety rails with improved logic"
git push -u origin feature/safety-rails-restoration
gh pr create --title "Restore safety rails (short subject + exception keywords)" --body "Testing branch - DO NOT MERGE YET"
```

**Acceptance Criteria:**
- [ ] Branch pushed
- [ ] PR created (marked as draft)
- [ ] Railway preview environment created

---

### 4.2 Clear database and test on 500 emails (2 hours)
**Files:** N/A (production testing)

**Commands:**
```bash
# Clear database
curl -X POST "https://inbox-janitor-staging-preview.up.railway.app/webhooks/run-migration-007"

# Reset usage
curl -X POST "https://inbox-janitor-staging-preview.up.railway.app/webhooks/reset-usage"

# Classify 500 emails
curl -X POST "https://inbox-janitor-staging-preview.up.railway.app/webhooks/sample-and-classify?batch_size=500"

# Wait 3-5 minutes for processing

# Check distribution
curl -X POST "https://inbox-janitor-staging-preview.up.railway.app/webhooks/sample-and-classify?batch_size=0"
```

**Expected Distribution (from PRD):**
- TRASH: ~50%
- REVIEW: ~5%
- KEEP: ~15% (down from 24.9%)
- ARCHIVE: ~30% (up from 22.1%)

**Acceptance Criteria:**
- [ ] 500 emails processed
- [ ] KEEP percentage closer to 15% (was 24.9%)
- [ ] ARCHIVE percentage closer to 30% (was 22.1%)
- [ ] No critical errors

---

### 4.3 Manual quality review (1 hour)
**Files:** Audit page on staging

**Actions:**
1. Visit: `https://inbox-janitor-staging-preview.up.railway.app/audit`
2. Review 50 random TRASH classifications:
   - Any false positives? (important emails trashed)
3. Review 50 random KEEP classifications:
   - Any false negatives? (marketing should be trashed)
4. Review short subject emails specifically:
   - Filter for subjects <5 chars
   - Verify classification accuracy
5. Review "offer" emails specifically:
   - Filter for "offer" in subject
   - Verify job offers protected, marketing not protected

**Deliverable:** Document findings in `/tmp/safety_rails_quality_review.md`:
```markdown
# Safety Rails Quality Review (500 emails)

## Distribution
- TRASH: X% (target: 50%)
- KEEP: X% (target: 15%)
- ARCHIVE: X% (target: 30%)
- REVIEW: X% (target: 5%)

## Manual Review (50 TRASH emails)
- False positives: X (important emails trashed)
- Examples: [list any false positives]

## Manual Review (50 KEEP emails)
- False negatives: X (marketing kept)
- Examples: [list any false negatives]

## Short Subject Analysis
- Total short subjects: X
- Flagged correctly: X
- False positives: X
- False negatives: X

## Exception Keyword "offer" Analysis
- Total with "offer": X
- Job offers protected: X ✅
- Marketing offers not protected: X ✅
- Errors: X

## Overall Quality
- False positive rate: X% (target: <0.1%)
- False negative rate: X% (target: <5%)

## Recommendation
[PASS / NEEDS IMPROVEMENT / FAIL]

If NEEDS IMPROVEMENT, list specific issues:
1. ...
2. ...
```

**Acceptance Criteria:**
- [ ] 100 emails manually reviewed
- [ ] False positive rate <0.1%
- [ ] False negative rate <5%
- [ ] Quality review documented
- [ ] Recommendation: PASS

---

## 5.0 Deploy and monitor (2 hours)

### 5.1 Merge PR and deploy (30 minutes)
**Files:** All modified files

**Commands:**
```bash
# Update PR from draft to ready
gh pr ready

# Wait for CI checks

# Merge after approval
gh pr merge --squash
```

**Acceptance Criteria:**
- [ ] CI checks pass
- [ ] User approves
- [ ] PR merged
- [ ] Railway deployment succeeds

---

### 5.2 Monitor production for 48 hours (1.5 hours initial monitoring)
**Files:** N/A (production monitoring)

**Actions:**
1. **Hour 1:** Monitor logs for errors
   - Check for exceptions in safety rail functions
   - Verify metadata extraction working
   - Watch for classification failures

2. **Hour 24:** Check distribution
   ```bash
   curl -X POST "https://inbox-janitor-production-03fc.up.railway.app/webhooks/sample-and-classify?batch_size=0"
   ```
   - Verify KEEP ~15%, ARCHIVE ~30%

3. **Hour 48:** Review audit log
   - Manual review of 50 random classifications
   - Check for user undo actions (indicates false positives)
   - Verify no critical issues

**Monitoring Dashboard:**
```
# Key Metrics to Watch
- Classification success rate: Should be >99%
- Short subject flag rate: Should be ~5-10% of emails
- Exception keyword trigger rate: Should be ~8-12% of emails
- Undo rate: Should remain <1%
```

**Acceptance Criteria:**
- [ ] No critical errors in 48 hours
- [ ] Distribution improved (KEEP down, ARCHIVE up)
- [ ] Undo rate <1%
- [ ] User reports: 0 complaints

---

## Definition of Done

- [ ] All tasks completed
- [ ] Baseline metrics collected and documented
- [ ] Smart short subject detection implemented and tested
- [ ] Phrase-based exception keywords implemented and tested
- [ ] Tested on 500+ production emails
- [ ] Manual quality review passed (false positive <0.1%)
- [ ] Deployed to production
- [ ] Monitored for 48 hours
- [ ] Distribution improved to targets
- [ ] Documentation updated (CLAUDE.md, skills)
- [ ] CHANGELOG.md updated

---

## Success Metrics

**Before Fix:**
- check_short_subject: Disabled (unknown false positive rate)
- Exception keywords: ~15% false negatives (promo offers protected)
- KEEP percentage: 24.9% (too high)
- ARCHIVE percentage: 22.1% (too low)

**After Fix:**
- check_short_subject: Enabled with <0.1% false positives ✅
- Exception keywords: <5% false negatives ✅
- KEEP percentage: ~15% (target achieved) ✅
- ARCHIVE percentage: ~30% (target achieved) ✅
- User complaints: 0 ✅

---

## Notes

**Why 24 hours?**
- Data collection: 4h (1000 emails, export, analysis)
- Implementation: 14h (short subject 8h, exception keywords 6h)
- Testing: 4h (500 emails, quality review)
- Deploy: 2h (merge, monitor)

**Risk Mitigation:**
- Test on 500 emails before production deploy
- Manual quality review with documented findings
- 48-hour monitoring period
- Can revert if false positive rate >0.1%

**Quality Gates:**
- False positive rate <0.1% (HARD REQUIREMENT)
- False negative rate <5%
- Distribution improves toward targets
- Zero user complaints in 48 hours
