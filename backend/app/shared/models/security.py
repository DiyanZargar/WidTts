"""Security and cryptography domain models."""

from pydantic import BaseModel, Field


class EncryptedBlob(BaseModel):
    """Envelope-encrypted cryptographic payload stored in DB JSON columns.

    Contains base64-encoded nonce and ciphertext encrypted via AES-256-GCM.
    """

    nonce: str = Field(
        ..., description="Base64-encoded 12-byte initialization vector / nonce"
    )
    ciphertext: str = Field(
        ..., description="Base64-encoded AES-256-GCM ciphertext"
    )
