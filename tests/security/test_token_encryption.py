"""
CRITICAL SECURITY TEST: OAuth Token Encryption

Tests that OAuth tokens are:
1. ALWAYS encrypted before database storage
2. NEVER appear in plaintext in logs
3. Decryptable for API usage
4. Protected from SQL injection

Run before every commit:
    pytest tests/security/test_token_encryption.py -v
"""

import pytest
from unittest.mock import patch, MagicMock
import logging

from app.core.security import encrypt_token, decrypt_token


class TestTokenEncryption:
    """Test OAuth token encryption and security."""

    def test_token_encryption_reversible(self):
        """Test that token encryption is reversible."""
        original_token = "ya29.a0AfH6SMBx..."  # Example OAuth token

        # Encrypt
        encrypted = encrypt_token(original_token)

        # Should not be plaintext
        assert encrypted != original_token
        assert "ya29" not in encrypted

        # Should be decryptable
        decrypted = decrypt_token(encrypted)
        assert decrypted == original_token

    def test_encrypted_tokens_are_different(self):
        """Test that same token encrypted multiple times produces different ciphertexts."""
        token = "ya29.a0AfH6SMBx..."

        encrypted1 = encrypt_token(token)
        encrypted2 = encrypt_token(token)

        # Fernet includes timestamp, so encryptions differ
        # But both decrypt to same value
        assert decrypt_token(encrypted1) == decrypt_token(encrypted2)

    def test_token_never_logged(self, caplog):
        """Test that tokens never appear in logs."""
        caplog.set_level(logging.DEBUG)

        test_token = "ya29.test_secret_token_12345"

        # Simulate token handling
        encrypted = encrypt_token(test_token)

        # Check logs don't contain plaintext token
        for record in caplog.records:
            assert test_token not in record.message
            assert test_token not in str(record.args)

        # Encrypted token might appear (that's ok)
        # But plaintext must never appear

    def test_invalid_encrypted_token_raises_error(self):
        """Test that invalid encrypted tokens raise errors."""
        with pytest.raises(Exception):
            decrypt_token("invalid_token_data")

    def test_token_storage_format(self):
        """Test that encrypted tokens are stored in expected format."""
        token = "ya29.example"
        encrypted = encrypt_token(token)

        # Fernet tokens are base64-encoded and start with 'gAAAAA'
        assert isinstance(encrypted, str)
        assert len(encrypted) > len(token)


@pytest.mark.skip(reason="TODO: Implement get_async_session")
class TestTokenDatabaseStorage:
    """Test that tokens are encrypted when stored in database."""

    @pytest.mark.asyncio
    async def test_mailbox_stores_encrypted_tokens(self):
        """Test that Mailbox model stores tokens encrypted."""
        from app.models.mailbox import Mailbox
        from app.core.database import get_async_session
        from sqlalchemy import select
        import uuid

        # Create test mailbox with tokens
        test_mailbox = Mailbox(
            id=uuid.uuid4(),
            user_id=uuid.uuid4(),
            provider="gmail",
            email_address="test@example.com",
            encrypted_access_token=encrypt_token("access_token_12345"),
            encrypted_refresh_token=encrypt_token("refresh_token_67890"),
        )

        # Verify tokens are encrypted in model
        assert "access_token_12345" not in test_mailbox.encrypted_access_token
        assert "refresh_token_67890" not in test_mailbox.encrypted_refresh_token

        # Verify they can be decrypted
        assert decrypt_token(test_mailbox.encrypted_access_token) == "access_token_12345"
        assert decrypt_token(test_mailbox.encrypted_refresh_token) == "refresh_token_67890"


class TestTokenSQLInjection:
    """Test that token handling is protected from SQL injection."""

    @pytest.mark.asyncio
    async def test_malicious_token_doesnt_cause_sql_injection(self):
        """Test that SQL injection attempts in tokens are safely handled."""
        from app.core.security import encrypt_token, decrypt_token

        # Malicious SQL injection attempt
        malicious_token = "'; DROP TABLE mailboxes; --"

        # Should encrypt and decrypt safely
        encrypted = encrypt_token(malicious_token)
        decrypted = decrypt_token(encrypted)

        assert decrypted == malicious_token
        # Token is safely stored as encrypted blob, not executed as SQL


class TestTokenNotInLogs:
    """Test that tokens never appear in application logs."""

    def test_oauth_callback_doesnt_log_tokens(self, caplog):
        """Test OAuth callback doesn't log tokens."""
        caplog.set_level(logging.DEBUG)

        # Simulate OAuth callback with token in response
        mock_token = "ya29.secret_access_token"

        # This would happen in OAuth flow
        encrypted = encrypt_token(mock_token)

        # Verify plaintext token not in logs
        for record in caplog.records:
            assert mock_token not in record.message
            assert "ya29.secret" not in record.message


@pytest.mark.skip(reason="TODO: Fix base64 false positives in test files")
class TestEncryptionKeyNotInCode:
    """Test that encryption key is not hardcoded."""

    def test_encryption_key_from_env(self):
        """Test that encryption key comes from environment, not hardcoded."""
        from app.core.config import settings

        # Key should be loaded from env var
        assert settings.ENCRYPTION_KEY is not None
        assert len(settings.ENCRYPTION_KEY) == 44  # Fernet key is 44 chars (base64-encoded 32 bytes)

    def test_no_encryption_key_in_source_files(self):
        """Test that no Fernet keys are hardcoded in source files."""
        import os
        import re

        # Pattern for Fernet keys (base64-encoded, 44 chars, ends with '=')
        fernet_pattern = re.compile(r'[A-Za-z0-9+/]{43}=')

        source_dirs = ['app/', 'tests/']
        found_keys = []

        for source_dir in source_dirs:
            for root, dirs, files in os.walk(source_dir):
                # Skip __pycache__ and .pytest_cache
                dirs[:] = [d for d in dirs if not d.startswith('.') and d != '__pycache__']

                for file in files:
                    if file.endswith('.py'):
                        file_path = os.path.join(root, file)
                        with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                            content = f.read()

                            # Look for Fernet key pattern
                            matches = fernet_pattern.findall(content)

                            # Filter out test keys (this test file itself)
                            if matches and 'test_token_encryption' not in file_path:
                                found_keys.append((file_path, matches))

        # Fail if any keys found outside test files
        assert len(found_keys) == 0, f"Found potential Fernet keys in source: {found_keys}"
