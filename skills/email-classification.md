# Email Classification Skill

## Purpose
Implement Inbox Janitor's 3-tier email classification system with proper safety rails and decision logic.

## Overview

Inbox Janitor uses a **three-tier classification system** that balances accuracy, cost, and speed:

1. **Tier 1**: Metadata Signals (80% accuracy, free, instant)
2. **Tier 2**: AI Classification (95% accuracy, $0.003/call)
3. **Tier 3**: User Rules (100% accuracy, user-controlled)

## Classification Flow

```
Email Arrives
    ↓
Check User Rules (Tier 3) → Match? → Apply Rule
    ↓ No
Check Metadata Signals (Tier 1) → Confidence ≥90%? → Apply Action
    ↓ No
Call AI Classifier (Tier 2) → Get Action + Confidence
    ↓
Apply Safety Rails → Final Action
```

## Action Types

### 1. KEEP (Important)
Email stays in inbox, requires attention

**Criteria:**
- Personal emails from real people
- Starred by user
- From known contacts (in address book)
- Critical keywords detected
- Recent (<3 days) + uncertainty
- Any email with confidence <0.55

**Keywords that force KEEP:**
```python
CRITICAL_KEYWORDS = [
    'interview', 'job', 'offer', 'application',
    'medical', 'doctor', 'appointment', 'health',
    'bank', 'account', 'fraud', 'security',
    'tax', 'irs', 'w-2', '1099',
    'legal', 'court', 'lawyer', 'lawsuit'
]
```

### 2. ARCHIVE (Future Value)
Email has value but doesn't need inbox attention

**Criteria:**
- Receipts, order confirmations, invoices
- Financial statements, bank notices
- Shipping notifications, tracking updates
- Booking confirmations, reservations
- Newsletters from subscribed sources
- Service notifications (password resets, security alerts)
- Emails from contacts (not starred)

**Keywords that suggest ARCHIVE:**
```python
ARCHIVE_KEYWORDS = [
    'receipt', 'invoice', 'order', 'payment',
    'booking', 'reservation', 'ticket', 'confirmation',
    'shipped', 'tracking', 'delivery',
    'statement', 'bill', 'due date'
]
```

### 3. TRASH (Delete-worthy)
Promotional spam with no future value

**Criteria:**
- Generic marketing blasts ("50% off everything!")
- Social media notifications ("You appeared in searches")
- Re-engagement campaigns ("We miss you!")
- Promotional category + List-Unsubscribe header + confidence >0.85
- Sender open rate <5% (user never reads them)
- Marketing platform domains (sendgrid.net, mailchimp, etc.)

**Strong trash signals:**
```python
TRASH_SIGNALS = [
    'category:promotions' + 'has_unsubscribe',
    'subject_contains: % off, limited time, sale, deal',
    'sender_open_rate < 0.05',
    'from_marketing_platform',
    'bulk_mail_headers'
]
```

### 4. REVIEW (Uncertain)
Borderline cases that need user judgment

**Criteria:**
- Confidence between 0.55 and 0.85
- Conflicting signals (promotional but has receipt keyword)
- Unknown sender with unclear intent
- AI unsure of classification

## Tier 1: Metadata Signals

### Gmail Category (Strong Signal)

```python
CATEGORY_WEIGHTS = {
    'CATEGORY_PROMOTIONS': 0.90,  # 90% likely trash
    'CATEGORY_SOCIAL': 0.80,       # 80% likely trash
    'CATEGORY_UPDATES': 0.70,      # 70% likely archive
    'CATEGORY_FORUMS': 0.60,       # 60% likely archive
    'CATEGORY_PRIMARY': -1.0       # Never auto-trash
}
```

### Email Headers (Strong Signal)

```python
def check_marketing_headers(headers):
    """Check for bulk/marketing headers."""
    
    # List-Unsubscribe = 99% marketing by law
    if 'List-Unsubscribe' in headers:
        return 0.90
    
    # Bulk mail indicators
    if headers.get('Precedence') == 'bulk':
        return 0.85
    
    if headers.get('Auto-Submitted'):
        return 0.85
    
    return 0.0
```

### Sender Domain (Moderate Signal)

```python
MARKETING_PLATFORMS = [
    'sendgrid.net', 'mailchimp.com', 'constantcontact.com',
    'mailgun.net', 'postmarkapp.com', 'amazonses.com'
]

def is_marketing_platform(from_address):
    """Check if sent via marketing platform."""
    domain = from_address.split('@')[1]
    return any(platform in domain for platform in MARKETING_PLATFORMS)
```

## Tier 2: AI Classification

### When to Call AI

Only call GPT-4o-mini if:
- Tier 1 confidence <90%
- No user rule matches
- Not a starred email
- Not from a contact

### AI Prompt Structure

```python
def build_classification_prompt(email_metadata):
    """Build AI classification prompt."""
    
    prompt = f"""You are an email classifier. Analyze this email and decide the best action.

Email Details:
- From: {email_metadata.from_address}
- Subject: {email_metadata.subject}
- Preview: {email_metadata.snippet}
- Days old: {email_metadata.date_days_ago}

Classification Rules:
1. **keep** = Personal emails, important finance/travel/health, actionable items
2. **archive** = Newsletters, receipts (>30 days), service notifications
3. **trash** = Generic marketing, re-engagement campaigns, social notifications
4. **review** = Uncertain, conflicting signals

Bias: Prefer "archive" over "keep" unless truly needs attention.
Bias: Use "review" if uncertain - it's safer.

Respond in JSON:
{{"action": "keep|archive|trash|review", "reason": "brief explanation", "confidence": 0.0-1.0}}"""
    
    return prompt
```

## Safety Rails (CRITICAL)

### Pre-Classification Checks

```python
def apply_safety_checks(email):
    """Run safety checks before any action."""
    
    # 1. Starred emails NEVER touched
    if email.is_starred:
        return 'keep', 1.0, "Email is starred"
    
    # 2. Known contacts always kept (unless user rule)
    if email.is_contact and not in_blocked_list(email.from_address):
        return 'archive', 0.95, "From known contact"
    
    # 3. Recent + important keywords → keep
    if email.date_days_ago <= 30:
        if has_exception_keywords(email.subject):
            return 'keep', 0.90, "Recent with critical keyword"
    
    return None, 0.0, None  # No safety override
```

### Exception Keywords (NEVER Trash)

These keywords override ALL other signals:

```python
EXCEPTION_KEYWORDS = {
    'financial': ['receipt', 'invoice', 'order', 'payment', 'bank', 'tax'],
    'travel': ['booking', 'reservation', 'ticket', 'flight', 'hotel'],
    'shipping': ['shipped', 'tracking', 'delivery', 'package'],
    'security': ['password', 'security', 'verify', 'confirm', 'authenticate'],
    'employment': ['interview', 'job', 'offer', 'application', 'resume'],
    'medical': ['medical', 'doctor', 'appointment', 'health', 'prescription'],
    'legal': ['legal', 'court', 'lawyer', 'lawsuit', 'contract']
}

def has_exception_keywords(text):
    """Check if text contains exception keywords."""
    text_lower = text.lower()
    return any(
        keyword in text_lower 
        for category in EXCEPTION_KEYWORDS.values() 
        for keyword in category
    )
```

## Confidence Thresholds

User-configurable thresholds:

```python
class ConfidenceThresholds:
    """Classification confidence thresholds."""
    
    # Auto-act threshold (default 0.85)
    AUTO_THRESHOLD = 0.85
    
    # Review threshold (default 0.55)
    REVIEW_THRESHOLD = 0.55

def apply_confidence_logic(action, confidence, thresholds):
    """Apply confidence-based decision logic."""
    
    # High confidence → auto-act
    if confidence >= thresholds.AUTO_THRESHOLD:
        return action
    
    # Medium confidence → review
    elif confidence >= thresholds.REVIEW_THRESHOLD:
        return 'review'
    
    # Low confidence → keep (safest)
    else:
        return 'keep'
```

## Testing Classification Logic

### Unit Tests Required

```python
# Test exception keywords
def test_exception_keywords_override():
    """Critical keywords should override classification."""
    email = EmailMetadata(
        subject="Job Interview Tomorrow",
        gmail_category="CATEGORY_PROMOTIONS",
        has_unsubscribe=True
    )
    assert classify_email(email).action == 'keep'

# Test starred emails
def test_starred_emails_never_trashed():
    """Starred emails must never be trashed."""
    email = EmailMetadata(
        is_starred=True,
        gmail_category="CATEGORY_PROMOTIONS"
    )
    assert classify_email(email).action == 'keep'
```

## Common Classification Scenarios

### Scenario 1: Newsletter Subscription
```
Input: Subject="Weekly Newsletter", Category=PROMOTIONS, Has Unsubscribe
Tier 1: 0.90 (category + unsubscribe)
Action: archive (high confidence, has value)
```

### Scenario 2: Amazon Receipt
```
Input: Subject="Your Amazon order has shipped", Has "receipt" keyword
Safety Check: Exception keyword detected
Action: keep (regardless of category)
```

### Scenario 3: Marketing Email from Contact
```
Input: From contact, Category=PROMOTIONS, Has Unsubscribe
Safety Check: Is contact = archive (not keep, not trash)
Action: archive (0.95 confidence)
```

### Scenario 4: Job Offer Email
```
Input: Subject="Job Offer - Congratulations", Category=PROMOTIONS
Safety Check: Exception keyword "job" + "offer"
Action: keep (safety rail override)
```

## Testing Requirements

Classification logic must be thoroughly tested (see **testing-requirements.md**):

**Required tests:**
- `test_exception_keywords_override()` - Critical keywords force KEEP
- `test_starred_emails_never_trashed()` - Starred always kept
- `test_job_offer_safety()` - Job-related emails protected
- `test_medical_email_safety()` - Medical emails protected
- `test_confidence_thresholds()` - Thresholds applied correctly
- `test_user_rules_override()` - User rules take precedence

**Test with real data:**
- 1000+ emails before launch (see **testing-requirements.md** Manual Testing section)
- Mom/sister Gmail accounts (closed beta)
- Monitor undo rate (<1% target)

## References

- **security-first.md** - Never store email bodies, only snippets
- **testing-requirements.md** - Classification tests to write
- **fastapi-module-builder.md** - Module structure for classifier
- **ai-dev-workflow.md** - Use for building classification feature

**Code references:**
- Database models: `/app/models/email_action.py`
- Classification service: `/app/modules/classifier/service.py`
- AI prompt: `/API/main.py` (current implementation)
