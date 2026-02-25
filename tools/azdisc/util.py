"""Utility helpers for azdisc."""
import re


def extract_arm_ids(obj):
    """Recursively walk any dict/list/str and return set of ARM IDs (lowercase)."""
    found = set()
    if isinstance(obj, str):
        s = obj.lower().strip()
        if s.startswith("/subscriptions/") and "/providers/" in s:
            found.add(s)
    elif isinstance(obj, dict):
        for v in obj.values():
            found |= extract_arm_ids(v)
    elif isinstance(obj, list):
        for item in obj:
            found |= extract_arm_ids(item)
    return found


def normalize_id(id_str):
    """Lowercase and strip an ARM ID."""
    return id_str.lower().strip()


def slug(id_str):
    """Deterministic alias from ARM id: replace non-alphanumeric with '_', truncate to 60 chars."""
    s = re.sub(r"[^a-zA-Z0-9]", "_", id_str.lower())
    s = s.strip("_")
    return s[:60]


def chunk(lst, size):
    """Yield successive chunks of `size` from list `lst`."""
    for i in range(0, len(lst), size):
        yield lst[i : i + size]


def sort_keys(d):
    """Recursively sort dict keys for deterministic JSON serialization."""
    if isinstance(d, dict):
        return {k: sort_keys(v) for k in sorted(d.keys()) for v in [d[k]]}
    if isinstance(d, list):
        return [sort_keys(item) for item in d]
    return d


def parent_id(arm_id, segment):
    """Given an ARM id like '.../subnets/foo', return the part before '/{segment}/...'."""
    lower = arm_id.lower()
    marker = "/" + segment.lower() + "/"
    idx = lower.find(marker)
    if idx == -1:
        return arm_id
    return arm_id[:idx]
