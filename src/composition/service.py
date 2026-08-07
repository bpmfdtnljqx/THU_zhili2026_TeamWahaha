"""
composition/service.py

Placeholder AI music composition service.

This file is intentionally a stub. It returns a fixed response so the HTTP
layer, frontend, and integration tests can all be wired up today.

--- REPLACEMENT GUIDE (for teammate) ---

When the real composition model is ready:

1. Replace the body of ``Composer.generate()`` with your model inference.
2. The method signature is:
       def generate(self, prompt: str, duration: int = 30,
                    style: str = "", tempo: int = 0, key: str = "") -> dict
   - ``prompt`` is a natural-language description of desired music.
   - ``duration`` is target duration in seconds.
   - ``style``, ``tempo``, ``key`` are optional creative constraints.
3. Return a dict with these keys:
       {
           "audio_url": str | None,  # URL to generated audio file
           "duration": int,          # actual duration in seconds
       }
4. The API layer (backend/routers/composition.py) will wrap your dict
   into the standard HTTP response envelope automatically.
5. If generation fails for a known reason, raise a custom exception.
   The exception handler will convert it to a clean error response.
6. Do NOT modify the router — it stays thin on purpose.

Audio file storage:
   - The placeholder returns ``audio_url: null``.
   - When implemented, save generated audio to a static directory and
     return its URL (e.g. ``/static/generated/<uuid>.wav``).
   - OR return a base64-encoded data URI for small clips.
"""

from __future__ import annotations

import logging
import time
from typing import Optional

logger = logging.getLogger("lyra.composition")


class Composer:
    """Placeholder AI music composition engine.

    Currently returns an empty result. Replace the internals with your
    generative model when ready.
    """

    def generate(
        self,
        prompt: str,
        duration: int = 30,
        style: str = "",
        tempo: int = 0,
        key: str = "",
    ) -> dict:
        """Generate original music from a text prompt.

        Args:
            prompt: Natural-language description of desired music
                (e.g. "Create a relaxing piano melody").
            duration: Target duration in seconds.
            style: Optional musical style reference.
            tempo: Optional BPM hint (0 = model decides).
            key: Optional musical key hint ("" = model decides).

        Returns:
            dict with keys ``audio_url``, ``duration``.
        """
        # ── Placeholder — replace with real generation below ────────
        logger.info(
            "Composition requested (prompt=%r, duration=%ds, style=%r) — "
            "returning placeholder result.",
            prompt,
            duration,
            style,
        )

        _start = time.monotonic()

        # TODO: Replace with real generation logic. Example skeleton:
        #
        #   import your_model
        #   audio_bytes = your_model.generate(
        #       prompt=prompt,
        #       duration=duration,
        #       style=style or None,
        #       tempo=tempo or None,
        #       key=key or None,
        #   )
        #   url = _save_and_get_url(audio_bytes)
        #   return {
        #       "audio_url": url,
        #       "duration":  actual_duration,
        #   }
        #
        # For now, always return an empty placeholder.

        _elapsed = time.monotonic() - _start

        return {
            "audio_url": None,
            "duration": duration,
        }

    # ── Future extension points ────────────────────────────────────
    # Add helper methods here as your module grows:
    #   - _save_audio(audio_bytes) -> url
    #   - _validate_prompt(prompt) -> bool
    #   - _estimate_generation_time(duration, style) -> float
