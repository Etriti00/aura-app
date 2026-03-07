"""
Aura — Key Vault
Hardware-bound Fernet encryption for API key storage.
Keys are tied to the machine via py-machineid so the .db file
is unreadable if copied to another machine.
"""

import hashlib
import base64
from cryptography.fernet import Fernet, InvalidToken

try:
    import machineid
    _MACHINE_ID_AVAILABLE = True
except ImportError:
    _MACHINE_ID_AVAILABLE = False

from config import ENCRYPTION_SALT


class KeyVault:
    """Encrypts and decrypts API keys using a machine-hardware-derived Fernet key."""

    def __init__(self):
        self._fernet = Fernet(self._derive_key())

    def _derive_key(self) -> bytes:
        """Derive a Fernet-compatible key from machine hardware ID + salt."""
        if _MACHINE_ID_AVAILABLE:
            hw_id = machineid.id()
        else:
            # Fallback for development/testing — less secure
            import platform
            hw_id = platform.node() + platform.machine()

        raw = f"{hw_id}:{ENCRYPTION_SALT}".encode("utf-8")
        digest = hashlib.sha256(raw).digest()
        # Fernet requires a 32-byte URL-safe base64-encoded key
        return base64.urlsafe_b64encode(digest)

    def encrypt(self, plaintext: str) -> str:
        """Encrypt a plaintext string, return hex-encoded ciphertext."""
        if not plaintext:
            return ""
        token = self._fernet.encrypt(plaintext.encode("utf-8"))
        return token.hex()

    def decrypt(self, hex_ciphertext: str) -> str:
        """Decrypt a hex-encoded ciphertext, return plaintext string."""
        if not hex_ciphertext:
            return ""
        try:
            token = bytes.fromhex(hex_ciphertext)
            return self._fernet.decrypt(token).decode("utf-8")
        except (InvalidToken, ValueError):
            return ""

    @staticmethod
    def mask(plaintext: str, visible_chars: int = 4) -> str:
        """
        Mask a sensitive string for display.
        Example: 'sk-proj-abc123456789' → 'sk-proj-****6789'
        """
        if not plaintext or len(plaintext) <= visible_chars:
            return "****"

        # Find the last dash-separated prefix
        parts = plaintext.split("-")
        if len(parts) > 1:
            prefix = "-".join(parts[:-1]) + "-"
            suffix = parts[-1]
            if len(suffix) <= visible_chars:
                return f"{prefix}****"
            return f"{prefix}****{suffix[-visible_chars:]}"
        else:
            return f"****{plaintext[-visible_chars:]}"
