"""
feedback.py
-----------
Simple feedback storage for Lyra music recommendations.

Stores user feedback in a local JSONL file (one JSON object per line)
for easy append-only writes and line-by-line reads.  No database required
— the file is human-readable and trivially parseable by pandas/polars
for future analysis.

Schema per entry::

    {
        "timestamp": "2026-08-02T12:34:56.789123+00:00",
        "user_query": "加班到凌晨，不想听太吵的歌",
        "intent": {...},
        "song_ids": ["0", "15", "42", "88", "120"],
        "song_titles": ["夜曲", "平凡之路", ...],
        "ratings": {"夜曲": "like", "平凡之路": "dislike", ...},
        "comment": ""
    }
"""

import json
import os
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

FEEDBACK_PATH = os.path.join(os.path.dirname(__file__), "..", "feedback.jsonl")


class FeedbackStore:
    """Append-only JSONL feedback storage.

    Usage::

        store = FeedbackStore()
        store.save(query, intent, recommendations, ratings)
        print(store.stats())
    """

    def __init__(self, path: str = FEEDBACK_PATH):
        self.path = path

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def save(
        self,
        user_query: str,
        intent: Dict[str, Any],
        recommendations: List[Dict[str, Any]],
        ratings: Dict[str, str],
        comment: Optional[str] = None,
    ) -> None:
        """Append one feedback entry to the JSONL file.

        Parameters
        ----------
        user_query : str
            The user's original natural-language input.
        intent : dict
            Structured intent from the Planner.
        recommendations : list[dict]
            Ranked recommendations from the Reranker.
        ratings : dict
            Mapping of song title → ``"like"`` | ``"dislike"`` | ``"neutral"``.
        comment : str, optional
            Optional free-text comment from the user.
        """
        entry = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "user_query": user_query,
            "intent": intent,
            "song_ids": [r.get("id", "") for r in recommendations],
            "song_titles": [r.get("title", "") for r in recommendations],
            "ratings": ratings,
            "comment": comment or "",
        }
        with open(self.path, "a", encoding="utf-8") as f:
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")

    def load_all(self) -> List[Dict[str, Any]]:
        """Load all feedback entries for analysis or personalization.

        Returns an empty list if the feedback file does not exist yet.
        """
        if not os.path.exists(self.path):
            return []
        entries: List[Dict[str, Any]] = []
        with open(self.path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line:
                    try:
                        entries.append(json.loads(line))
                    except json.JSONDecodeError:
                        continue
        return entries

    def stats(self) -> Dict[str, Any]:
        """Return summary statistics of stored feedback."""
        entries = self.load_all()
        total_sessions = len(entries)

        likes = 0
        dislikes = 0
        for entry in entries:
            for rating in entry.get("ratings", {}).values():
                if rating == "like":
                    likes += 1
                elif rating == "dislike":
                    dislikes += 1

        return {
            "total_sessions": total_sessions,
            "total_ratings": likes + dislikes,
            "likes": likes,
            "dislikes": dislikes,
        }
