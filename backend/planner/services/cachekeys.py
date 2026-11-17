import hashlib


def key(prefix: str, raw: str) -> str:
    """Short, backend-safe cache key (no spaces/control chars, bounded length)."""
    return f"{prefix}:{hashlib.sha1(raw.encode()).hexdigest()}"
