"""
recognition/service.py

Music recognition service — delegates to the cloud-based AudD
recognition API via the provider layer.

Architecture:
    Recognizer  ──►  AudDProvider (HTTP)   ──►  AudD Cloud API
                ──►  Placeholder (fallback)      (built-in)

The recognition database is maintained by AudD.
Lyra does not require a local music fingerprint database.

--- HOW TO SWAP THE RECOGNITION ENGINE ---

1. Add a new provider in ``src/recognition/providers/``.
2. Import it here and swap the provider instantiation in
   ``_init_provider()``.
3. The router and frontend need NO changes — the ``recognize()``
   return dict is the stable contract.

--- REPLACEMENT GUIDE ---

When another recognition engine is ready:

1. Write a new provider class with an
   ``identify(audio_file, filename)`` method.

2. Make it return a dictionary containing at least:
   {
       "title": "...",
       "artist": "...",
       "confidence": 0.0,
       "match_offset_secs": None,
   }

3. Change ``_init_provider()`` to instantiate the new provider.

The rest of the Lyra recognition pipeline remains unchanged.
"""

from __future__ import annotations

import logging
from typing import BinaryIO

from .providers.audd import AudDProvider


logger = logging.getLogger("lyra.recognition")


class Recognizer:
    """Music recognition engine.

    Uses the AudD cloud recognition service.

    If AudD is unreachable, fails to initialise, or returns no match,
    the recognizer falls back to an empty result so the rest of the
    Lyra system remains functional.

    Usage::

        recognizer = Recognizer()

        result = recognizer.recognize(
            uploaded_file,
            filename="recording.wav",
        )

        # result:
        # {
        #     "title": "...",
        #     "artist": "...",
        #     "confidence": 0.92,
        #     "match_offset_secs": 3.2,
        # }
    """

    def __init__(self):
        self._provider = _init_provider()

        logger.info(
            "Recognizer ready — provider=%s",
            type(self._provider).__name__,
        )

    def recognize(
        self,
        audio_file: BinaryIO,
        filename: str = "",
    ) -> dict:
        """Identify a song from raw audio data.

        Args:
            audio_file:
                A file-like object opened in binary mode, such as
                ``UploadFile.file`` from FastAPI.

            filename:
                The original uploaded filename.

        Returns:
            A dictionary containing recognition information.

            At minimum:

            {
                "title": str,
                "artist": str,
                "confidence": float,
                "match_offset_secs": float | None,
            }

            Providers may return additional fields such as:

            {
                "album": str,
                "release_date": str,
                "song_link": str,
            }

            Extra fields are harmless as long as the API response
            model accepts them.
        """

        # ── Try AudD provider ──────────────────────────────────────
        try:
            result = self._provider.identify(
                audio_file,
                filename,
            )

            if result.get("title"):
                return result

            # AudD returned successfully but no song was identified.
            logger.info(
                "AudD returned no match — returning placeholder"
            )

        except Exception:
            logger.exception(
                "AudD provider raised unexpectedly — falling back"
            )

        # ── Fallback: empty result ─────────────────────────────────
        return _empty_result()


# ---------------------------------------------------------------------------
# Private helpers
# ---------------------------------------------------------------------------


def _init_provider():
    """Create the cloud-based recognition provider.

    AudD is the primary recognition engine.

    If AudD cannot be initialised, return a fallback provider so that
    the rest of the Lyra backend can continue running.
    """

    try:
        provider = AudDProvider()

        logger.info(
            "AudD provider initialised successfully"
        )

        return provider

    except Exception:
        logger.exception(
            "Failed to initialise AudD provider"
        )

        return _FallbackProvider()


class _FallbackProvider:
    """Minimal provider used when AudD cannot be initialised."""

    def identify(
        self,
        audio_file: BinaryIO,
        filename: str = "",
    ) -> dict:
        """Return an empty recognition result."""

        return _empty_result()


def _empty_result() -> dict:
    """Return a no-match recognition result."""

    return {
        "title": "",
        "artist": "",
        "confidence": 0.0,
        "match_offset_secs": None,
    }