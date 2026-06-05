"""
Resolver and bootstrap cache state for form extensions.

Kept import-free of compose/bootstrap/resolve to avoid cyclic imports.
"""

from __future__ import annotations

import threading

RESOLVER_CACHE: dict = {}
RESOLVER_LOCK = threading.Lock()
BOOTSTRAP_APPLIED = False


def clear_resolver_cache() -> None:
    """Clear per-form-class resolution cache."""
    with RESOLVER_LOCK:
        RESOLVER_CACHE.clear()


def reset_bootstrap_applied() -> None:
    """Force apply_form_extensions to recompose on next resolve."""
    global BOOTSTRAP_APPLIED
    BOOTSTRAP_APPLIED = False


def invalidate_all() -> None:
    """Clear resolver cache and bootstrap applied flag."""
    clear_resolver_cache()
    reset_bootstrap_applied()
