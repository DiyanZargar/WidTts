"""Tests for envelope encryption round-trip.

Verifies:
- encrypt_credential → decrypt_credential round-trip
- different encryptions produce different ciphertexts (random nonces)
- corrupted ciphertext fails cleanly
- key wrapping/unwrapping works
"""
import os
import pytest
from app.shared.security.envelope_encryption import (
    generate_dek,
    wrap_dek,
    unwrap_dek,
    encrypt_credential,
    decrypt_credential,
)


class TestDEKManagement:
    def test_generate_dek_is_32_bytes(self):
        dek = generate_dek()
        assert len(dek) == 32

    def test_generate_dek_is_random(self):
        dek1 = generate_dek()
        dek2 = generate_dek()
        assert dek1 != dek2

    def test_wrap_unwrap_round_trip(self):
        dek = generate_dek()
        wrapped, nonce = wrap_dek(dek)
        unwrapped = unwrap_dek(wrapped, nonce)
        assert unwrapped == dek

    def test_wrap_produces_different_output_each_time(self):
        dek = generate_dek()
        wrapped1, nonce1 = wrap_dek(dek)
        wrapped2, nonce2 = wrap_dek(dek)
        # Different nonces → different wrapped output
        assert nonce1 != nonce2
        assert wrapped1 != wrapped2

    def test_unwrap_with_wrong_nonce_fails(self):
        dek = generate_dek()
        wrapped, nonce = wrap_dek(dek)
        wrong_nonce = os.urandom(12)
        with pytest.raises(Exception):
            unwrap_dek(wrapped, wrong_nonce)

    def test_unwrap_with_wrong_wrapped_data_fails(self):
        dek = generate_dek()
        wrapped, nonce = wrap_dek(dek)
        wrong_wrapped = os.urandom(len(wrapped))
        with pytest.raises(Exception):
            unwrap_dek(wrong_wrapped, nonce)


class TestCredentialEncryption:
    def test_round_trip_simple(self):
        dek = generate_dek()
        plaintext = {"api_key": "sk-test-12345"}
        blob = encrypt_credential(plaintext, dek)
        result = decrypt_credential(blob, dek)
        assert result == plaintext

    def test_round_trip_complex(self):
        dek = generate_dek()
        plaintext = {"api_key": "sk-abc", "secret": "xyz", "nested": {"a": 1}}
        blob = encrypt_credential(plaintext, dek)
        result = decrypt_credential(blob, dek)
        assert result == plaintext

    def test_different_encryptions_different_ciphertext(self):
        dek = generate_dek()
        plaintext = {"api_key": "same-key"}
        blob1 = encrypt_credential(plaintext, dek)
        blob2 = encrypt_credential(plaintext, dek)
        # Different nonces → different ciphertexts
        assert blob1["nonce"] != blob2["nonce"]
        assert blob1["ciphertext"] != blob2["ciphertext"]

    def test_plaintext_not_exposed_in_blob(self):
        dek = generate_dek()
        plaintext = {"api_key": "super-secret-key-12345"}
        blob = encrypt_credential(plaintext, dek)
        # The raw ciphertext should not contain the plaintext
        assert "super-secret-key-12345" not in blob["ciphertext"]
        assert "super-secret-key-12345" not in blob["nonce"]

    def test_decrypt_with_wrong_key_fails(self):
        dek = generate_dek()
        wrong_dek = generate_dek()
        plaintext = {"api_key": "test"}
        blob = encrypt_credential(plaintext, dek)
        with pytest.raises(Exception):
            decrypt_credential(blob, wrong_dek)

    def test_decrypt_with_corrupted_ciphertext_fails(self):
        dek = generate_dek()
        plaintext = {"api_key": "test"}
        blob = encrypt_credential(plaintext, dek)
        blob["ciphertext"] = blob["ciphertext"][:-4] + "XXXX"
        with pytest.raises(Exception):
            decrypt_credential(blob, dek)

    def test_decrypt_with_corrupted_nonce_fails(self):
        dek = generate_dek()
        plaintext = {"api_key": "test"}
        blob = encrypt_credential(plaintext, dek)
        blob["nonce"] = blob["nonce"][:-4] + "XXXX"
        with pytest.raises(Exception):
            decrypt_credential(blob, dek)

    def test_round_trip_empty_dict(self):
        dek = generate_dek()
        plaintext = {}
        blob = encrypt_credential(plaintext, dek)
        result = decrypt_credential(blob, dek)
        assert result == {}

    def test_round_trip_unicode_values(self):
        dek = generate_dek()
        plaintext = {"name": "日本語テスト", "emoji": "🔐"}
        blob = encrypt_credential(plaintext, dek)
        result = decrypt_credential(blob, dek)
        assert result == plaintext
