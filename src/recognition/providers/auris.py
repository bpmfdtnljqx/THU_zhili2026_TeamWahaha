"""
recognition/providers/auris.py

HTTP client for the Auris audio recognition engine.

Large files are truncated to 8 MiB before being sent to Auris because
the Auris /identify endpoint currently has an 8 MiB multipart upload limit.
"""

from __future__ import annotations

import logging
import os
from typing import BinaryIO, Optional

import httpx

logger = logging.getLogger("lyra.recognition.auris")


# ── Configuration ────────────────────────────────────────────────────────

_DEFAULT_AURIS_URL = "http://127.0.0.1:8001"

_REQUEST_TIMEOUT_S = 30.0

_MIN_CONFIDENCE = 0.0
_MAX_CONFIDENCE = 1.0

# Auris IDENTIFY endpoint limit.
# 8 MiB = 8 * 1024 * 1024 bytes
_MAX_IDENTIFY_BYTES = 6 * 1024 * 1024


class AurisProvider:
    """Thin HTTP client for the Auris /identify endpoint."""

    def __init__(self, base_url: Optional[str] = None):
        self._base_url = (
            base_url
            or os.getenv("AURIS_API_URL", _DEFAULT_AURIS_URL)
        ).rstrip("/")

        self._identify_url = f"{self._base_url}/identify"
        self._timeout = _REQUEST_TIMEOUT_S

        logger.info(
            "Auris provider initialised — endpoint=%s, max_upload=%d bytes",
            self._identify_url,
            _MAX_IDENTIFY_BYTES,
        )

    # ── Public API ──────────────────────────────────────────────────────

    def identify(
        self,
        audio_file: BinaryIO,
        filename: str = "",
    ) -> dict:
        """Send audio to Auris and return the best match.

        Files larger than 8 MiB are truncated to 8 MiB before upload.
        """

        try:
            # Make sure we read from the beginning.
            try:
                audio_file.seek(0)
            except Exception:
                pass

            audio_bytes = audio_file.read()

        except Exception:
            logger.exception("Failed to read input audio file")
            return _empty_result()

        if not audio_bytes:
            logger.warning(
                "Empty audio file received — returning no-match"
            )
            return _empty_result()

        original_size = len(audio_bytes)

        # ── Apply Auris 8 MiB limit ────────────────────────────────────

        if original_size > _MAX_IDENTIFY_BYTES:
            logger.info(
                "Audio is too large for Auris: %d bytes (%.2f MiB). "
                "Truncating to %d bytes (8 MiB).",
                original_size,
                original_size / 1024 / 1024,
                _MAX_IDENTIFY_BYTES,
            )

            audio_bytes = audio_bytes[:_MAX_IDENTIFY_BYTES]

        else:
            logger.info(
                "Audio size: %d bytes (%.2f MiB), no truncation needed.",
                original_size,
                original_size / 1024 / 1024,
            )

        logger.info(
            "Sending %d bytes (%.2f MiB) to Auris (filename=%s)",
            len(audio_bytes),
            len(audio_bytes) / 1024 / 1024,
            filename or "<unknown>",
        )

        try:
            response = self._post_identify(
                audio_bytes,
                filename,
            )

        except httpx.TimeoutException:
            logger.error(
                "Auris request timed out after %.1fs",
                self._timeout,
            )
            return _empty_result()

        except httpx.ConnectError:
            logger.error(
                "Cannot connect to Auris at %s",
                self._base_url,
            )
            return _empty_result()

        except httpx.HTTPStatusError as e:
            logger.error(
                "Auris returned HTTP %d: %s",
                e.response.status_code,
                e.response.text[:1000],
            )
            return _empty_result()

        except Exception:
            logger.exception(
                "Unexpected error calling Auris"
            )
            return _empty_result()

        return self._extract_best_match(response)

    # ── HTTP ────────────────────────────────────────────────────────────

    def _post_identify(
        self,
        audio_bytes: bytes,
        filename: str,
    ) -> dict:
        """POST multipart/form-data to Auris /identify."""

        # Keep the original extension because Auris uses it to determine
        # the audio format.
        send_filename = filename or "audio.mp3"

        # If the filename somehow has no extension, use mp3.
        if "." not in send_filename:
            send_filename = f"{send_filename}.mp3"

        # Determine MIME type from extension.
        lower_name = send_filename.lower()

        if lower_name.endswith(".wav"):
            content_type = "audio/wav"
        elif lower_name.endswith(".flac"):
            content_type = "audio/flac"
        elif lower_name.endswith(".ogg"):
            content_type = "audio/ogg"
        elif lower_name.endswith(".m4a"):
            content_type = "audio/mp4"
        elif lower_name.endswith(".aac"):
            content_type = "audio/aac"
        elif lower_name.endswith(".webm"):
            content_type = "audio/webm"
        else:
            content_type = "audio/mpeg"

        logger.debug(
            "Uploading to Auris: filename=%s content_type=%s size=%d",
            send_filename,
            content_type,
            len(audio_bytes),
        )

        # IMPORTANT:
        # Let httpx construct the multipart/form-data boundary itself.
        # Do NOT manually set Content-Type: multipart/form-data.
        with httpx.Client(
            timeout=self._timeout,
            follow_redirects=True,
        ) as client:

            response = client.post(
                self._identify_url,
                files={
                    "file": (
                        send_filename,
                        audio_bytes,
                        content_type,
                    )
                },
            )

            if response.status_code >= 400:
                logger.error(
                    "Auris HTTP %d. Sent %d bytes as %s (%s). "
                    "Response: %s",
                    response.status_code,
                    len(audio_bytes),
                    send_filename,
                    content_type,
                    response.text[:1000],
                )

            response.raise_for_status()

            return response.json()

    # ── Response parsing ────────────────────────────────────────────────

    def _extract_best_match(
        self,
        response: dict,
    ) -> dict:
        """Pick the highest-confidence match."""

        matches: list[dict] = response.get("matches", [])

        if not matches:
            logger.info("Auris returned 0 matches")
            return _empty_result()

        best = max(
            matches,
            key=lambda m: m.get("confidence", 0.0),
        )

        track = best.get("track", {})

        confidence = float(
            best.get("confidence", 0.0)
        )

        confidence = max(
            _MIN_CONFIDENCE,
            min(_MAX_CONFIDENCE, confidence),
        )

        offset = best.get("offset_secs")

        match_offset = (
            float(offset)
            if offset is not None
            else None
        )

        result = {
            "title": track.get("title", ""),
            "artist": track.get("artist") or "",
            "confidence": confidence,
            "match_offset_secs": match_offset,
        }

        logger.info(
            "Best match: title=%r artist=%r "
            "confidence=%.2f offset=%.1fs",
            result["title"],
            result["artist"],
            result["confidence"],
            (
                result["match_offset_secs"]
                if result["match_offset_secs"] is not None
                else -1
            ),
        )

        return result


# ── Helpers ──────────────────────────────────────────────────────────────

def _empty_result() -> dict:
    """Return a no-match result."""

    return {
        "title": "",
        "artist": "",
        "confidence": 0.0,
        "match_offset_secs": None,
    }
