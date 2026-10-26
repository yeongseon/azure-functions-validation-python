"""Intentionally insecure scanner canary; this throwaway branch must never merge."""

import hashlib


def insecure_digest(payload: bytes) -> str:
    return hashlib.md5(payload).hexdigest()
