"""
Security utilities for token encryption, JWT handling, and sensitive data protection.

CRITICAL SECURITY REQUIREMENTS:
1. NEVER log tokens (access_token, refresh_token)
2. ALWAYS encrypt OAuth tokens before database storage
3. NEVER store email bodies in database
4. ALWAYS use parameterized queries (SQLAlchemy ORM handles this)
"""

import secrets
from datetime import datetime, timedelta
from typing import Optional
from cryptography.fernet import Fernet
from jose import jwt, JWTError

from app.core.config import settings


class TokenEncryption:
    """
    Symmetric encryption for OAuth tokens using Fernet (AES-128-CBC + HMAC).

    Fernet is chosen for:
    - Fast symmetric encryption
    - Built-in key rotation support
    - HMAC for authenticity
    - Simple API (less room for mistakes)

    For 500+ users, migrate to KMS (AWS KMS, Google Cloud KMS).
    """

    def __init__(self, encryption_key: str):
        """
        Initialize with encryption key.

        Key must be 44-character base64-encoded string.
        Generate with: Fernet.generate_key().decode()
        """
        self._fernet = Fernet(encryption_key.encode())

    def encrypt(self, plaintext: str) -> str:
        """
        Encrypt plaintext string.

        Args:
            plaintext: OAuth token or other sensitive string

        Returns:
            Base64-encoded encrypted string (safe for database storage)
        """
        if not plaintext:
            raise ValueError("Cannot encrypt empty string")

        # Encrypt and return as string
        encrypted_bytes = self._fernet.encrypt(plaintext.encode())
        return encrypted_bytes.decode()

    def decrypt(self, ciphertext: str) -> str:
        """
        Decrypt ciphertext string.

        Args:
            ciphertext: Encrypted token from database

        Returns:
            Original plaintext string

        Raises:
            cryptography.fernet.InvalidToken: If decryption fails
        """
        if not ciphertext:
            raise ValueError("Cannot decrypt empty string")

        # Decrypt and return as string
        decrypted_bytes = self._fernet.decrypt(ciphertext.encode())
        return decrypted_bytes.decode()

    def rotate_token(self, old_encrypted: str, new_key: Fernet) -> str:
        """
        Rotate encryption key (decrypt with old, encrypt with new).

        Used for annual key rotation without re-authenticating users.

        Args:
            old_encrypted: Token encrypted with old key
            new_key: New Fernet instance with new key

        Returns:
            Token re-encrypted with new key
        """
        plaintext = self.decrypt(old_encrypted)
        return new_key.encrypt(plaintext.encode()).decode()


# Global encryption instance
token_encryptor = TokenEncryption(settings.ENCRYPTION_KEY)


def encrypt_token(token: str) -> str:
    """
    Encrypt OAuth token for database storage.

    Usage:
        encrypted = encrypt_token(oauth_response.access_token)
        mailbox.encrypted_access_token = encrypted
    """
    return token_encryptor.encrypt(token)


def decrypt_token(encrypted_token: str) -> str:
    """
    Decrypt OAuth token from database.

    Usage:
        decrypted = decrypt_token(mailbox.encrypted_access_token)
        gmail_service = build('gmail', 'v1', credentials=decrypted)

    WARNING: Never log the decrypted token!
    """
    return token_encryptor.decrypt(encrypted_token)


def create_magic_link_token(
    user_id: str,
    action: str,
    expires_hours: int = 24
) -> str:
    """
    Create JWT token for magic links (one-click actions via email).

    Args:
        user_id: User UUID
        action: Action type ('undo_24h', 'enable_action_mode', 'cleanup_backlog')
        expires_hours: Token expiration in hours

    Returns:
        JWT token string

    Usage:
        token = create_magic_link_token(user.id, 'undo_24h')
        link = f"{settings.APP_URL}/a/{token}"
    """
    payload = {
        "user_id": user_id,
        "action": action,
        "exp": datetime.utcnow() + timedelta(hours=expires_hours),
        "iat": datetime.utcnow(),
    }
    return jwt.encode(payload, settings.SECRET_KEY, algorithm="HS256")


def verify_magic_link_token(token: str) -> Optional[dict]:
    """
    Verify and decode magic link token.

    Args:
        token: JWT token from URL

    Returns:
        Decoded payload dict if valid, None if invalid/expired

    Usage:
        payload = verify_magic_link_token(token)
        if payload:
            user_id = payload['user_id']
            action = payload['action']
    """
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=["HS256"])
        return payload
    except JWTError:
        return None


def generate_state_token() -> str:
    """
    Generate secure random state token for OAuth flow (CSRF protection).

    Returns:
        32-character hex string

    Usage:
        state = generate_state_token()
        redis.setex(f"oauth_state:{state}", 600, user_id)  # 10 min expiry
    """
    return secrets.token_hex(32)


def generate_encryption_key() -> str:
    """
    Generate new Fernet encryption key.

    Returns:
        44-character base64-encoded key

    Usage:
        key = generate_encryption_key()
        print(f"ENCRYPTION_KEY={key}")  # Add to .env

    WARNING: Only use during initial setup. Never regenerate in production
    without migrating existing tokens first!
    """
    return Fernet.generate_key().decode()


# Security helper functions

def is_email_body_in_text(text: str) -> bool:
    """
    Detect if text suspiciously contains full email body content.

    Used as safety check before logging/storing text.
    Returns True if text is likely a full email body (> 1000 chars with HTML).

    Usage:
        if is_email_body_in_text(log_message):
            raise SecurityError("Attempted to log email body!")
    """
    if len(text) > 1000 and ("<html" in text.lower() or "<div" in text.lower()):
        return True
    return False


def sanitize_for_logging(email_address: str, subject: str, snippet: str) -> dict:
    """
    Sanitize email metadata for safe logging (no PII, no full content).

    Args:
        email_address: Sender email
        subject: Email subject
        snippet: First 200 chars of email

    Returns:
        Dict safe for logging (truncated, no sensitive patterns)

    Usage:
        safe_data = sanitize_for_logging(from_addr, subject, snippet)
        logger.info("Classified email", extra=safe_data)
    """
    # Truncate subject and snippet
    safe_subject = subject[:100] + "..." if len(subject) > 100 else subject
    safe_snippet = snippet[:200] + "..." if len(snippet) > 200 else snippet

    # Mask email domain (keep first 3 chars + domain)
    # e.g., "seb***@example.com"
    if "@" in email_address:
        local, domain = email_address.split("@", 1)
        masked_local = local[:3] + "***" if len(local) > 3 else "***"
        safe_email = f"{masked_local}@{domain}"
    else:
        safe_email = "***@unknown"

    return {
        "from": safe_email,
        "subject": safe_subject,
        "snippet": safe_snippet,
    }
