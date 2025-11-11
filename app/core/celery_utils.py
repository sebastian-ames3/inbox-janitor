"""
Utilities for running async code in Celery tasks.

CRITICAL: Celery workers use prefork pool which requires special handling
for async code. Using asyncio.run() closes the event loop, breaking async
database connections.
"""

import asyncio
from functools import wraps


def run_async_task(coro):
    """
    Run an async coroutine in a Celery task without closing the event loop.

    This function properly manages the event loop lifecycle to prevent
    "Event loop is closed" errors when using async database connections
    in Celery tasks.

    Args:
        coro: The async coroutine to run

    Returns:
        The result of the coroutine

    Usage:
        @celery_app.task
        def my_task():
            async def _do_work():
                # async code here
                pass

            return run_async_task(_do_work())
    """
    try:
        # Try to get existing event loop (in worker process)
        loop = asyncio.get_event_loop()
        if loop.is_closed():
            # Loop was closed, create a new one
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
    except RuntimeError:
        # No event loop exists, create one
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

    try:
        # Run the coroutine
        return loop.run_until_complete(coro)
    except Exception as e:
        # Ensure we don't leave the loop in a bad state
        # But DON'T close it (other tasks may need it)
        raise e


def async_task(func):
    """
    Decorator to make a Celery task async-friendly.

    Automatically wraps the task to properly handle async code
    without closing the event loop.

    Usage:
        @celery_app.task
        @async_task
        async def my_async_task(arg1, arg2):
            # async code here
            pass
    """
    @wraps(func)
    def wrapper(*args, **kwargs):
        return run_async_task(func(*args, **kwargs))
    return wrapper
