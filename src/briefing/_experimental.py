"""Experimental functions (#199): what they return may change in any release, without a deprecation period."""
from __future__ import annotations

import warnings


class ExperimentalWarning(UserWarning):
    """Warns, once per session, that a function is experimental (``bf.deck.from_report``…).

    What an experimental function returns may change in any release, without a deprecation
    period. Silence the warning with ``warnings.filterwarnings("ignore", category=bf.ExperimentalWarning)``.

    Example::

        import warnings
        warnings.filterwarnings("ignore", category=bf.ExperimentalWarning)
    """


_warned: set[str] = set()


def experimental(name: str, stacklevel: int = 3) -> None:
    """Warn that *name* is experimental, the first time it is called in this session.

    *stacklevel* as ``warnings.warn`` takes it: 3 points at the caller of the function that calls this.
    """
    if name in _warned:
        return
    _warned.add(name)
    warnings.warn(
        f"{name} is experimental: what it returns may change in any release, without a deprecation period. "
        "Check the result; silence this with warnings.filterwarnings('ignore', category=bf.ExperimentalWarning).",
        ExperimentalWarning,
        stacklevel=stacklevel,
    )


__all__ = ["ExperimentalWarning", "experimental"]
