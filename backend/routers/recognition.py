"""
Recognition router.

POST /recognition — delegates to src.recognition.Recognizer.

Accepts an uploaded audio file and returns a recognition result.
Currently the recognizer is a placeholder; when the teammate's model
is ready, only ``service.py`` needs to change — this router stays the same.
"""

import sys
import os

_src_dir = os.path.join(os.path.dirname(__file__), "..", "..", "src")
if _src_dir not in sys.path:
    sys.path.insert(0, _src_dir)

from fastapi import APIRouter, File, UploadFile

from backend.exception_handlers import LyraException
from backend.models import RecognitionData, RecognitionResponse

router = APIRouter(tags=["recognition"])

# Allowed audio MIME types and extensions (extensible by teammate).
_ALLOWED_CONTENT_TYPES = frozenset({
    "audio/mpeg",       # .mp3
    "audio/wav",        # .wav
    "audio/wave",       # .wav (alternative)
    "audio/x-wav",      # .wav (legacy)
    "audio/flac",       # .flac
    "audio/ogg",        # .ogg / .oga
    "audio/mp4",        # .m4a
    "audio/x-m4a",      # .m4a (alternative)
    "audio/webm",       # .webm
})

_ALLOWED_EXTENSIONS = frozenset({
    ".mp3", ".wav", ".flac", ".ogg", ".oga", ".m4a", ".webm",
})


def _validate_audio_file(file: UploadFile) -> None:
    """Reject unsupported formats early with a clear error."""
    # Check MIME type if provided.
    if file.content_type and file.content_type not in _ALLOWED_CONTENT_TYPES:
        raise LyraException(
            "Unsupported audio format",
            detail=(
                f"Content-Type '{file.content_type}' is not supported. "
                f"Allowed: mp3, wav, flac, ogg, m4a, webm."
            ),
        )

    # Double-check by extension.
    if file.filename:
        _, ext = os.path.splitext(file.filename)
        if ext.lower() not in _ALLOWED_EXTENSIONS:
            raise LyraException(
                "Unsupported audio format",
                detail=(
                    f"File extension '{ext}' is not supported. "
                    f"Allowed: {', '.join(sorted(_ALLOWED_EXTENSIONS))}."
                ),
            )


@router.post("/recognition", response_model=RecognitionResponse)
async def recognize(file: UploadFile = File(...)):
    """Identify a song from an uploaded audio file.

    Accepts mp3, wav, flac, ogg, m4a, webm.

    **Placeholder:** currently returns an empty result. The real
    recognition model will be integrated by replacing
    ``src/recognition/service.py``.
    """
    # ── Validate input ──────────────────────────────────────────────
    _validate_audio_file(file)

    # ── Import the recognizer ───────────────────────────────────────
    try:
        from recognition import Recognizer
    except ImportError as e:
        raise LyraException(
            "Recognition module not available",
            detail=f"Could not import src.recognition: {e}",
        )

    # ── Delegate to service layer ───────────────────────────────────
    try:
        recognizer = Recognizer()
        result = recognizer.recognize(file.file, filename=file.filename or "")
    except Exception as e:
        raise LyraException(
            "Recognition failed",
            detail=str(e),
        )

    # ── Build response ──────────────────────────────────────────────
    return RecognitionResponse(
        data=RecognitionData(**result),
        message="Recognition service placeholder"
        if not result.get("title")
        else "Recognition completed",
    )
