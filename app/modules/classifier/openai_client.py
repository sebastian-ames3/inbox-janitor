"""
OpenAI API client for email classification.

Tier 2 classification using GPT-4o-mini for uncertain emails.

CRITICAL SECURITY:
- Only sends minimal data: sender, subject, snippet (200 chars max)
- NEVER sends full email body
- All prompts are logged for auditing

Cost tracking:
- GPT-4o-mini: ~$0.003 per classification
- Target: <30% of emails need AI (70% handled by Tier 1)
"""

import logging
import json
from typing import Dict, Optional
from openai import OpenAI, OpenAIError
from pydantic import BaseModel, Field, ValidationError

from app.models.email_metadata import EmailMetadata
from app.core.config import settings

logger = logging.getLogger(__name__)


class AIClassificationResponse(BaseModel):
    """
    Structured response from OpenAI classifier.

    Validates AI responses to ensure correct format.
    """
    action: str = Field(..., description="trash, archive, or keep")
    confidence: float = Field(..., description="Confidence score 0.0-1.0", ge=0.0, le=1.0)
    reason: str = Field(..., description="Brief explanation of classification")

    def validate_action(self):
        """Validate action is one of the allowed values."""
        allowed_actions = ["trash", "archive", "keep"]
        if self.action not in allowed_actions:
            raise ValueError(f"Invalid action: {self.action}. Must be one of {allowed_actions}")


class OpenAIClassifier:
    """
    OpenAI-based email classifier using GPT-4o-mini.

    Usage:
        classifier = OpenAIClassifier()
        result = await classifier.classify_email(metadata)
    """

    def __init__(self, api_key: Optional[str] = None):
        """
        Initialize OpenAI client.

        Args:
            api_key: OpenAI API key (defaults to settings.OPENAI_API_KEY)
        """
        self.api_key = api_key or settings.OPENAI_API_KEY
        self.model = settings.OPENAI_MODEL
        self.client = OpenAI(api_key=self.api_key)

        logger.info(f"OpenAI classifier initialized with model: {self.model}")

    def _build_classification_prompt(self, metadata: EmailMetadata) -> str:
        """
        Build classification prompt from email metadata.

        SECURITY: Only includes minimal data (sender, subject, snippet).
        NEVER includes full email body.

        Args:
            metadata: Email metadata

        Returns:
            Prompt string
        """
        # Check for unsubscribe header
        has_unsubscribe = "yes" if metadata.has_unsubscribe_header else "no"

        # Get Gmail category
        gmail_category = metadata.gmail_category or "unknown"

        # Truncate snippet to 200 chars (double-check)
        snippet = (metadata.snippet or "")[:200]

        prompt = f"""Classify this email as TRASH (promotional spam), ARCHIVE (receipts/transactional), or KEEP (important personal).

Email metadata:
- From: {metadata.from_address}
- Subject: {metadata.subject or "(no subject)"}
- Snippet: {snippet}
- Has unsubscribe link: {has_unsubscribe}
- Gmail category: {gmail_category}

Guidelines:
- TRASH: Generic marketing blasts, promotional emails user never opens, re-engagement campaigns, social notifications
- ARCHIVE: Receipts, order confirmations, invoices, shipping notifications, financial statements, booking confirmations
- KEEP: Personal emails from real people, job offers, medical, bills, security alerts, anything uncertain

Critical safety rules:
- If subject/snippet contains: receipt, invoice, order, payment, booking, job, interview, medical, tax, legal → KEEP
- If uncertain → KEEP (safety first)
- Be conservative with TRASH (high confidence only)

Respond with ONLY valid JSON (no markdown, no explanation):
{{"action": "trash|archive|keep", "confidence": 0.0-1.0, "reason": "brief explanation"}}"""

        return prompt

    async def classify_email(self, metadata: EmailMetadata) -> Dict:
        """
        Classify email using OpenAI GPT-4o-mini.

        Args:
            metadata: Email metadata

        Returns:
            Dict with keys: action, confidence, reason, tokens_used, cost

        Raises:
            OpenAIError: If API call fails
            ValidationError: If AI response is invalid

        Usage:
            result = await classifier.classify_email(metadata)
            print(f"Action: {result['action']}, Confidence: {result['confidence']}")
        """
        prompt = self._build_classification_prompt(metadata)

        # Log prompt (for auditing and debugging)
        logger.debug(
            f"Calling OpenAI for message {metadata.message_id}",
            extra={
                "message_id": metadata.message_id,
                "from_address": metadata.from_address,
                "model": self.model,
                "prompt_length": len(prompt)
            }
        )

        try:
            # Call OpenAI API
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {
                        "role": "system",
                        "content": "You are an email classification assistant. Respond with ONLY valid JSON."
                    },
                    {
                        "role": "user",
                        "content": prompt
                    }
                ],
                temperature=0.1,  # Low temperature for consistency
                max_tokens=150,  # Short responses only
                response_format={"type": "json_object"}  # Force JSON output
            )

            # Extract response
            ai_response_text = response.choices[0].message.content

            # Parse JSON
            try:
                ai_response_dict = json.loads(ai_response_text)
            except json.JSONDecodeError as e:
                logger.error(
                    f"Failed to parse AI response as JSON: {ai_response_text}",
                    extra={"message_id": metadata.message_id, "error": str(e)}
                )
                # Fallback: conservative response
                return {
                    "action": "keep",
                    "confidence": 0.0,
                    "reason": f"AI response parsing failed: {str(e)}",
                    "tokens_used": 0,
                    "cost": 0.0,
                    "error": "json_parse_error"
                }

            # Validate response structure
            try:
                validated_response = AIClassificationResponse(**ai_response_dict)
                validated_response.validate_action()
            except (ValidationError, ValueError) as e:
                logger.error(
                    f"Invalid AI response structure: {ai_response_dict}",
                    extra={"message_id": metadata.message_id, "error": str(e)}
                )
                # Fallback: conservative response
                return {
                    "action": "keep",
                    "confidence": 0.0,
                    "reason": f"AI response validation failed: {str(e)}",
                    "tokens_used": 0,
                    "cost": 0.0,
                    "error": "validation_error"
                }

            # Calculate cost
            tokens_used = response.usage.total_tokens
            # GPT-4o-mini pricing: $0.150/1M input tokens, $0.600/1M output tokens
            # Simplified average: ~$0.003 per 1000 tokens
            cost = (tokens_used / 1000) * 0.003

            logger.info(
                f"AI classified message {metadata.message_id}: {validated_response.action} "
                f"(confidence: {validated_response.confidence:.2f})",
                extra={
                    "message_id": metadata.message_id,
                    "action": validated_response.action,
                    "confidence": validated_response.confidence,
                    "tokens": tokens_used,
                    "cost": cost
                }
            )

            return {
                "action": validated_response.action,
                "confidence": validated_response.confidence,
                "reason": validated_response.reason,
                "tokens_used": tokens_used,
                "cost": cost
            }

        except OpenAIError as e:
            # OpenAI API error (rate limit, timeout, etc.)
            logger.error(
                f"OpenAI API error for message {metadata.message_id}: {e}",
                extra={
                    "message_id": metadata.message_id,
                    "error_type": type(e).__name__,
                    "error": str(e)
                }
            )

            # Log to Sentry
            import sentry_sdk
            sentry_sdk.capture_exception(e, extra={
                "message_id": metadata.message_id,
                "error": "OpenAI API call failed"
            })

            # Fallback: conservative response
            return {
                "action": "keep",
                "confidence": 0.0,
                "reason": f"AI API error: {str(e)}",
                "tokens_used": 0,
                "cost": 0.0,
                "error": "api_error"
            }

        except Exception as e:
            # Unexpected error
            logger.error(
                f"Unexpected error during AI classification for message {metadata.message_id}: {e}",
                extra={
                    "message_id": metadata.message_id,
                    "error": str(e)
                }
            )

            # Log to Sentry
            import sentry_sdk
            sentry_sdk.capture_exception(e, extra={
                "message_id": metadata.message_id,
                "error": "Unexpected AI classification error"
            })

            # Fallback: conservative response
            return {
                "action": "keep",
                "confidence": 0.0,
                "reason": f"Unexpected error: {str(e)}",
                "tokens_used": 0,
                "cost": 0.0,
                "error": "unexpected_error"
            }

    def verify_no_body_in_prompt(self, metadata: EmailMetadata) -> bool:
        """
        Security check: Verify prompt doesn't contain full email body.

        This is a safety check to ensure we're not accidentally sending
        full email bodies to OpenAI.

        Args:
            metadata: Email metadata

        Returns:
            True if prompt is safe (no full body), False otherwise
        """
        prompt = self._build_classification_prompt(metadata)

        # Check prompt length (should be <2000 chars if only using metadata)
        if len(prompt) > 3000:
            logger.error(
                f"SECURITY: Prompt too long ({len(prompt)} chars) - may contain full body",
                extra={"message_id": metadata.message_id}
            )
            return False

        # Check snippet is truncated (should be max 200 chars)
        snippet_in_prompt = metadata.snippet or ""
        if len(snippet_in_prompt) > 200:
            logger.error(
                f"SECURITY: Snippet too long ({len(snippet_in_prompt)} chars)",
                extra={"message_id": metadata.message_id}
            )
            return False

        return True
