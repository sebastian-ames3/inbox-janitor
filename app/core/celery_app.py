"""
Celery application configuration for background task processing.

CRITICAL: This module initializes the Celery app with Redis broker and configures
all background tasks for email processing, classification, and scheduled jobs.
"""

from celery import Celery
from celery.schedules import crontab
from kombu import Queue

from app.core.config import settings


# Initialize Celery app
celery_app = Celery(
    "inbox_janitor",
    broker=settings.CELERY_BROKER_URL,
    backend=settings.CELERY_RESULT_BACKEND,
    include=[
        "app.tasks.ingest",
        "app.tasks.classify",
    ]
)


# Celery Configuration
celery_app.conf.update(
    # Serialization (JSON only for security)
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,

    # Task execution settings
    task_acks_late=True,  # Acknowledge after task completes (reliability)
    task_reject_on_worker_lost=True,  # Requeue if worker crashes
    task_track_started=True,  # Track when tasks start

    # Task timeout settings (prevent stuck tasks)
    task_time_limit=60,  # Hard limit: 60 seconds (kills task)
    task_soft_time_limit=50,  # Soft limit: 50 seconds (raises exception)

    # Task-specific timeout overrides (set in task decorators)
    task_annotations={
        "app.tasks.ingest.process_gmail_history": {
            "time_limit": 90,  # 90 seconds for history processing
            "soft_time_limit": 80,
        },
        "app.tasks.ingest.extract_email_metadata": {
            "time_limit": 30,  # 30 seconds for metadata extraction
            "soft_time_limit": 25,
        },
        "app.tasks.classify.classify_email_tier1": {
            "time_limit": 10,  # 10 seconds for classification
            "soft_time_limit": 8,
        },
    },

    # Retry settings (exponential backoff)
    task_default_retry_delay=60,  # 1 minute initial delay
    task_max_retries=3,  # Maximum 3 retries

    # Result backend settings
    result_expires=3600,  # Results expire after 1 hour
    result_backend_transport_options={
        "master_name": "mymaster",
        "visibility_timeout": 3600,
    },

    # Worker settings
    worker_prefetch_multiplier=4,  # Number of tasks to prefetch per worker
    worker_max_tasks_per_child=1000,  # Restart worker after 1000 tasks (prevent memory leaks)

    # Queue settings
    task_queues=(
        Queue("default", routing_key="task.#"),
        Queue("priority", routing_key="priority.#"),
    ),
    task_default_queue="default",
    task_default_exchange="tasks",
    task_default_exchange_type="topic",
    task_default_routing_key="task.default",
)


# Celery Beat Schedule (periodic tasks)
celery_app.conf.beat_schedule = {
    # Renew Gmail watches every 6 days (watches expire in 7 days)
    "renew-gmail-watches": {
        "task": "app.tasks.ingest.renew_all_gmail_watches",
        "schedule": crontab(hour="3", minute="0", day_of_week="*/6"),  # Every 6 days at 3 AM
        "options": {"queue": "priority"},
    },

    # Fallback polling every 10 minutes (catch missed webhooks)
    "fallback-poll-gmail": {
        "task": "app.tasks.ingest.fallback_poll_gmail",
        "schedule": crontab(minute="*/10"),  # Every 10 minutes
        "options": {"queue": "default"},
    },

    # Monitor undo rate every 5 minutes (alert if classifier broken)
    "monitor-undo-rate": {
        "task": "app.tasks.analytics.monitor_undo_rate",
        "schedule": crontab(minute="*/5"),  # Every 5 minutes
        "options": {"queue": "default"},
    },

    # Database cleanup daily at 2 AM UTC
    "cleanup-old-data": {
        "task": "app.tasks.maintenance.cleanup_old_data",
        "schedule": crontab(hour="2", minute="0"),  # Daily at 2 AM
        "options": {"queue": "default"},
    },
}


# Task routing (send specific tasks to priority queue)
celery_app.conf.task_routes = {
    "app.tasks.ingest.renew_all_gmail_watches": {"queue": "priority"},
    "app.tasks.ingest.process_gmail_history": {"queue": "default"},
    "app.tasks.classify.classify_email_tier1": {"queue": "default"},
}


# Autodiscover tasks from these modules
celery_app.autodiscover_tasks([
    "app.tasks.ingest",
    "app.tasks.classify",
    "app.tasks.analytics",
    "app.tasks.maintenance",
])


# Error handling
@celery_app.task(bind=True, max_retries=3)
def default_error_handler(self, *args, **kwargs):
    """Default error handler with exponential backoff."""
    try:
        return self.apply_async(args=args, kwargs=kwargs)
    except Exception as exc:
        # Exponential backoff: 60s, 120s, 240s
        retry_delay = 60 * (2 ** self.request.retries)
        raise self.retry(exc=exc, countdown=retry_delay)


# Logging configuration
celery_app.conf.worker_hijack_root_logger = False  # Don't override logging config
celery_app.conf.worker_log_format = "[%(asctime)s: %(levelname)s/%(processName)s] %(message)s"
celery_app.conf.worker_task_log_format = (
    "[%(asctime)s: %(levelname)s/%(processName)s] "
    "[%(task_name)s(%(task_id)s)] %(message)s"
)


if __name__ == "__main__":
    celery_app.start()
