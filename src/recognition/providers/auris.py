"""
recognition/providers/auris.py

HTTP client for the Auris audio recognition engine.

Auris is a self-hosted Shazam-style fingerprinting server (Rust / Axum).
This provider sends an audio clip to Auris's ``POST /identify`` endpoint
and normalises the response.

--- Auris API reference ---

Endpoint:   POST /identify
Content-Type: multipart/form-data
Field:      ``file`` — audio binary (mp3/wav/flac/ogg, 10–15 s recommended)

Success response (200):
    {
        "matches": [
            {
                "track": {
                    "id": "uuid",
                    "title": "夜曲",
                    "artist": "周杰伦",
                    "status": "ready",
                    "duration_secs": 213.5,
                    "created_at": "2026-08-07T12:00:00Z"
                },
                "confidence": 0.92,
                "match_count": 47,
                "offset_secs": 3.2
            }
        ],
        "query_duration_ms": 420,
        "sample_duration_secs": 10.5
    }

No-match response (200):
    {"matches": [], "query_duration_ms": 400, "sample_duration_secs": 10.5}

--- Configuration ---

Set the Auris API base URL via environment variable::

    AURIS_API_URL=http://127.0.0.1:8001

If unset, defaults to ``http://127.0.0.1:8001`` (Auris default port
remapped to avoid collision with Lyra on 8000).
"""

from __future__ import annotations

import logging
import os
from typing import BinaryIO, Optional

import httpx

logger = logging.getLogger("lyra.recognition.auris")

# ── Constants ────────────────────────────────────────────────────────────

_DEFAULT_AURIS_URL = "http://127.0.0.1:8001"
_REQUEST_TIMEOUT_S = 8.0           # generous for fingerprint matching (~500 ms typical)
_MIN_CONFIDENCE = 0.0
_MAX_CONFIDENCE = 1.0


class AurisProvider:
    """Thin HTTP client for the Auris /identify endpoint.

    Stateless — one instance can serve the lifetime of the process.
    """

    def __init__(self, base_url: Optional[str] = None):
        """
        Args:
            base_url: Auris API root, e.g. ``http://192.168.1.50:8001``.
                      Reads ``AURIS_API_URL`` env var if omitted.
        """
        self._base_url = (base_url or os.getenv("AURIS_API_URL", _DEFAULT_AURIS_URL)).rstrip("/")
        self._identify_url = f"{self._base_url}/identify"
        self._timeout = _REQUEST_TIMEOUT_S

        logger.info("Auris provider initialised — endpoint=%s", self._identify_url)

    # ── Public API ──────────────────────────────────────────────────────

    def identify(self, audio_file: BinaryIO, filename: str = "") -> dict:
        """Send audio to Auris and return the best match.

        Args:
            audio_file: A file-like object opened in binary mode
                (e.g. ``UploadFile.file`` from FastAPI).
            filename: Original filename, passed to Auris for format detection.

        Returns:
            Normalised dict::

                {
                    "title":            str,   # empty string if no match
                    "artist":           str,
                    "confidence":       float, # 0.0 – 1.0
                    "match_offset_secs": float | None,
                }
        """
        audio_bytes = audio_file.read()

        if not audio_bytes:
            logger.warning("Empty audio file received — returning no-match")
            return _empty_result()

        logger.info(
            "Sending %d bytes to Auris (filename=%s)",
            len(audio_bytes),
            filename or "<unknown>",
        )

        try:
            response = self._post_identify(audio_bytes, filename)
        except httpx.TimeoutException:
            logger.error("Auris request timed out after %.1fs", self._timeout)
            return _empty_result()
        except httpx.ConnectError:
            logger.error("Cannot connect to Auris at %s", self._base_url)
            return _empty_result()
        except httpx.HTTPStatusError as e:
            logger.error("Auris returned HTTP %d: %s", e.response.status_code, e.response.text[:500])
            return _empty_result()
        except Exception:
            logger.exception("Unexpected error calling Auris")
            return _empty_result()

        return self._extract_best_match(response)

    # ── Private helpers ─────────────────────────────────────────────────

    def _post_identify(self, audio_bytes: bytes, filename: str) -> dict:
        """POST multipart/form-data to Auris /identify.

        Raises:
            httpx.HTTPError: On transport or HTTP-level failures.
        """
        # Choose a fallback filename so Auris can sniff the format from the
        # extension. If the caller didn't provide one, default to .mp3 since
        # it's the most common format for music clips.
        send_filename = filename if filename else "audio.mp3"

        with httpx.Client(timeout=self._timeout) as client:
            resp = client.post(
                self._identify_url,
                files={"file": (send_filename, audio_bytes)},
            )
            resp.raise_for_status()
            return resp.json()

    def _extract_best_match(self, response: dict) -> dict:
        """Pick the highest-confidence match from an Auris response.

        Auris returns matches sorted by confidence descending, so the first
        element is the best.  We still scan explicitly for safety.
        """
        matches: list[dict] = response.get("matches", [])

        if not matches:
            logger.info("Auris returned 0 matches")
            return _empty_result()

        best = max(matches, key=lambda m: m.get("confidence", 0.0))
        track = best.get("track", {})

        confidence = float(best.get("confidence", 0.0))
        confidence = max(_MIN_CONFIDENCE, min(_MAX_CONFIDENCE, confidence))

        offset = best.get("offset_secs")
        match_offset = float(offset) if offset is not None else None

        result = {
            "title": track.get("title", ""),
            "artist": track.get("artist") or "",
            "confidence": confidence,
            "match_offset_secs": match_offset,
        }

        logger.info(
            "Best match: title=%r artist=%r confidence=%.2f offset=%.1fs",
            result["title"],
            result["artist"],
            result["confidence"],
            result["match_offset_secs"] if result["match_offset_secs"] is not None else -1,
        )

        return result


# ── Module-level helpers ─────────────────────────────────────────────────


def _empty_result() -> dict:
    """Return a no-match placeholder."""
    return {
        "title": "",
        "artist": "",
        "confidence": 0.0,
        "match_offset_secs": None,
    }
