
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from typing import Literal
import os
from openai import OpenAI
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

app = FastAPI(title="Inbox Janitor Classifier")

# Initialize OpenAI client
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

# Define request/response models
class EmailMetadata(BaseModel):
    from_address: str
    subject: str
    snippet: str
    is_starred: bool
    is_contact: bool
    date_days_ago: int

class ClassificationResult(BaseModel):
    action: Literal["keep", "archive", "trash", "review"]
    reason: str
    confidence: float

# Safety pre-rules (fast path - no AI needed)
def apply_pre_rules(email: EmailMetadata) -> ClassificationResult | None:
    """Check safety rules before calling AI. Returns result if matched, None otherwise."""
    
    # Rule 1: Starred emails always kept
    if email.is_starred:
        return ClassificationResult(
            action="keep",
            reason="Email is starred by user",
            confidence=1.0
        )
    
    # Rule 2: Contact emails (not starred) archived
    if email.is_contact and not email.is_starred:
        return ClassificationResult(
            action="archive",
            reason="From known contact, not starred",
            confidence=0.95
        )
    
    # Rule 3: Recent important keywords → keep
    important_keywords = ["receipt", "invoice", "booking", "itinerary", 
                         "order", "bank", "tax", "confirmation"]
    subject_lower = email.subject.lower()
    
    if email.date_days_ago <= 30:
        if any(keyword in subject_lower for keyword in important_keywords):
            return ClassificationResult(
                action="keep",
                reason=f"Recent email with important keyword in subject",
                confidence=0.9
            )
    
    return None  # No pre-rule matched, proceed to AI

def classify_with_ai(email: EmailMetadata) -> ClassificationResult:
    """Use OpenAI to classify email when pre-rules don't match."""
    
    prompt = f"""You are an email classifier. Analyze this email and decide the best action.

Email Details:
- From: {email.from_address}
- Subject: {email.subject}
- Preview: {email.snippet}
- Days old: {email.date_days_ago}

Classification Rules:
1. **keep** = Personal emails, important finance/travel/health, actionable items, anything needing attention
2. **archive** = Newsletters, promotions, old receipts (>30 days), social media notifications, updates
3. **trash** = Spam, obvious ads, irrelevant marketing, duplicate notifications
4. **review** = Ambiguous cases where you're uncertain

Content Guidelines:
- Promotions/ads/marketing → usually archive or trash
- Personal conversations → keep
- Finance/travel/booking (recent) → keep
- Social media notifications → archive or trash
- Newsletters → archive (unless explicitly valuable)
- Old receipts/confirmations (>30 days) → archive

Bias: Prefer "archive" over "keep" unless it truly needs attention.
Bias: Use "review" if you're uncertain - it's safer.

Respond in JSON format:
{{"action": "keep|archive|trash|review", "reason": "brief explanation", "confidence": 0.0-1.0}}"""

    try:
        response = client.chat.completions.create(
            model="gpt-4o-mini",  # Fast and cheap model
            messages=[
                {"role": "system", "content": "You are a helpful email classification assistant. Always respond with valid JSON."},
                {"role": "user", "content": prompt}
            ],
            temperature=0.3,  # Low temperature for consistent decisions
            response_format={"type": "json_object"}
        )
        
        import json
        result = json.loads(response.choices[0].message.content)
        
        return ClassificationResult(
            action=result["action"],
            reason=result["reason"],
            confidence=result.get("confidence", 0.7)
        )
    
    except Exception as e:
        # If AI fails, default to review (safest option)
        return ClassificationResult(
            action="review",
            reason=f"AI classification failed: {str(e)}",
            confidence=0.0
        )

@app.get("/health")
async def health_check():
    """Check if API is running."""
    return {"ok": True, "service": "inbox-janitor-classifier"}

@app.post("/classify", response_model=ClassificationResult)
async def classify_email(email: EmailMetadata):
    """
    Classify an email and return the recommended action.
    
    First checks pre-rules (starred, contacts, important keywords).
    If no pre-rule matches, uses OpenAI for classification.
    """
    
    # Step 1: Check pre-rules first (fast and free)
    pre_rule_result = apply_pre_rules(email)
    if pre_rule_result:
        return pre_rule_result
    
    # Step 2: Use AI for classification
    ai_result = classify_with_ai(email)
    return ai_result

@app.get("/")
async def root():
    """Welcome message."""
    return {
        "service": "Inbox Janitor Classifier API",
        "version": "1.0.0",
        "endpoints": {
            "health": "/health",
            "classify": "POST /classify"
        }
    }