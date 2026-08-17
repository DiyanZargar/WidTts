"""Unit tests for the EncryptedBlob data model."""

import pytest
from pydantic import ValidationError

from app.shared.models.security import EncryptedBlob


def test_valid_encrypted_blob():
    blob = EncryptedBlob(nonce="YWJjZGVmMTIzNDU2", ciphertext="c2VjcmV0ZGF0YQ==")
    assert blob.nonce == "YWJjZGVmMTIzNDU2"
    assert blob.ciphertext == "c2VjcmV0ZGF0YQ=="


def test_invalid_encrypted_blob_missing_fields():
    with pytest.raises(ValidationError):
        EncryptedBlob.model_validate({"nonce": "YWJjZGVmMTIzNDU2"})

    with pytest.raises(ValidationError):
        EncryptedBlob.model_validate({"ciphertext": "c2VjcmV0ZGF0YQ=="})

