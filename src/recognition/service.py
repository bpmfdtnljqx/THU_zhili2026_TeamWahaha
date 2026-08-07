"""
recognition/service.py

Music recognition service — delegates to external engines via the provider
layer, with graceful fallback to placeholder.

Architecture:
    Recognizer  ──►  AurisProvider (HTTP)   ──►  Auris API
                ──►  Placeholder (fallback)       (built-in)

--- HOW TO SWAP THE RECOGNITION ENGINE ---

1. Add a new provider in ``src/recognition/providers/``.
2. Import it here and swap the instantiation in ``Recognizer.__init__``.
3. The router and frontend need NO changes — the ``recognize()`` return
   dict is the stable contract.

--- REPLACEMENT GUIDE (for teammate) ---

When your own model is ready instead of Auris:
1. Write a new provider class with an ``identify(audio_file, filename)``
   method that returns {title, artist, confidence, match_offset_secs}.
2. Change ``_init_provider()`` to instantiate your provider.
3. Delete ``providers/auris.py`` if no longer needed.
"""

from __future__ import annotations

import logging
from typing import BinaryIO

from .providers.auris import AurisProvider

logger = logging.getLogger("lyra.recognition")


class Recognizer:
    """Music recognition engine.

    Tries the Auris fingerprinting engine first.  If Auris is unreachable
    or returns no match, falls back to a placeholder result so the rest of
    the system stays functional.

    Usage::

        recognizer = Recognizer()
        result = recognizer.recognize(uploaded_file, filename="recording.wav")
        # result: {"title": "...", "artist": "...", "confidence": 0.92,
        #          "match_offset_secs": 3.2}
    """

    def __init__(self):
        self._provider = _init_provider()
        logger.info("Recognizer ready — provider=%s", type(self._provider).__name__)

    def recognize(self, audio_file: BinaryIO, filename: str = "") -> dict:
        """Identify a song from raw audio data.

        Args:
            audio_file: A file-like object opened in binary mode (e.g. the
                result of ``UploadFile.file`` in FastAPI).
            filename: The original uploaded filename, for format hinting.

        Returns:
            dict with keys ``title``, ``artist``, ``confidence``,
            and ``match_offset_secs``.  Extra keys are harmless — the API
            layer picks the fields it needs.
        """
        # ── Try Auris provider ──────────────────────────────────────
        try:
            result = self._provider.identify(audio_file, filename)
            if result.get("title"):
                return result
            # Auris returned successfully but with no match.
            logger.info("Auris returned no match — returning placeholder")
        except Exception:
            logger.exception("Auris provider raised unexpectedly — falling back")

        # ── Fallback: placeholder ───────────────────────────────────
        return {
            "title": "",
            "artist": "",
            "confidence": 0.0,
            "match_offset_secs": None,
        }


# ---------------------------------------------------------------------------
# Private helpers
# ---------------------------------------------------------------------------


def _init_provider():
    """Create the recognition provider.

    Try Auris first.  If the environment variable is set to a non-default
    value we trust the user's intent; otherwise we still create the
    AurisProvider and let it handle connection failures gracefully at
    call time (so a late-started Auris container works without restarting
    the Lyra process).
    """
    try:
        provider = AurisProvider()
        # Quick connectivity check — non-fatal.
        # We don't actually call /identify here (no audio to send), but
        # the provider logs its endpoint URL for debugging.
        return provider
    except Exception:
        logger.exception("Failed to initialise Auris provider")
        # Return a bare provider-like object that always returns empty.
        return _FallbackProvider()


class _FallbackProvider:
    """Minimal provider used when Auris cannot even be imported."""

    def identify(self, audio_file: BinaryIO, filename: str = "") -> dict:
        return {
            "title": "",
            "artist": "",
            "confidence": 0.0,
            "match_offset_secs": None,
        }
