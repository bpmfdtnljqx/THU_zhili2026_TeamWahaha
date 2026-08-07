"""
src/recognition/providers/__init__.py

Provider layer for recognition engines.

Each provider wraps an external recognition API (Auris, AcoustID, etc.)
and normalises its response into the standard internal dict format:

    {
        "title": str,
        "artist": str,
        "confidence": float,        # 0.0 – 1.0
        "match_offset_secs": float | None,  # optional, for future use
    }

Providers are swappable: change the import in service.py to switch engines
without touching the router or frontend.
"""

from .auris import AurisProvider

__all__ = ["AurisProvider"]
