"""
Tests for core/key_vault.py — encryption, decryption, masking.
"""

import pytest
from core.key_vault import KeyVault


class TestEncryption:
    def test_round_trip(self):
        kv = KeyVault()
        original = "sk-test-123456789"
        encrypted = kv.encrypt(original)
        decrypted = kv.decrypt(encrypted)
        assert decrypted == original

    def test_empty_string(self):
        kv = KeyVault()
        assert kv.encrypt("") == ""
        assert kv.decrypt("") == ""

    def test_different_ciphertexts(self):
        kv = KeyVault()
        enc1 = kv.encrypt("same_key")
        enc2 = kv.encrypt("same_key")
        # Fernet uses different IV each time
        assert enc1 != enc2

    def test_decrypt_invalid_hex_returns_empty(self):
        kv = KeyVault()
        # Implementation gracefully returns "" on invalid input
        result = kv.decrypt("not_valid_hex_at_all_!!!")
        assert result == ""

    def test_long_key(self):
        kv = KeyVault()
        long_key = "x" * 5000
        encrypted = kv.encrypt(long_key)
        decrypted = kv.decrypt(encrypted)
        assert decrypted == long_key

    def test_special_characters(self):
        kv = KeyVault()
        special = "key-with-$pecial!@#%^&*()_+=chars/\\\"'"
        encrypted = kv.encrypt(special)
        decrypted = kv.decrypt(encrypted)
        assert decrypted == special

    def test_unicode(self):
        kv = KeyVault()
        unicode_key = "key-with-émojis-🔑-and-ñ"
        encrypted = kv.encrypt(unicode_key)
        decrypted = kv.decrypt(encrypted)
        assert decrypted == unicode_key


class TestMasking:
    def test_mask_long_key(self):
        kv = KeyVault()
        masked = kv.mask("sk-proj-abc123456789")
        # Implementation: prefix="sk-proj-", suffix="abc123456789", visible=4
        # Result: "sk-proj-****6789"
        assert masked.startswith("sk-proj-")
        assert masked.endswith("6789")
        assert "****" in masked

    def test_mask_short_key(self):
        kv = KeyVault()
        masked = kv.mask("short")
        # "short" has 5 chars > visible_chars(4), no dashes → "****" + last 4
        assert masked == "****hort"

    def test_mask_empty(self):
        kv = KeyVault()
        masked = kv.mask("")
        # Implementation returns "****" for empty/short strings
        assert masked == "****"
