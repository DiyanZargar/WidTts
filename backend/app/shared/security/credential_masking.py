"""
Credential masking utilities for safe logging.

Never log plaintext API keys, tokens, or secrets.
"""


def mask_credential(value: str, visible_prefix: int = 3, visible_suffix: int = 2) -> str:
    """
    Mask a credential string for safe logging.

    Examples:
        mask_credential("sk-abc123xyz789") → "sk-...89"
        mask_credential("short") → "sh...rt"
        mask_credential("ab") → "**"
    """
    if not value:
        return "***"
    if len(value) <= 4:
        return "*" * len(value)

    prefix = value[:visible_prefix]
    suffix = value[-visible_suffix:]
    return f"{prefix}...{suffix}"


def mask_dict(d: dict, sensitive_keys: set = None) -> dict:
    """
    Return a copy of a dict with sensitive values masked.

    Default sensitive keys: api_key, secret, password, token
    """
    if sensitive_keys is None:
        sensitive_keys = {"api_key", "secret", "password", "token", "key", "xi_api_key"}

    result = {}
    for k, v in d.items():
        if k.lower() in sensitive_keys and isinstance(v, str):
            result[k] = mask_credential(v)
        elif isinstance(v, dict):
            result[k] = mask_dict(v, sensitive_keys)
        else:
            result[k] = v
    return result
