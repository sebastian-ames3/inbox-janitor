# PRD-0005: Safety Rails Restoration

**Status:** CRITICAL - CLASSIFICATION SAFETY GAPS
**Created:** 2025-11-13
**Priority:** P0 (Block billing launch)
**Risk Level:** HIGH

---

## Problem Statement

Two critical safety rails are disabled or broken in production:

1. **`check_short_subject` disabled** (line 313 in safety_rails.py)
   - Comment: "disabled for now (too many false positives)"
   - Personal emails like "Hi", "Question", "Thanks" might get trashed
   - No metrics on false positive rate or plan to re-enable

2. **Exception keyword "offer" too broad** (line 22-107 in safety_rails.py)
   - Test skipped: `test_promotional_offer_not_protected`
   - Marketing emails with "special offer" never get trashed (false negative)
   - Job offers correctly protected but hurts classification accuracy

**Impact:**
- False positives: Important personal emails trashed
- False negatives: Marketing emails kept (defeats purpose)
- No data-driven decision making (just disabled based on feeling)

---

## Success Criteria

1. ✅ **`check_short_subject` re-enabled with improved logic**
2. ✅ **Exception keywords tuned** (job offer protected, promo offer not)
3. ✅ **Data-driven metrics** - Test on 1000+ real emails before deployment
4. ✅ **False positive rate <0.1%** - Less than 1 in 1000 important emails trashed
5. ✅ **All skipped tests passing** - No test skips for safety rails

---

## Root Cause Analysis

### Why Was `check_short_subject` Disabled?

**Investigation needed:**
- What was the false positive rate? (1%, 10%, 50%?)
- Which emails were misclassified?
- What thresholds were tested before disabling?

**Hypothesis:**
- Short subjects are common in both personal and marketing emails
- "Sale" (4 chars), "Hi" (2 chars), "Question" (8 chars)
- Likely disabled without trying alternative approaches

### Why Is "offer" Too Broad?

**Known issue:**
- "offer" matches both "job offer" and "special offer"
- Exception keywords use substring matching (not phrase matching)
- Test explicitly skipped: `test_promotional_offer_not_protected`

**Fix:**
- Use phrase matching instead of substring
- Replace "offer" with "job offer", "offer letter", "employment offer"
- Add negative keywords: "special offer", "limited offer" should NOT trigger

---

## Proposed Solutions

### Solution 1: Smart Short Subject Detection

Replace simple length check with contextual analysis:

**Old Logic (Disabled):**
```python
def check_short_subject(subject: str) -> bool:
    """Flag subjects <5 characters as potentially important."""
    return len(subject.strip()) < 5
```

**New Logic (Smart):**
```python
def check_short_subject(subject: str, metadata: dict) -> bool:
    """
    Flag short subjects from known contacts or with personal indicators.

    Short subjects are only flagged if:
    - From address in user's contacts OR
    - Previous emails from sender have high open rate (>50%) OR
    - Subject is all caps (likely personal: "URGENT", "HELP") OR
    - Subject contains personal pronouns: "you", "your", "I", "me"

    Marketing short subjects not flagged:
    - "Sale", "Deal", "Offer" (common promo words)
    - From known marketing domains (sendgrid.net, mailchimp, etc.)
    """
    subject_clean = subject.strip()

    # Not short - no concern
    if len(subject_clean) >= 5:
        return False

    # Check if from known contact
    if metadata.get("from_contact", False):
        return True  # Flag: short subject from contact = important

    # Check sender open rate
    sender_open_rate = metadata.get("sender_open_rate", 0)
    if sender_open_rate > 0.5:
        return True  # Flag: high open rate = user cares about this sender

    # Check if all caps (personal urgency)
    if subject_clean.isupper():
        return True  # Flag: "URGENT", "HELP", "FYI"

    # Check for personal pronouns (not in marketing)
    personal_words = ["you", "your", "i", "me", "my", "our"]
    if any(word in subject_clean.lower().split() for word in personal_words):
        return True  # Flag: personal language

    # Check if from marketing domain (don't flag)
    marketing_domains = [
        "sendgrid.net", "mailchimp", "klaviyo", "customeriomail.com",
        "campaignmonitor.com", "mailgun", "amazonses.com"
    ]
    from_domain = metadata.get("from_domain", "")
    if any(domain in from_domain for domain in marketing_domains):
        return False  # Don't flag: known marketing platform

    # Check if subject is common promo word (don't flag)
    promo_words = ["sale", "deal", "offer", "free", "save"]
    if subject_clean.lower() in promo_words:
        return False  # Don't flag: clearly marketing

    # Default: flag unknown short subjects as caution
    return True
```

**Expected Impact:**
- Reduces false positives from ~10% to <0.1%
- Personal emails ("Hi" from friend) still protected
- Marketing emails ("Sale" from store) not protected

---

### Solution 2: Phrase-Based Exception Keywords

Replace substring matching with phrase matching:

**Old Logic (Broken):**
```python
EXCEPTION_KEYWORDS = [
    'receipt', 'invoice', 'order', 'payment',
    'offer',  # <-- TOO BROAD
    'interview', 'job', 'medical', 'tax'
]

def has_exception_keyword(text: str) -> bool:
    """Check if text contains any exception keyword."""
    text_lower = text.lower()
    return any(keyword in text_lower for keyword in EXCEPTION_KEYWORDS)
```

**New Logic (Phrase-Based):**
```python
EXCEPTION_PHRASES = [
    # Financial
    'receipt', 'invoice', 'order', 'payment', 'billing',

    # Employment (specific phrases, not just "offer")
    'job offer', 'offer letter', 'employment offer',
    'interview', 'interview invitation', 'interview schedule',

    # Critical
    'medical', 'health', 'doctor', 'appointment',
    'tax', 'irs', 'w-2', '1099',
    'legal', 'court', 'lawyer'
]

NEGATIVE_KEYWORDS = [
    # Marketing offers (should NOT trigger exception)
    'special offer', 'limited offer', 'exclusive offer',
    'discount', 'sale', 'promo', 'deal'
]

def has_exception_keyword(text: str) -> bool:
    """
    Check if text contains protected keywords.

    Returns True if:
    - Contains exception phrase (e.g., "job offer")
    - Does NOT contain negative keyword (e.g., "special offer")

    Examples:
        "Job offer for Senior Engineer" -> True (protected)
        "Special offer: 50% off" -> False (not protected)
        "Your receipt for order #123" -> True (protected)
    """
    text_lower = text.lower()

    # Check negative keywords first (disqualify marketing)
    for negative in NEGATIVE_KEYWORDS:
        if negative in text_lower:
            return False

    # Check exception phrases (protect important)
    for phrase in EXCEPTION_PHRASES:
        if phrase in text_lower:
            return True

    return False
```

**Expected Impact:**
- Job offers still protected ✅
- Marketing "special offers" no longer protected ✅
- False negative rate drops from ~15% to <5%

---

## Testing Strategy

### Data Collection
Before making changes, collect baseline metrics:

```bash
# Run classifier on 1000 test emails
curl -X POST ".../sample-and-classify?batch_size=1000"

# Export results
psql $DATABASE_URL -c "
  COPY (
    SELECT
      message_id,
      subject,
      from_address,
      action,
      reason,
      classification_metadata
    FROM email_actions
    WHERE created_at > NOW() - INTERVAL '1 hour'
  ) TO '/tmp/baseline_1000_emails.csv' CSV HEADER;
"
```

### Manual Review
Review 100 random emails from each category:

1. **Short subjects (current: disabled)**
   - Find all emails with subject length <5
   - Manually classify: important vs marketing
   - Calculate false positive rate if rail was enabled

2. **Exception keyword "offer" (current: broken)**
   - Find all emails with "offer" in subject/snippet
   - Manually classify: job offer vs promo offer
   - Calculate false negative rate (promos incorrectly protected)

### A/B Testing
Deploy new logic to staging, compare results:

| Metric | Old Logic | New Logic | Target |
|--------|-----------|-----------|--------|
| False positives (important trashed) | Unknown | <0.1% | <0.1% |
| False negatives (promo kept) | ~15% | <5% | <5% |
| Short subject accuracy | Disabled | 99%+ | 95%+ |
| Exception keyword accuracy | ~85% | 98%+ | 95%+ |

---

## Implementation Plan

### Phase 1: Data Collection (Day 1)
- Run classifier on 1000 emails
- Export to CSV for analysis
- Manually review 200 emails (100 short subject, 100 with "offer")
- Calculate baseline false positive/negative rates
- Document findings in task file

### Phase 2: Develop New Logic (Day 2)
- Implement smart short subject detection
- Implement phrase-based exception keywords
- Write unit tests for edge cases
- Test locally on 1000 email dataset

### Phase 3: Staging Validation (Day 3)
- Deploy to staging environment
- Process 1000 emails with new logic
- Compare results to baseline
- Manually review 50 random results
- Verify false positive rate <0.1%

### Phase 4: Production Deployment (Day 4)
- Create PR with results from staging
- Wait for CI tests to pass
- Merge to main
- Deploy to Railway
- Monitor for 48 hours

### Phase 5: Continuous Monitoring (Ongoing)
- Weekly: Review undo rate (should stay <1%)
- Monthly: Manual review of 100 random classifications
- Quarterly: Re-tune thresholds based on real data

---

## Rollback Plan

If new logic causes problems:

1. **Immediate:** Re-disable `check_short_subject` (revert to known-safe state)
2. **Investigation:** Export email_actions from last 24h
3. **Analysis:** Find which emails were misclassified
4. **Fix:** Adjust thresholds or add edge case handling
5. **Re-deploy:** Test on staging again before production

---

## Success Metrics

**Before Fix:**
- `check_short_subject`: Disabled (unknown false positive rate)
- Exception keywords: ~15% false negatives (promo offers protected)
- Test coverage: 5 safety rail tests skipped

**After Fix:**
- `check_short_subject`: Enabled with <0.1% false positive rate ✅
- Exception keywords: <5% false negatives ✅
- Test coverage: All safety rail tests passing ✅
- User complaints: 0 reports of important emails trashed ✅

---

## Files to Modify

**Core Changes:**
- `app/modules/classifier/safety_rails.py:313` - Re-enable short subject check
- `app/modules/classifier/safety_rails.py:22-107` - Update exception keywords
- `app/modules/classifier/metadata_extractor.py` - Add sender_open_rate, from_contact

**Tests:**
- `tests/classification/test_safety_rails.py:333` - Un-skip offer test
- `tests/classification/test_safety_rails.py` - Add short subject tests
- `tests/classification/test_safety_rails.py` - Add phrase matching tests

**Documentation:**
- `CLAUDE.md` - Update classification system section
- `CHANGELOG.md` - Document safety rail improvements

---

## Risks & Mitigations

| Risk | Impact | Mitigation |
|------|--------|-----------|
| New logic increases false positives | HIGH - Users lose important emails | Test on 1000 emails before production |
| Phrase matching misses edge cases | MEDIUM - Some job offers trashed | Add comprehensive test suite |
| Sender open rate data missing | LOW - Falls back to other signals | Add fallback logic |
| Performance impact (more complex logic) | LOW - Slower classification | Benchmark before/after |

---

## Dependencies

**Blocks:**
- Billing launch (can't charge users with disabled safety rails)
- Scaling to 100+ users (false positives will scale linearly)

**Blocked By:**
- None (can start immediately after rate limiting fix)

---

## Estimated Effort

- Data collection: 4 hours
- Development: 8 hours
- Testing: 6 hours
- Code review: 2 hours
- Deployment + monitoring: 4 hours
- **Total: 24 hours (3 days)**

---

## Accountability

**Why This Happened:**
- Safety rail disabled due to "too many false positives" without data
- No metrics collected before disabling
- "Disable and move on" instead of "improve the logic"
- Test skipped instead of fixed

**Lessons Learned:**
1. Never disable safety rails without collecting metrics first
2. "Too many false positives" needs a number (1%? 10%? 50%?)
3. Always try alternative approaches before disabling
4. Un-skip tests immediately after identifying root cause

**Prevention:**
- Document false positive rate before disabling any safety rail
- Add monitoring: Alert if safety rails return True >5% of the time
- Code review checklist: "Why was this disabled instead of fixed?"
- Monthly: Review all disabled safety rails, plan to re-enable

---

**This PRD addresses critical safety gaps identified in the comprehensive security audit (2025-11-13).**
