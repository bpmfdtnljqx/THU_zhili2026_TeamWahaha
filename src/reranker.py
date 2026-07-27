"""
reranker.py
-----------
DeepSeekReranker: sends Top-10 vector candidates + user query to the
DeepSeek API and returns a re-ranked Top-5 with personalized reasons.

Falls back gracefully to vector Top-5 if the API or JSON parsing fails.

Optimizations applied:
- Defensive candidate slicing (max 10) with before/after logging
- API parameter tuning (temperature=0, max_tokens=200, top_p=0.9, timeout=20)
- Prompt compression (shorter field names, reduced whitespace)
- Structured timing breakdown (prompt build → API call → parse)
- LRU cache with TTL via RerankerCache
- Better error handling with specific JSON parse recovery
"""

import json
import os
import re
import time
from typing import Any, Dict, List, Optional

import requests
from dotenv import load_dotenv

from reranker_cache import RerankerCache

load_dotenv()

SONGS_PATH = os.path.join(os.path.dirname(__file__), "..", "songs.json")

# ---------------------------------------------------------------------------
# Configuration (move these to config.py/env later if needed)
# ---------------------------------------------------------------------------

DEFAULT_CANDIDATE_LIMIT = 10   # hard-cap on candidates sent to the API
API_TEMPERATURE = 0.0           # no sampling — deterministic & faster
API_MAX_TOKENS = 200            # limit output length
API_TOP_P = 0.9
API_TIMEOUT = 20                # seconds (down from 30)
CACHE_ENABLED = os.getenv("LYRA_CACHE_ENABLED", "1") == "1"
CACHE_TTL = int(os.getenv("LYRA_CACHE_TTL", "1800"))    # 30 min
CACHE_MAX_SIZE = int(os.getenv("LYRA_CACHE_MAX_SIZE", "1000"))

# ---------------------------------------------------------------------------
# Prompts (compressed — shorter field labels, less whitespace)
# ---------------------------------------------------------------------------

SYSTEM_PROMPT = (
    "You are a professional music recommendation expert. "
    "Pick the 5 best songs from candidates. "
    "Priority: emotion > scene > theme. "
    "Return ONLY valid JSON, no extra text."
)

USER_TEMPLATE = (
    "{user_query}\n\n"
    "Candidates ({total}):\n"
    "{candidates}\n\n"
    'JSON: {{"selected":[{{"index":0,"reason":"≤50 chars why this fits"}}]}}'
)


def _load_songs() -> Dict[str, Any]:
    """
    Load songs.json and build a lookup dictionary.

    songs.json is a list. ChromaDB IDs are str(index) matching list positions.
    We return {str_position: song_dict} so lookups by ChromaDB ID work in O(1).
    """
    with open(SONGS_PATH, "r", encoding="utf-8") as f:
        songs_list = json.load(f)
    return {str(i): song for i, song in enumerate(songs_list)}


# ---------------------------------------------------------------------------
# DeepSeekReranker
# ---------------------------------------------------------------------------


class DeepSeekReranker:
    """Re-rank candidate songs via the DeepSeek API with personalised reasons."""

    def __init__(self):
        self.api_key = os.getenv("DEEPSEEK_API_KEY", "")
        self.base_url = os.getenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com/v1")
        self.model = os.getenv("DEEPSEEK_MODEL", "deepseek-chat")

        self.songs = _load_songs()

        # Init cache
        self._cache = RerankerCache(
            max_size=CACHE_MAX_SIZE,
            ttl_seconds=CACHE_TTL,
        ) if CACHE_ENABLED else None

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def rerank(self, user_query: str, candidates: List[Any]) -> List[Dict]:
        """
        Re-rank *candidates* (up to {DEFAULT_CANDIDATE_LIMIT}) to a Top-5 with reasons.

        Returns list of dicts: title, artist, album, year, genre, reason, distance.

        candidates can be any format (dicts, strings, lists, nested lists) —
        they are normalized via _normalize_candidate before processing.
        """
        t_total = time.time()

        # ---- Defensive slicing & normalize ----
        original_count = len(candidates)
        candidates_raw = list(candidates)[:DEFAULT_CANDIDATE_LIMIT]

        # Normalize all candidates to List[Dict] early, so everything downstream
        # works with a consistent format.
        candidates: List[Dict] = []
        for idx, item in enumerate(candidates_raw):
            print(f"  [rerank] raw[{idx}] type={type(item).__name__}  "
                  f"sample={str(item)[:120]}")
            norm = self._normalize_candidate(item)
            if norm is not None:
                candidates.append(norm)
            else:
                print(f"  [rerank] raw[{idx}] → dropped (unparseable)")

        sliced_count = len(candidates)
        candidate_ids = [str(c.get("id", f"unknown_{i}")) for i, c in enumerate(candidates)]

        print(
            f"[Reranker] Start reranking | "
            f"received={original_count} → normalized={sliced_count}"
        )

        # ---- Cache lookup ----
        if self._cache is not None:
            cache_key = RerankerCache.make_key(user_query, candidate_ids)
            cached = self._cache.get(cache_key)
            if cached is not None:
                elapsed = time.time() - t_total
                print(
                    f"[Reranker] CACHE HIT → returned in {elapsed:.2f}s | "
                    f"stats={self._cache.stats}"
                )
                return cached

        # ---- Build prompt ----
        t_prompt = time.time()
        candidates_text = self._build_candidates_text(candidates)
        user_message = USER_TEMPLATE.format(
            user_query=user_query,
            total=sliced_count,
            candidates=candidates_text,
        )
        prompt_ms = (time.time() - t_prompt) * 1000

        # ---- API call ----
        try:
            raw_response, api_ms = self._call_api(user_message)
        except Exception as e:
            print(f"[Reranker] API error: {e}")
            print(f"[Reranker] Falling back to vector Top-5.")
            elapsed = time.time() - t_total
            print(f"[Reranker] Completed in {elapsed:.2f}s (fallback)")
            return self._fallback(user_query, candidates[:5])

        # ---- Parse response ----
        t_parse = time.time()
        try:
            output = self._parse_response(raw_response, candidates)
            parse_ms = (time.time() - t_parse) * 1000
        except Exception as e:
            print(f"[Reranker] Parse error: {e}")
            elapsed = time.time() - t_total
            print(f"[Reranker] Completed in {elapsed:.2f}s (fallback)")
            return self._fallback(user_query, candidates[:5])

        # ---- Summary ----
        elapsed = time.time() - t_total
        print(
            f"[Reranker] Completed in {elapsed:.2f}s | "
            f"prompt={prompt_ms:.0f}ms api={api_ms:.0f}ms parse={parse_ms:.0f}ms"
        )

        # ---- Cache store ----
        if self._cache is not None:
            cache_key = RerankerCache.make_key(user_query, candidate_ids)
            self._cache.set(cache_key, output)

        return output

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _normalize_candidate(self, item: Any) -> Optional[Dict]:
        """
        Convert ANY candidate format to a standard song dict.

        Tries to extract the song ID, then enriches with self.songs data.

        Handles:
          - Dict with 'id'  (retriever output)
          - Dict with title/artist but no id
          - Plain string ID
          - Single-element list [song_id]
          - Multi-element list [song_id, title, ...]
          - Nested lists (recurses into first element)

        Returns None for completely unparseable data.
        """
        # ---- DICT: standard retriever output ----
        if isinstance(item, dict):
            song_id = str(item.get("id", ""))
            if song_id:
                song_data = self.songs.get(song_id)
                if song_data:
                    # Merge: candidate's own fields win, song_data fills gaps
                    merged = dict(song_data)
                    merged.update(item)
                    print(f"  [normalize] dict+id   → id={song_id}  title={merged.get('title','')}")
                    return merged
                # ID exists but not in songs.json — use candidate as-is
                print(f"  [normalize] dict+id   → id={song_id}  (NOT in songs.json, using raw)")
                return item
            # Dict without id — try title/artist from songs or use raw
            title = item.get("title", "")
            artist = item.get("artist", "")
            print(f"  [normalize] dict-no-id → title='{title}' artist='{artist}' (using raw)")
            return item

        # ---- STRING: plain song ID ----
        if isinstance(item, str):
            song_data = self.songs.get(item)
            if song_data:
                result = dict(song_data)
                result["id"] = item
                print(f"  [normalize] str       → id={item}  title={result.get('title','')}")
                return result
            print(f"  [normalize] str       → id={item}  (NOT in songs.json)")
            return {"id": item, "title": item, "artist": "unknown"}

        # ---- LIST: could be [id], [id, title, artist, ...], or nested ----
        if isinstance(item, list):
            if len(item) == 0:
                print(f"  [normalize] list      → EMPTY list, skipping")
                return None

            # If first element is a list itself, recurse into it
            if isinstance(item[0], list):
                print(f"  [normalize] list      → nested list (len={len(item)}), recursing into [0]")
                return self._normalize_candidate(item[0])

            # First element is a string — treat as song ID
            if isinstance(item[0], str):
                song_id = str(item[0])
                song_data = self.songs.get(song_id)
                if song_data:
                    result = dict(song_data)
                    result["id"] = song_id
                    # If list has more elements, use them positionally
                    if len(item) >= 2:
                        result["title"] = str(item[1])
                    if len(item) >= 3:
                        result["artist"] = str(item[2])
                    print(f"  [normalize] list[str] → id={song_id}  title={result.get('title','')} (len={len(item)})")
                    return result
                # Not in songs — build minimal dict
                result = {"id": song_id, "title": song_id, "artist": "unknown"}
                if len(item) >= 2:
                    result["title"] = str(item[1])
                if len(item) >= 3:
                    result["artist"] = str(item[2])
                print(f"  [normalize] list[str] → id={song_id}  (NOT in songs, using list fields)")
                return result

            # First element is something else (dict, int, etc.)
            print(f"  [normalize] list      → unexpected inner type={type(item[0]).__name__}, trying [0]")
            return self._normalize_candidate(item[0])

        # ---- UNKNOWN TYPE ----
        print(f"  [normalize] UNKNOWN   → type={type(item).__name__}  value={str(item)[:80]}")
        return None

    def _build_candidates_text(self, candidates: List[Any]) -> str:
        """
        Build compact candidate text for the prompt.

        Defensive: normalizes every candidate via _normalize_candidate, then
        builds a compact one-line-per-song representation using songs.json for
        rich metadata (core_theme, emotion, suitable_scene).
        """
        candidates = list(candidates)[:DEFAULT_CANDIDATE_LIMIT]

        lines: List[str] = []
        for i, item in enumerate(candidates):
            # Debug: show what we received
            print(f"  [build] candidate[{i}] type={type(item).__name__}  "
                  f"raw_sample={str(item)[:120]}")

            # Normalize to a standard dict
            normalized = self._normalize_candidate(item)
            if normalized is None:
                print(f"  [build] candidate[{i}] → SKIPPED (normalize returned None)")
                continue

            # Gather fields — prefer normalized (enriched from songs.json),
            # fall back to the candidate dict for title/artist
            title = normalized.get("title", "") or item.get("title", "") if isinstance(item, dict) else normalized.get("title", "")
            artist = normalized.get("artist", "") or item.get("artist", "") if isinstance(item, dict) else normalized.get("artist", "")

            # Rich fields from songs.json (via normalizer)
            theme = _join_truncate(normalized.get("core_theme", []), max_len=40)
            emotion = _join_truncate(normalized.get("emotion", []), max_len=40)
            scene = _join_truncate(normalized.get("suitable_scene", []), max_len=40)

            if not title:
                print(f"  [build] candidate[{i}] → SKIPPED (no title)")
                continue

            lines.append(
                f"{i + 1}.{title}-{artist}"
                f" | {theme}"
                f" | {emotion}"
                f" | {scene}"
            )

        result = "\n".join(lines)
        print(f"  [build] produced {len(lines)} lines from {len(candidates)} candidates")
        return result

    def _call_api(self, user_message: str) -> tuple:
        """Call DeepSeek API. Returns (raw_text, latency_ms)."""
        t0 = time.time()

        payload = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": user_message},
            ],
            "temperature": API_TEMPERATURE,
            "max_tokens": API_MAX_TOKENS,
            "top_p": API_TOP_P,
        }

        response = requests.post(
            f"{self.base_url}/chat/completions",
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
            },
            json=payload,
            timeout=API_TIMEOUT,
        )
        response.raise_for_status()

        content = response.json()["choices"][0]["message"]["content"]
        api_ms = (time.time() - t0) * 1000
        return content, api_ms

    def _parse_response(
        self, raw: str, candidates: List[Dict]
    ) -> List[Dict]:
        """Parse the API response. Attempts JSON repair if needed."""
        # Try clean JSON first
        selected = None
        try:
            result = json.loads(raw)
            selected = result.get("selected", [])
        except json.JSONDecodeError:
            # Attempt to extract JSON block from the response
            match = re.search(r"\[.*?\]", raw, re.DOTALL)
            if match:
                try:
                    result = json.loads(match.group(0))
                    if isinstance(result, list):
                        selected = result  # direct list of objects
                        # Normalize: wrap in expected structure
                        selected = [
                            {"index": item.get("index", i),
                             "reason": item.get("reason", "")}
                            for i, item in enumerate(selected)
                        ]
                except json.JSONDecodeError:
                    pass

        if not selected:
            raise ValueError(f"Could not extract 'selected' from response: {raw[:200]}")

        output: List[Dict] = []
        for item in selected[:5]:
            idx = int(item.get("index", 0))
            if idx < len(candidates):
                c = candidates[idx]
                output.append(self._format_result(c, item.get("reason", "")))

        return output

    def _fallback(
        self, user_query: str, candidates: List[Dict]
    ) -> List[Dict]:
        """Return a simple Top-5 fallback without API reasoning."""
        output: List[Dict] = []
        for c in candidates[:5]:
            # c is already normalized (enriched from songs.json)
            title = c.get("title", "")
            artist = c.get("artist", "unknown")
            theme = "、".join(c.get("core_theme", []))
            reason = f"'{theme}' theme may match '{user_query}'" if theme else f"May match '{user_query}'"
            output.append(self._format_result(c, reason))
        return output

    @staticmethod
    def _format_result(candidate: Dict, reason: str) -> Dict:
        return {
            "title": candidate.get("title", ""),
            "artist": candidate.get("artist", ""),
            "album": candidate.get("album", ""),
            "year": candidate.get("year", ""),
            "genre": candidate.get("genre", ""),
            "reason": reason,
            "distance": candidate.get("distance", ""),
        }

    @property
    def cache_stats(self) -> Optional[Dict]:
        """Expose cache stats for monitoring."""
        return self._cache.stats if self._cache else None


# ---------------------------------------------------------------------------
# Module helpers
# ---------------------------------------------------------------------------


def _join_truncate(items: List[str], max_len: int = 40) -> str:
    """Join items with '、' and truncate to max_len characters."""
    text = "、".join(str(i) for i in items)
    if len(text) > max_len:
        text = text[: max_len - 1] + "…"
    return text
