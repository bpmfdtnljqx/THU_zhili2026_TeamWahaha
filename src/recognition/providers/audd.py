"""
AudD music recognition provider.

Sends uploaded audio to the AudD cloud recognition API.
No local music database or fingerprint database is required.
"""

from __future__ import annotations

import logging
import os
from typing import BinaryIO

import requests
from dotenv import load_dotenv

logger = logging.getLogger("lyra.recognition.audd")

_AUDD_API_URL = "https://api.audd.io/"
_REQUEST_TIMEOUT = 180

# Keep uploads reasonably small.
# The current test file is about 3 MB and works successfully.
_MAX_UPLOAD_BYTES = 9 * 1024 * 1024


class AudDProvider:
    """HTTP client for the AudD cloud recognition service."""

    def __init__(self, base_url: str | None = None):
        # Make sure .env is loaded even when this module is used directly.
        load_dotenv()

        self._api_token = os.getenv("AUDD_API_TOKEN")

        if not self._api_token:
            raise RuntimeError(
                "AUDD_API_TOKEN is not configured"
            )

        self._base_url = (
            base_url or os.getenv("AUDD_API_URL", _AUDD_API_URL)
        ).rstrip("/") + "/"

        logger.info(
            "AudD provider initialised: endpoint=%s",
            self._base_url,
        )

    def identify(
        self,
        audio_file: BinaryIO,
        filename: str = "",
    ) -> dict:
        """Identify a song from an uploaded audio file."""

        try:
            audio_file.seek(0)
            audio_bytes = audio_file.read()
        except Exception:
            logger.exception("Failed to read audio file")
            return _empty_result()

        if not audio_bytes:
            logger.warning("Empty audio file received")
            return _empty_result()

        original_size = len(audio_bytes)

        if original_size > _MAX_UPLOAD_BYTES:
            logger.warning(
                "Audio file too large: %.2f MiB; truncating to %.2f MiB",
                original_size / 1024 / 1024,
                _MAX_UPLOAD_BYTES / 1024 / 1024,
            )
            audio_bytes = audio_bytes[:_MAX_UPLOAD_BYTES]

        send_filename = filename or "audio.mp3"
        content_type = _guess_content_type(send_filename)

        logger.info(
            "Sending %.2f MiB to AudD: filename=%s content_type=%s",
            len(audio_bytes) / 1024 / 1024,
            send_filename,
            content_type,
        )

        try:
            response = requests.post(
                self._base_url,
                data={
                    "api_token": self._api_token,
                },
                files={
                    "file": (
                        send_filename,
                        audio_bytes,
                        content_type,
                    )
                },
                timeout=_REQUEST_TIMEOUT,
            )

            response.raise_for_status()

            payload = response.json()

        except requests.Timeout:
            logger.error("AudD request timed out")
            return _empty_result()

        except requests.RequestException as exc:
            logger.error("AudD request failed: %s", exc)
            return _empty_result()

        except ValueError:
            logger.error("AudD returned invalid JSON")
            return _empty_result()

        return self._extract_result(payload)

    def _extract_result(self, payload: dict) -> dict:
        """Convert AudD response into Lyra's stable recognition format."""

        if payload.get("status") != "success":
            error = payload.get("error", {})
            logger.error(
                "AudD recognition failed: code=%s message=%s",
                error.get("error_code"),
                error.get("error_message"),
            )
            return _empty_result()

        result = payload.get("result")

        if not result:
            logger.info("AudD returned no recognition result")
            return _empty_result()

        title = result.get("title") or ""
        artist = result.get("artist") or ""
        album = result.get("album") or ""
        release_date = result.get("release_date")
        song_link = result.get("song_link")

        # AudD does not provide a calibrated numeric confidence value.
        # 1.0 means that AudD successfully returned a match.
        confidence = 1.0

        match_offset_secs = _parse_timecode(
            result.get("timecode")
        )

        logger.info(
            "AudD match: title=%r artist=%r album=%r offset=%s",
            title,
            artist,
            album,
            match_offset_secs,
        )

        return {
            "title": title,
            "artist": artist,
            "album": album,
            "confidence": confidence,
            "match_offset_secs": match_offset_secs,
            "release_date": release_date,
            "song_link": song_link,
        }


def _guess_content_type(filename: str) -> str:
    lower = filename.lower()

    if lower.endswith(".wav"):
        return "audio/wav"
    if lower.endswith(".flac"):
        return "audio/flac"
    if lower.endswith(".ogg") or lower.endswith(".oga"):
        return "audio/ogg"
    if lower.endswith(".m4a"):
        return "audio/mp4"
    if lower.endswith(".aac"):
        return "audio/aac"
    if lower.endswith(".webm"):
        return "audio/webm"

    return "audio/mpeg"


def _parse_timecode(timecode: str | None) -> float | None:
    """Convert HH:MM:SS or MM:SS into seconds."""

    if not timecode:
        return None

    try:
        parts = [int(x) for x in timecode.split(":")]

        if len(parts) == 2:
            minutes, seconds = parts
            return float(minutes * 60 + seconds)

        if len(parts) == 3:
            hours, minutes, seconds = parts
            return float(hours * 3600 + minutes * 60 + seconds)

    except (ValueError, TypeError):
        pass

    logger.warning("Invalid AudD timecode: %r", timecode)
    return None


def _empty_result() -> dict:
    return {
        "title": "",
        "artist": "",
        "album": "",
        "confidence": 0.0,
        "match_offset_secs": None,
        "release_date": None,
        "song_link": None,
    }
