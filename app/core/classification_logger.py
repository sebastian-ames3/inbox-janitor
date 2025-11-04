"""
Classification logging for learning and improvement.

Logs all classification decisions to structured JSON files for:
- Analysis and metrics
- Model improvement
- Debugging false positives/negatives
- A/B testing different thresholds
"""

import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Optional

from app.models.email_metadata import EmailMetadata
from app.models.classification import ClassificationResult

# Classification log file
CLASSIFICATION_LOG_DIR = Path("logs")
CLASSIFICATION_LOG_FILE = CLASSIFICATION_LOG_DIR / "classifications.jsonl"


def ensure_log_directory():
    """Ensure logs directory exists."""
    CLASSIFICATION_LOG_DIR.mkdir(exist_ok=True)


def log_classification(
    metadata: EmailMetadata,
    result: ClassificationResult,
    mailbox_id: str,
    processing_time_ms: Optional[float] = None
):
    """
    Log classification result to JSON file for learning.

    Creates one JSON object per line (JSONL format) for easy parsing.

    Args:
        metadata: Email metadata
        result: Classification result
        mailbox_id: Mailbox UUID
        processing_time_ms: Time taken to classify (milliseconds)

    File format (one JSON object per line):
    {
        "timestamp": "2025-11-04T12:34:56Z",
        "mailbox_id": "uuid",
        "message_id": "gmail-message-id",
        "from_address": "sender@example.com",
        "from_domain": "example.com",
        "subject": "Email subject",
        "gmail_category": "promotional",
        "action": "trash",
        "confidence": 0.95,
        "overridden": false,
        "signals": [
            {"name": "gmail_category", "score": 0.60, "reason": "..."},
            {"name": "list_unsubscribe", "score": 0.40, "reason": "..."}
        ],
        "reason": "Promotional email...",
        "processing_time_ms": 15.3
    }

    Usage:
        log_classification(metadata, result, mailbox_id, processing_time_ms)
    """
    ensure_log_directory()

    # Build log entry
    log_entry = {
        "timestamp": datetime.utcnow().isoformat() + "Z",
        "mailbox_id": mailbox_id,
        "message_id": metadata.message_id,
        "from_address": metadata.from_address,
        "from_domain": metadata.from_domain,
        "subject": metadata.subject,
        "gmail_category": metadata.gmail_category,
        "gmail_labels": metadata.gmail_labels,
        "has_unsubscribe": metadata.has_unsubscribe_header,
        "is_starred": metadata.is_starred,
        "is_important": metadata.is_important,
        "action": result.action.value,
        "confidence": result.confidence,
        "overridden": result.overridden,
        "override_reason": result.override_reason,
        "signals": [
            {
                "name": s.name,
                "score": s.score,
                "reason": s.reason
            }
            for s in result.signals
        ],
        "total_signal_score": result.total_signal_score,
        "reason": result.reason,
        "processing_time_ms": processing_time_ms,
    }

    # Write to file (append mode)
    try:
        with open(CLASSIFICATION_LOG_FILE, "a") as f:
            f.write(json.dumps(log_entry) + "\n")
    except Exception as e:
        # Don't fail classification if logging fails
        logging.getLogger(__name__).error(f"Failed to log classification: {e}")


def get_classification_stats(days: int = 7) -> dict:
    """
    Get classification statistics from log file.

    Args:
        days: Number of days to analyze (default 7)

    Returns:
        Dict with statistics:
        - total: Total classifications
        - by_action: Count by action type
        - avg_confidence: Average confidence by action
        - override_rate: Percentage overridden
        - avg_processing_time: Average processing time

    Usage:
        stats = get_classification_stats(days=7)
        print(f"Override rate: {stats['override_rate']:.1%}")
    """
    from datetime import timedelta
    from collections import defaultdict

    if not CLASSIFICATION_LOG_FILE.exists():
        return {
            "total": 0,
            "by_action": {},
            "avg_confidence": {},
            "override_rate": 0.0,
            "avg_processing_time": 0.0
        }

    cutoff = datetime.utcnow() - timedelta(days=days)

    total = 0
    by_action = defaultdict(int)
    confidence_by_action = defaultdict(list)
    overridden_count = 0
    processing_times = []

    try:
        with open(CLASSIFICATION_LOG_FILE, "r") as f:
            for line in f:
                try:
                    entry = json.loads(line)

                    # Check if within time window
                    timestamp = datetime.fromisoformat(entry["timestamp"].replace("Z", "+00:00"))
                    if timestamp < cutoff:
                        continue

                    total += 1
                    action = entry["action"]
                    by_action[action] += 1
                    confidence_by_action[action].append(entry["confidence"])

                    if entry.get("overridden"):
                        overridden_count += 1

                    if entry.get("processing_time_ms"):
                        processing_times.append(entry["processing_time_ms"])

                except (json.JSONDecodeError, KeyError):
                    continue

    except Exception as e:
        logging.getLogger(__name__).error(f"Failed to read classification stats: {e}")
        return {
            "total": 0,
            "by_action": {},
            "avg_confidence": {},
            "override_rate": 0.0,
            "avg_processing_time": 0.0
        }

    # Calculate averages
    avg_confidence = {}
    for action, confidences in confidence_by_action.items():
        avg_confidence[action] = sum(confidences) / len(confidences) if confidences else 0.0

    override_rate = overridden_count / total if total > 0 else 0.0
    avg_processing_time = sum(processing_times) / len(processing_times) if processing_times else 0.0

    return {
        "total": total,
        "by_action": dict(by_action),
        "avg_confidence": avg_confidence,
        "override_rate": override_rate,
        "avg_processing_time": avg_processing_time
    }


def rotate_classification_logs(keep_days: int = 30):
    """
    Rotate classification log files (keep last N days).

    Call this daily via Celery beat task.

    Args:
        keep_days: Number of days to keep (default 30)

    Usage:
        # In Celery beat schedule
        rotate_classification_logs.delay(keep_days=30)
    """
    if not CLASSIFICATION_LOG_FILE.exists():
        return

    from datetime import timedelta

    cutoff = datetime.utcnow() - timedelta(days=keep_days)

    # Read file, filter old entries, rewrite
    try:
        entries_to_keep = []

        with open(CLASSIFICATION_LOG_FILE, "r") as f:
            for line in f:
                try:
                    entry = json.loads(line)
                    timestamp = datetime.fromisoformat(entry["timestamp"].replace("Z", "+00:00"))

                    if timestamp >= cutoff:
                        entries_to_keep.append(line)

                except (json.JSONDecodeError, KeyError, ValueError):
                    # Keep malformed entries (safer)
                    entries_to_keep.append(line)

        # Rewrite file with filtered entries
        with open(CLASSIFICATION_LOG_FILE, "w") as f:
            f.writelines(entries_to_keep)

        logger = logging.getLogger(__name__)
        logger.info(f"Rotated classification logs: kept {len(entries_to_keep)} entries")

    except Exception as e:
        logging.getLogger(__name__).error(f"Failed to rotate classification logs: {e}")
