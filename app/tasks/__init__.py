"""
Celery tasks package.

This package contains all background tasks for email processing, classification,
and scheduled jobs.
"""

from app.core.celery_app import celery_app


@celery_app.task(name="test_celery_connection")
def test_celery_connection():
    """
    Test task to verify Celery worker is functioning correctly.

    This task simply logs a success message and returns True.
    Use this to verify:
    - Celery worker is connected to Redis
    - Tasks can be enqueued and executed
    - Worker logs are visible

    Usage:
        # From Python shell or code:
        from app.tasks import test_celery_connection
        result = test_celery_connection.delay()

        # From Celery CLI:
        celery -A app.core.celery_app call app.tasks.test_celery_connection
    """
    import logging
    logger = logging.getLogger(__name__)

    logger.info("SUCCESS: Celery works! Test task executed successfully.")

    return {
        "status": "success",
        "message": "Celery worker is functioning correctly!",
        "task_name": "test_celery_connection"
    }


@celery_app.task(name="test_celery_with_retry")
def test_celery_with_retry(should_fail: bool = False):
    """
    Test task to verify retry mechanism works correctly.

    Args:
        should_fail: If True, raises exception to test retry logic

    Usage:
        # Test successful execution:
        test_celery_with_retry.delay(should_fail=False)

        # Test retry mechanism:
        test_celery_with_retry.delay(should_fail=True)
    """
    import logging
    logger = logging.getLogger(__name__)

    if should_fail:
        logger.warning("WARNING: Test task intentionally failing to test retry mechanism")
        raise Exception("Intentional failure for retry testing")

    logger.info("SUCCESS: Test task with retry executed successfully")

    return {
        "status": "success",
        "message": "Retry mechanism verified",
        "task_name": "test_celery_with_retry"
    }
