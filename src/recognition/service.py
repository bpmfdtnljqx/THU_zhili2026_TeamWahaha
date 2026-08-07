"""
recognition/service.py

Placeholder music recognition service.

This file is intentionally a stub. It returns a fixed response so the HTTP
layer, frontend, and integration tests can all be wired up today.

--- REPLACEMENT GUIDE (for teammate) ---

When the real recognition model is ready:

1. Replace the body of ``Recognizer.recognize()`` with your model inference.
2. The method signature is:
       def recognize(self, audio_file: BinaryIO, filename: str = "") -> dict
   - ``audio_file`` is a file-like object opened in binary mode.
   - ``filename`` is the original uploaded filename (for format hinting).
3. Return a dict with these keys:
       {
           "title": str,        # recognised song title, or ""
           "artist": str,       # recognised artist, or ""
           "confidence": float, # 0.0 – 1.0
       }
4. The API layer (backend/routers/recognition.py) will wrap your dict
   into the standard HTTP response envelope automatically.
5. If recognition fails for a known reason, raise a custom exception.
   The exception handler will convert it to a clean error response.
6. Do NOT modify the router — it stays thin on purpose.

Supported formats: mp3, wav, flac, ogg, m4a (depends on your model).
"""

from __future__ import annotations

import logging
from typing import BinaryIO

logger = logging.getLogger("lyra.recognition")


class Recognizer:
    """Placeholder music recognition engine.

    Currently returns an empty result. Replace the internals with your
    fingerprinting / embedding model when ready.
    """

    def recognize(self, audio_file: BinaryIO, filename: str = "") -> dict:
        """Identify a song from raw audio data.

        Args:
            audio_file: A file-like object opened in binary mode (e.g. the
                result of ``UploadFile.file`` in FastAPI).
            filename: The original filename, for format detection.

        Returns:
            dict with keys ``title``, ``artist``, ``confidence``.
        """
        # ── Placeholder — replace with real inference below ──────────
        logger.info(
            "Recognition requested (filename=%s, size=%d bytes) — "
            "returning placeholder result.",
            filename or "<unknown>",
            _safe_file_size(audio_file),
        )

        # TODO: Replace with real recognition logic. Example skeleton:
        #
        #   import your_model
        #   audio_bytes = audio_file.read()
        #   result = your_model.identify(audio_bytes)
        #   return {
        #       "title":      result.title,
        #       "artist":     result.artist,
        #       "confidence": result.confidence,
        #   }
        #
        # For now, always return an empty placeholder.

        return {
            "title": "",
            "artist": "",
            "confidence": 0.0,
        }

    # ── Future extension points ────────────────────────────────────
    # Add helper methods here as your module grows:
    #   - _validate_format(filename) -> bool
    #   - _preprocess_audio(audio_bytes) -> processed_data
    #   - _fingerprint(processed_data) -> fingerprint
    #   - _search_fingerprint(fingerprint) -> match_result


# ---------------------------------------------------------------------------
# Private helpers
# ---------------------------------------------------------------------------


def _safe_file_size(f: BinaryIO) -> int:
    """Return the size of a file-like object without moving its cursor."""
    try:
        pos = f.tell()
        f.seek(0, 2)  # seek to end
        size = f.tell()
        f.seek(pos)  # restore position
        return size
    except (OSError, AttributeError):
        return -1
