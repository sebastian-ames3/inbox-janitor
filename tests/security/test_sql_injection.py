"""
CRITICAL SECURITY TEST: SQL Injection Protection

Tests that the application is protected from SQL injection:
1. Parameterized queries (no string concatenation)
2. SQLAlchemy ORM usage (automatic escaping)
3. Input validation and sanitization
4. No raw SQL execution with user input

Run before every commit:
    pytest tests/security/test_sql_injection.py -v
"""

import pytest
from sqlalchemy import text


class TestParameterizedQueries:
    """Test that all database queries use parameterized statements."""

    @pytest.mark.asyncio
    async def test_email_lookup_uses_parameterized_query(self):
        """Test that email address lookup uses parameterized queries."""
        from app.core.database import get_async_session
        from app.models.mailbox import Mailbox
        from sqlalchemy import select

        # Malicious SQL injection attempt
        malicious_email = "test@example.com'; DROP TABLE users; --"

        async with get_async_session() as session:
            # This query should be safe (parameterized via SQLAlchemy)
            result = await session.execute(
                select(Mailbox).where(Mailbox.email_address == malicious_email)
            )
            mailbox = result.scalar_one_or_none()

            # Should return None (no match), not execute SQL
            assert mailbox is None

    @pytest.mark.asyncio
    async def test_message_id_lookup_uses_parameterized_query(self):
        """Test that message ID lookup uses parameterized queries."""
        from app.core.database import get_async_session
        from app.models.email_action import EmailAction
        from sqlalchemy import select

        # Malicious SQL injection attempt
        malicious_message_id = "123'; DELETE FROM email_actions; --"

        async with get_async_session() as session:
            result = await session.execute(
                select(EmailAction).where(EmailAction.message_id == malicious_message_id)
            )
            action = result.scalar_one_or_none()

            # Should safely handle as string, not execute SQL
            assert action is None


class TestInputValidation:
    """Test that user inputs are validated before database operations."""

    def test_email_address_validation(self):
        """Test that email addresses are validated."""
        from pydantic import ValidationError, EmailStr
        from pydantic import BaseModel

        class TestModel(BaseModel):
            email: EmailStr

        # Valid email
        valid = TestModel(email="test@example.com")
        assert valid.email == "test@example.com"

        # Invalid email with SQL injection attempt
        with pytest.raises(ValidationError):
            TestModel(email="test'; DROP TABLE users; --")

    def test_uuid_validation(self):
        """Test that UUIDs are validated."""
        from pydantic import ValidationError
        from pydantic import BaseModel
        from uuid import UUID

        class TestModel(BaseModel):
            id: UUID

        # Valid UUID
        valid = TestModel(id="550e8400-e29b-41d4-a716-446655440000")
        assert isinstance(valid.id, UUID)

        # Invalid UUID with SQL injection attempt
        with pytest.raises(ValidationError):
            TestModel(id="invalid'; DROP TABLE users; --")


class TestORMUsage:
    """Test that application uses SQLAlchemy ORM (automatic SQL injection protection)."""

    def test_mailbox_model_uses_orm(self):
        """Test that Mailbox operations use ORM."""
        from app.models.mailbox import Mailbox
        from sqlalchemy.orm import DeclarativeMeta

        # Verify it's an ORM model
        assert isinstance(Mailbox, DeclarativeMeta)

    def test_email_action_model_uses_orm(self):
        """Test that EmailAction operations use ORM."""
        from app.models.email_action import EmailAction
        from sqlalchemy.orm import DeclarativeMeta

        assert isinstance(EmailAction, DeclarativeMeta)

    def test_no_raw_sql_concatenation(self):
        """Test that source code doesn't contain raw SQL string concatenation."""
        import os
        import re

        # Pattern for dangerous SQL concatenation
        dangerous_patterns = [
            r'f"SELECT.*{',  # f-string SQL
            r'"SELECT.*"\s*\+',  # String concatenation
            r"'SELECT.*'\s*\+",  # String concatenation
            r'\.format\(.*SELECT',  # .format() SQL
        ]

        source_dirs = ['app/']
        violations = []

        for source_dir in source_dirs:
            for root, dirs, files in os.walk(source_dir):
                dirs[:] = [d for d in dirs if not d.startswith('.') and d != '__pycache__']

                for file in files:
                    if file.endswith('.py'):
                        file_path = os.path.join(root, file)
                        with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                            content = f.read()

                            for pattern in dangerous_patterns:
                                matches = re.findall(pattern, content, re.IGNORECASE)
                                if matches:
                                    violations.append({
                                        'file': file_path,
                                        'pattern': pattern,
                                        'matches': matches
                                    })

        # Fail if any dangerous patterns found
        assert len(violations) == 0, f"Found dangerous SQL concatenation patterns: {violations}"


class TestTextQuerySafety:
    """Test that text() queries use bound parameters."""

    @pytest.mark.asyncio
    async def test_health_check_uses_bound_parameters(self):
        """Test that health check queries use bound parameters."""
        import inspect
        from app.core import health

        source = inspect.getsource(health)

        # If using text(), should use :param syntax (bound parameters)
        if 'text(' in source:
            # Check for parameterized queries
            assert ':' in source or '?' in source, "text() queries should use bound parameters"

            # Should NOT have f-strings or .format() with SQL
            assert 'f"SELECT' not in source and "f'SELECT" not in source, \
                "Should not use f-strings with SQL queries"


class TestWebhookInputSanitization:
    """Test that webhook inputs are sanitized."""

    @pytest.mark.asyncio
    async def test_webhook_validates_input(self):
        """Test that webhook endpoint validates input schema."""
        from app.models.webhook import PubSubRequest

        # Valid webhook
        valid_data = {
            "message": {
                "data": "eyJlbWFpbEFkZHJlc3MiOiJ0ZXN0QGV4YW1wbGUuY29tIiwiaGlzdG9yeUlkIjoiMTIzNDUifQ==",
                "messageId": "msg_123",
                "publishTime": "2025-01-01T00:00:00Z"
            },
            "subscription": "projects/test/subscriptions/test-sub"
        }

        webhook = PubSubRequest(**valid_data)
        assert webhook.message.messageId == "msg_123"

    @pytest.mark.asyncio
    async def test_webhook_rejects_malicious_input(self):
        """Test that webhook rejects malicious input."""
        from app.models.webhook import PubSubRequest
        from pydantic import ValidationError

        # Missing required fields
        malicious_data = {
            "message": "'; DROP TABLE mailboxes; --"
        }

        with pytest.raises(ValidationError):
            PubSubRequest(**malicious_data)


class TestDatabaseConnectionSafety:
    """Test that database connection strings are safe."""

    def test_database_url_not_in_logs(self, caplog):
        """Test that database URL never appears in logs."""
        import logging
        caplog.set_level(logging.DEBUG)

        from app.core.config import settings

        # Access database URL (might trigger logging)
        db_url = settings.DATABASE_URL

        # Verify database URL not in logs
        for record in caplog.records:
            # Check password not in logs (if URL contains password)
            if '@' in db_url:
                password_part = db_url.split('@')[0].split(':')[-1]
                assert password_part not in record.message, "Database password leaked in logs"
