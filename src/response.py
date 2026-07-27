"""
response.py
------------
Response generator for the Lyra Agent.

Converts structured recommendation results into natural, empathetic
conversation text suitable for terminal display.

Design principles
------------------
- **Phase 2.1: template-based.**  Fast, predictable, no extra API call.
- **Designed for future LLM replacement.**  The ``generate()`` signature
  takes structured data (user_input, intent, recommendations) and returns
  a string.  An LLM-based generator would have the same interface — just
  swap the implementation.
- **Separation of concerns.**  The Reranker produces *data* (which songs
  + why); the Responder produces *presentation* (how to say it).
"""

from typing import Any, Dict, List


# ---------------------------------------------------------------------------
# Response templates
# ---------------------------------------------------------------------------
# These are deliberately simple.  They use intent fields (emotion, scene,
# listener_need) to craft an empathetic opening, then present the
# recommendations with their reasons.
#
# If you replace this module with an LLM-based generator in the future,
# keep the same ``generate(user_input, intent, recommendations) -> str``
# signature and the rest of the pipeline stays unchanged.
# ---------------------------------------------------------------------------


class Response:
    """Format recommendation results as natural conversation.

    Template-based for Phase 2.1.  The ``generate()`` interface is
    designed so that swapping in an LLM-based generator later requires
    no changes to ``agent.py`` or ``main.py``.
    """

    def generate(
        self,
        user_input: str,
        intent: Dict[str, Any],
        recommendations: List[Dict[str, Any]],
    ) -> str:
        """Build a display-ready response string.

        Parameters
        ----------
        user_input : str
            The user's original message.
        intent : dict
            Structured intent from the Planner (emotion, scene, …).
        recommendations : list[dict]
            Ranked recommendations from the Reranker.  Each dict has:
            title, artist, album, year, genre, reason, distance.

        Returns
        -------
        str
            Multi-line formatted string for terminal display.
        """
        lines: List[str] = []

        # ── Opening: empathetic acknowledgment ──
        opening = self._build_opening(intent)
        if opening:
            lines.append(opening)
            lines.append("")

        # ── Recommendations ──
        lines.append(self._build_divider())
        for i, rec in enumerate(recommendations, 1):
            lines.append(self._format_song(i, rec))
        lines.append(self._build_divider())

        # ── Closing ──
        closing = self._build_closing(intent)
        if closing:
            lines.append("")
            lines.append(closing)

        return "\n".join(lines)

    # ------------------------------------------------------------------
    # Template builders (private — replace these when moving to LLM)
    # ------------------------------------------------------------------

    @staticmethod
    def _build_opening(intent: Dict[str, Any]) -> str:
        """Craft an empathetic opening line from intent fields."""
        emotion = intent.get("emotion", [])
        scene = intent.get("scene", [])

        # Use the first recognised emotion/scene to personalise the opening
        if emotion:
            emotion_text = "、".join(emotion[:2])
            if scene:
                scene_text = "、".join(scene[:2])
                return f"🎵 听你说起{scene_text}时那种{emotion_text}的感觉，我想这些歌或许能懂你——"
            return f"🎵 感受到你此刻的{emotion_text}，这些歌或许正合你心意——"
        elif scene:
            scene_text = "、".join(scene[:2])
            return f"🎵 在{scene_text}的时刻，音乐是最好的陪伴——"
        else:
            return "🎵 根据你的心情，为你找到这些歌——"

    @staticmethod
    def _build_closing(intent: Dict[str, Any]) -> str:
        """Craft a warm closing thought."""
        need = intent.get("listener_need", [])
        if need:
            if "安慰" in need or "治愈" in need or "放松" in need or "安静" in need:
                return "💫 希望这些旋律能轻轻接住你此刻的心情。"
            if "鼓励" in need or "力量" in need or "激励" in need:
                return "💫 愿这些音符给你继续前行的力量。"
            return "💫 希望这些音乐能陪你度过这一刻。"
        return "💫 希望这些音乐能陪你度过这一刻。"

    @staticmethod
    def _build_divider() -> str:
        return "  " + "─" * 48

    @staticmethod
    def _format_song(index: int, rec: Dict[str, Any]) -> str:
        """Format a single song recommendation."""
        lines: List[str] = []
        lines.append(
            f"  {index}.  {rec.get('title', '?')}  —  {rec.get('artist', '?')}"
        )
        lines.append(
            f"       {rec.get('album', '?')} ({rec.get('year', '?')})"
            f"  |  {rec.get('genre', '?')}"
        )
        reason = rec.get("reason", "")
        if reason:
            lines.append(f"       💭 {reason}")
        lines.append("")
        return "\n".join(lines)
