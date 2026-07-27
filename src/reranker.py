"""
reranker.py
-----------
DeepSeekReranker: sends Top-15 vector candidates + user query to the
DeepSeek API and returns a re-ranked Top-5 with personalized reasons.

Falls back gracefully to vector Top-5 if the API or JSON parsing fails.

Optimizations applied:
- Defensive candidate slicing (max 15) with before/after logging
- API parameter tuning (temperature=0, max_tokens=600, top_p=0.9, timeout=20)
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
# Configuration
# ---------------------------------------------------------------------------

DEFAULT_CANDIDATE_LIMIT = 15
API_TEMPERATURE = 0.0
API_MAX_TOKENS = 600
API_TOP_P = 0.9
API_TIMEOUT = 20
API_MAX_RETRIES = 2
VERBOSE = os.getenv("LYRA_VERBOSE", "0") == "1"

CACHE_ENABLED = os.getenv("LYRA_CACHE_ENABLED", "1") == "1"
CACHE_TTL = int(os.getenv("LYRA_CACHE_TTL", "1800"))
CACHE_MAX_SIZE = int(os.getenv("LYRA_CACHE_MAX_SIZE", "1000"))

# Fallback model names to try if the primary model fails
FALLBACK_MODELS = ["deepseek-chat", "deepseek-reasoner"]

# ---------------------------------------------------------------------------
# Prompts (polished — longer, more expressive reasons)
# ---------------------------------------------------------------------------

SYSTEM_PROMPT = (
    "你是音乐推荐专家。基于用户查询和候选歌曲，输出Top5排序及理由。"
    "优先级: 情感匹配 > 场景匹配 > 主题匹配。"
    "推荐理由要优美、有文采、能打动人心，20-40字，像唱片介绍那样写。"
    "只输出JSON数组，不要其他文字。"
)

USER_TEMPLATE = (
    "{user_query}\n\n"
    "候选歌曲 ({total}首):\n"
    "{candidates}\n\n"
    '输出格式(JSON数组,5个对象):\n'
    '[{{"title":"歌名","artist":"歌手","reason":"推荐理由(优美流畅,20-40字)"}}]'
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

    def __init__(self, verbose: bool = None):
        self.api_key = os.getenv("DEEPSEEK_API_KEY", "")
        self.model = os.getenv("DEEPSEEK_MODEL", "deepseek-chat")

        # Normalize base_url — ensure it ends with /v1
        raw_base = os.getenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com")
        self.base_url = raw_base.rstrip("/")
        if not self.base_url.endswith("/v1"):
            # Auto-append /v1 if missing (common misconfiguration)
            self.base_url += "/v1"

        self.songs = _load_songs()

        # Verbose logging — defaults to LYRA_VERBOSE env var
        self.verbose = verbose if verbose is not None else VERBOSE

        # Init cache
        self._cache = RerankerCache(
            max_size=CACHE_MAX_SIZE,
            ttl_seconds=CACHE_TTL,
        ) if CACHE_ENABLED else None

        self._log(
            f"[Reranker] Init | model={self.model} | "
            f"base_url={self.base_url} | "
            f"api_key={'***' + self.api_key[-6:] if self.api_key else 'MISSING'}"
        )

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _log(self, msg: str) -> None:
        """Print debug message only when verbose mode is enabled."""
        if self.verbose:
            print(msg)

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
            self._log(f"  [rerank] raw[{idx}] type={type(item).__name__}  "
                      f"sample={str(item)[:120]}")
            norm = self._normalize_candidate(item)
            if norm is not None:
                candidates.append(norm)
            else:
                self._log(f"  [rerank] raw[{idx}] → dropped (unparseable)")

        sliced_count = len(candidates)
        candidate_ids = [str(c.get("id", f"unknown_{i}")) for i, c in enumerate(candidates)]

        self._log(
            f"[Reranker] Start reranking | "
            f"received={original_count} → normalized={sliced_count}"
        )

        # ---- Cache lookup ----
        if self._cache is not None:
            cache_key = RerankerCache.make_key(user_query, candidate_ids)
            cached = self._cache.get(cache_key)
            if cached is not None:
                elapsed = time.time() - t_total
                self._log(
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
            self._log(f"[Reranker] API error: {e}")
            self._log(f"[Reranker] Falling back to vector Top-5.")
            elapsed = time.time() - t_total
            self._log(f"[Reranker] Completed in {elapsed:.2f}s (fallback)")
            return self._fallback(user_query, candidates[:5])

        # ---- Parse response ----
        t_parse = time.time()
        try:
            output = self._parse_response(raw_response, candidates)
            parse_ms = (time.time() - t_parse) * 1000
        except Exception as e:
            self._log(f"[Reranker] Parse error: {e}")
            elapsed = time.time() - t_total
            self._log(f"[Reranker] Completed in {elapsed:.2f}s (fallback)")
            return self._fallback(user_query, candidates[:5])

        # ---- Summary ----
        elapsed = time.time() - t_total
        self._log(
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
                    self._log(f"  [normalize] dict+id   → id={song_id}  title={merged.get('title','')}")
                    return merged
                # ID exists but not in songs.json — use candidate as-is
                self._log(f"  [normalize] dict+id   → id={song_id}  (NOT in songs.json, using raw)")
                return item
            # Dict without id — try title/artist from songs or use raw
            title = item.get("title", "")
            artist = item.get("artist", "")
            self._log(f"  [normalize] dict-no-id → title='{title}' artist='{artist}' (using raw)")
            return item

        # ---- STRING: plain song ID ----
        if isinstance(item, str):
            song_data = self.songs.get(item)
            if song_data:
                result = dict(song_data)
                result["id"] = item
                self._log(f"  [normalize] str       → id={item}  title={result.get('title','')}")
                return result
            self._log(f"  [normalize] str       → id={item}  (NOT in songs.json)")
            return {"id": item, "title": item, "artist": "unknown"}

        # ---- LIST: could be [id], [id, title, artist, ...], or nested ----
        if isinstance(item, list):
            if len(item) == 0:
                self._log(f"  [normalize] list      → EMPTY list, skipping")
                return None

            # If first element is a list itself, recurse into it
            if isinstance(item[0], list):
                self._log(f"  [normalize] list      → nested list (len={len(item)}), recursing into [0]")
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
                    self._log(f"  [normalize] list[str] → id={song_id}  title={result.get('title','')} (len={len(item)})")
                    return result
                # Not in songs — build minimal dict
                result = {"id": song_id, "title": song_id, "artist": "unknown"}
                if len(item) >= 2:
                    result["title"] = str(item[1])
                if len(item) >= 3:
                    result["artist"] = str(item[2])
                self._log(f"  [normalize] list[str] → id={song_id}  (NOT in songs, using list fields)")
                return result

            # First element is something else (dict, int, etc.)
            self._log(f"  [normalize] list      → unexpected inner type={type(item[0]).__name__}, trying [0]")
            return self._normalize_candidate(item[0])

        # ---- UNKNOWN TYPE ----
        self._log(f"  [normalize] UNKNOWN   → type={type(item).__name__}  value={str(item)[:80]}")
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
            self._log(f"  [build] candidate[{i}] type={type(item).__name__}  "
                      f"raw_sample={str(item)[:120]}")

            # Normalize to a standard dict
            normalized = self._normalize_candidate(item)
            if normalized is None:
                self._log(f"  [build] candidate[{i}] → SKIPPED (normalize returned None)")
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
                self._log(f"  [build] candidate[{i}] → SKIPPED (no title)")
                continue

            lines.append(
                f"{i + 1}.{title}-{artist}"
                f" | {theme}"
                f" | {emotion}"
                f" | {scene}"
            )

        result = "\n".join(lines)
        self._log(f"  [build] produced {len(lines)} lines from {len(candidates)} candidates")
        return result

    def _call_api(self, user_message: str) -> tuple:
        """Call DeepSeek API with retries, fallback models, and full diagnostics.

        Returns (raw_text, latency_ms).

        Diagnostics logged for every attempt:
          - HTTP status code
          - Response headers (key ones)
          - Response body (truncated)
          - Timing per phase
        """
        t0 = time.time()

        # ── Build payload ──
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

        url = f"{self.base_url}/chat/completions"

        # Log request (sanitized)
        prompt_preview = user_message[:120].replace("\n", "\\n")
        self._log(
            f"[API] → Request | url={url} | model={payload['model']} | "
            f"max_tokens={payload['max_tokens']} | temp={payload['temperature']} | "
            f"prompt_preview=\"{prompt_preview}...\""
        )

        models_to_try = [self.model] + [
            m for m in FALLBACK_MODELS if m != self.model
        ]

        last_error = None

        for attempt, model_name in enumerate(models_to_try):
            payload["model"] = model_name

            for retry in range(API_MAX_RETRIES + 1):
                try:
                    t_call = time.time()
                    response = requests.post(
                        url,
                        headers={
                            "Authorization": f"Bearer {self.api_key}",
                            "Content-Type": "application/json",
                        },
                        json=payload,
                        timeout=API_TIMEOUT,
                    )
                    call_ms = (time.time() - t_call) * 1000

                    status = response.status_code

                    # ── Log full response diagnostics ──
                    content_type = response.headers.get("Content-Type", "unknown")
                    body = response.text

                    self._log(
                        f"[API] ← Response | status={status} | "
                        f"content_type={content_type} | "
                        f"body_len={len(body)} | call_ms={call_ms:.0f}"
                    )

                    if status == 200:
                        # Check that it's actually JSON, not an HTML page
                        if not body.strip():
                            last_error = f"HTTP 200 but EMPTY body (model={model_name})"
                            self._log(f"[API] ⚠ {last_error}")
                            break  # try next model

                        if "text/html" in content_type:
                            last_error = (
                                f"HTTP 200 but got HTML (wrong endpoint? "
                                f"Tried {url}). Check DEEPSEEK_BASE_URL."
                            )
                            self._log(f"[API] ⚠ {last_error}")
                            # Truncate HTML body for debugging
                            self._log(f"[API] HTML body: {body[:500]}")
                            break  # endpoint issue — don't retry same URL

                        try:
                            data = response.json()
                        except json.JSONDecodeError as je:
                            last_error = (
                                f"HTTP 200 but body is not JSON: {je}. "
                                f"Body preview: {body[:300]}"
                            )
                            self._log(f"[API] ⚠ {last_error}")
                            break  # try next model

                        # Extract content
                        choices = data.get("choices", [])
                        if not choices:
                            last_error = (
                                f"HTTP 200 but no 'choices' in response. "
                                f"Keys: {list(data.keys())}. "
                                f"Body: {body[:500]}"
                            )
                            self._log(f"[API] ⚠ {last_error}")
                            break

                        content = choices[0].get("message", {}).get("content", "")
                        if not content:
                            # Check for finish_reason — might indicate truncation
                            finish_reason = choices[0].get(
                                "finish_reason", "unknown"
                            )
                            last_error = (
                                f"HTTP 200 but empty content. "
                                f"finish_reason={finish_reason}, "
                                f"body_preview={body[:300]}"
                            )
                            self._log(f"[API] ⚠ {last_error}")
                            break

                        # ── Success! ──
                        api_ms = (time.time() - t0) * 1000
                        self._log(
                            f"[API] ✅ Success | model={model_name} | "
                            f"attempt={attempt + 1}.{retry + 1} | "
                            f"content_len={len(content)} | "
                            f"total_ms={api_ms:.0f}"
                        )
                        return content, api_ms

                    elif status == 401:
                        last_error = (
                            f"HTTP 401 Unauthorized — API key is invalid or expired. "
                            f"Key ends with: ...{self.api_key[-6:] if self.api_key else 'N/A'}"
                        )
                        self._log(f"[API] ❌ {last_error}")
                        # Don't retry on auth errors
                        raise RuntimeError(last_error)

                    elif status == 403:
                        last_error = (
                            f"HTTP 403 Forbidden — API key lacks permission "
                            f"or account is restricted."
                        )
                        self._log(f"[API] ❌ {last_error}")
                        raise RuntimeError(last_error)

                    elif status == 429:
                        retry_after = response.headers.get("Retry-After", "unknown")
                        last_error = (
                            f"HTTP 429 Rate Limited | "
                            f"Retry-After={retry_after}s"
                        )
                        self._log(f"[API] ⚠ {last_error}")
                        if retry < API_MAX_RETRIES:
                            wait = int(retry_after) if retry_after.isdigit() else (2 ** retry)
                            self._log(f"[API] Waiting {wait}s before retry...")
                            time.sleep(wait)
                            continue
                        break  # try next model

                    elif status in (500, 502, 503, 504):
                        last_error = f"HTTP {status} Server Error"
                        self._log(f"[API] ⚠ {last_error}")
                        if retry < API_MAX_RETRIES:
                            wait = 2 ** retry
                            self._log(f"[API] Waiting {wait}s before retry...")
                            time.sleep(wait)
                            continue
                        break  # try next model

                    else:
                        last_error = f"HTTP {status} | body={body[:300]}"
                        self._log(f"[API] ⚠ Unexpected: {last_error}")
                        break  # unknown status → try next model

                except requests.exceptions.Timeout:
                    last_error = (
                        f"Timeout after {API_TIMEOUT}s (model={model_name}, "
                        f"retry={retry + 1}/{API_MAX_RETRIES + 1})"
                    )
                    self._log(f"[API] ⚠ {last_error}")
                    if retry < API_MAX_RETRIES:
                        continue
                    break

                except requests.exceptions.ConnectionError as ce:
                    last_error = (
                        f"Connection error: {ce}. "
                        f"Check network, proxy, and DEEPSEEK_BASE_URL={self.base_url}"
                    )
                    self._log(f"[API] ❌ {last_error}")
                    break  # connection issues — try next model

                except requests.exceptions.RequestException as re:
                    last_error = f"Request error: {re}"
                    self._log(f"[API] ⚠ {last_error}")
                    break

        # ── All attempts exhausted ──
        error_msg = (
            f"All API attempts failed. "
            f"Models tried: {models_to_try}. "
            f"Last error: {last_error}"
        )
        self._log(f"[API] ❌ {error_msg}")
        raise RuntimeError(error_msg)

    def _parse_response(
        self, raw: str, candidates: List[Dict]
    ) -> List[Dict]:
        """Parse the API response with robust multi-strategy extraction.

        Strategy order:
          1. Direct JSON parse (clean)
          2. Extract from markdown code blocks
          3. Regex-extract JSON array/object from mixed text
          4. Repair common JSON issues (trailing commas) and retry each strategy

        Once parsed, matches songs to candidates by:
          - ``index`` field → positional lookup
          - ``title`` + ``artist`` fields → fuzzy candidate match
          - ``title`` only → candidate match
        """
        # ── Log raw response for debugging ──
        self._log(f"  [parse] Raw response ({len(raw)} chars):")
        self._log(f"  [parse] {raw[:500]}")
        if len(raw) > 500:
            self._log(f"  [parse] ... ({len(raw) - 500} more chars)")

        parsed = self._extract_json(raw)

        if parsed is None:
            self._log(f"  [parse] FAILED: all extraction strategies exhausted")
            raise ValueError(
                f"Could not extract JSON from response: {raw[:200]}"
            )

        self._log(f"  [parse] Extracted JSON type={type(parsed).__name__}  "
                  f"preview={json.dumps(parsed, ensure_ascii=False)[:200]}")

        # ── Normalize to list of song-ref dicts ──
        items = self._normalize_parsed(parsed)
        if not items:
            raise ValueError(
                f"Parsed JSON but got empty song list: {json.dumps(parsed, ensure_ascii=False)[:200]}"
            )

        self._log(f"  [parse] Normalized → {len(items)} song refs: "
                  f"{json.dumps(items[:3], ensure_ascii=False)}")

        # ── Match against candidates ──
        output = self._match_to_candidates(items, candidates)
        self._log(f"  [parse] Matched → {len(output)} validated songs")

        if not output:
            raise ValueError(
                f"Parsed {len(items)} items but matched 0 against candidates"
            )

        return output[:5]

    # ------------------------------------------------------------------
    # JSON extraction strategies
    # ------------------------------------------------------------------

    @staticmethod
    def _extract_json(raw: str) -> Optional[Any]:
        """Try every strategy to extract a JSON value from *raw*.

        Returns a parsed Python object (list or dict), or None.
        """
        # Pre-processing: strip BOM, normalize line endings
        text = raw.strip().lstrip("﻿")

        strategies = [
            # 1) Direct parse — the happy path
            lambda t: DeepSeekReranker._try_json_loads(t),
            # 2) Strip markdown ``` fences then direct parse
            lambda t: DeepSeekReranker._try_strip_fences(t),
            # 3) Repair trailing commas then direct parse (MUST run before regex extractors,
            #    otherwise the object extractor grabs the first {…} in a broken array)
            lambda t: DeepSeekReranker._try_repair_trailing_commas(t),
            # 4) Repair trailing commas + strip fences
            lambda t: DeepSeekReranker._try_repair_then_fences(t),
            # 5) Regex-extract largest JSON array from (possibly repaired) text
            lambda t: DeepSeekReranker._try_extract_array(t),
            # 6) Regex-extract largest JSON object — last resort
            lambda t: DeepSeekReranker._try_extract_object(t),
        ]

        for strategy in strategies:
            result = strategy(text)
            if result is not None:
                return result

        return None

    @staticmethod
    def _try_json_loads(text: str) -> Optional[Any]:
        """Attempt a direct ``json.loads``."""
        try:
            result = json.loads(text)
            if isinstance(result, (list, dict)):
                return result
            # Primitive value — not useful
            return None
        except (json.JSONDecodeError, ValueError):
            return None

    @staticmethod
    def _try_strip_fences(text: str) -> Optional[Any]:
        """Remove markdown code fences, then parse."""
        # Remove opening ```json / ``` / ``` JSON
        cleaned = re.sub(
            r"^```(?:json|JSON)?\s*\n?", "", text, flags=re.MULTILINE
        )
        # Remove closing ```
        cleaned = re.sub(r"\n?```\s*$", "", cleaned, flags=re.MULTILINE)
        cleaned = cleaned.strip()

        if cleaned == text:
            return None  # No change — avoid infinite loop with strategy 1

        return DeepSeekReranker._try_json_loads(cleaned)

    @staticmethod
    def _try_extract_array(text: str) -> Optional[Any]:
        """Find the longest [...] JSON array in *text* via regex."""
        # Greedy match of balanced-ish brackets — handles nested objects
        match = re.search(r"\[(?:[^\[\]]|\[(?:[^\[\]]*)\])*\]", text, re.DOTALL)
        if not match:
            return None

        candidate = match.group(0)
        try:
            result = json.loads(candidate)
            if isinstance(result, list) and len(result) > 0:
                return result
        except (json.JSONDecodeError, ValueError):
            pass

        return None

    @staticmethod
    def _try_extract_object(text: str) -> Optional[Any]:
        """Find the largest JSON object via brace-matching."""
        # Strategy: find all top-level { }, try each from largest to smallest
        depth = 0
        start = -1
        objects = []

        for i, ch in enumerate(text):
            if ch == "{":
                if depth == 0:
                    start = i
                depth += 1
            elif ch == "}":
                depth -= 1
                if depth == 0 and start >= 0:
                    objects.append(text[start : i + 1])

        # Try largest first
        for obj_str in sorted(objects, key=len, reverse=True):
            try:
                result = json.loads(obj_str)
                if isinstance(result, dict):
                    # Accept if it has song-like keys
                    if any(
                        k in result
                        for k in ("selected", "title", "recommendations", "result", "songs")
                    ):
                        return result
            except (json.JSONDecodeError, ValueError):
                continue

        return None

    @staticmethod
    def _try_repair_trailing_commas(text: str) -> Optional[Any]:
        """Remove trailing commas inside arrays/objects, then parse."""
        # Remove commas before ] or }
        repaired = re.sub(r",\s*([}\]])", r"\1", text)
        if repaired == text:
            return None  # No change

        return DeepSeekReranker._try_json_loads(repaired)

    @staticmethod
    def _try_repair_then_fences(text: str) -> Optional[Any]:
        """Strip fences from repaired text, then parse."""
        cleaned = re.sub(
            r"^```(?:json|JSON)?\s*\n?", "", text, flags=re.MULTILINE
        )
        cleaned = re.sub(r"\n?```\s*$", "", cleaned, flags=re.MULTILINE)
        cleaned = re.sub(r",\s*([}\]])", r"\1", cleaned)
        cleaned = cleaned.strip()

        try:
            result = json.loads(cleaned)
            if isinstance(result, (list, dict)):
                return result
        except (json.JSONDecodeError, ValueError):
            pass

        return None

    # ------------------------------------------------------------------
    # Normalize parsed JSON → list of song-ref dicts
    # ------------------------------------------------------------------

    @staticmethod
    def _normalize_parsed(parsed: Any) -> List[Dict]:
        """Convert *any* parsed JSON into a flat list of ``{title?, artist?, index?, reason?}`` dicts.

        Handles:
          - Direct list: ``[{...}, ...]``
          - Wrapped dict: ``{"selected": [...]}`` / ``{"recommendations": [...]}``
          - Single object: ``{"title": "...", "artist": "..."}``
        """
        # Already a list
        if isinstance(parsed, list):
            # If first element looks like a chat message (has "role"), skip it
            items = [
                item for item in parsed
                if isinstance(item, dict) and "role" not in item
            ]
            return items

        # Wrapped in a dict
        if isinstance(parsed, dict):
            # Known wrapper keys
            for key in ("selected", "recommendations", "result", "songs", "tracks", "items"):
                if key in parsed:
                    inner = parsed[key]
                    if isinstance(inner, list):
                        return [
                            item for item in inner
                            if isinstance(item, dict)
                        ]
                    if isinstance(inner, dict):
                        return [inner]

            # Unwrapped song object (has title/artist-like keys)
            if any(k in parsed for k in ("title", "name", "song")):
                return [parsed]

            # Check if any value is a list of dicts
            for val in parsed.values():
                if isinstance(val, list) and val and isinstance(val[0], dict):
                    return val

        return []

    # ------------------------------------------------------------------
    # Match parsed items to candidates
    # ------------------------------------------------------------------

    def _match_to_candidates(
        self, items: List[Dict], candidates: List[Dict]
    ) -> List[Dict]:
        """Match each parsed song-ref to a candidate and produce formatted output.

        Matching order:
          1. By ``index`` field → ``candidates[index]``
          2. By ``title`` + ``artist`` fuzzy match
          3. By ``title`` fuzzy match
          4. Skip if no match found
        """
        output: List[Dict] = []
        seen_titles: set = set()  # prevent duplicate matches

        for item in items:
            reason = str(item.get("reason", "") or "")

            # ── Strategy A: index-based ──
            raw_idx = item.get("index")
            if raw_idx is not None:
                try:
                    idx = int(raw_idx)
                    if 0 <= idx < len(candidates):
                        c = candidates[idx]
                        title = c.get("title", "")
                        if title not in seen_titles:
                            seen_titles.add(title)
                            output.append(self._format_result(c, reason))
                            continue
                except (ValueError, TypeError):
                    pass

            # ── Strategy B: title + artist fuzzy match ──
            title = str(item.get("title", "")).strip()
            artist = str(item.get("artist", "")).strip()
            # Also check alternate key names the API might use
            title = title or str(item.get("song", "")).strip() or str(item.get("name", "")).strip()
            artist = artist or str(item.get("singer", "")).strip()

            if title and title not in seen_titles:
                matched = self._fuzzy_match_candidate(
                    candidates, title, artist, seen_titles
                )
                if matched is not None:
                    seen_titles.add(matched.get("title", ""))
                    output.append(self._format_result(matched, reason))

        return output

    @staticmethod
    def _fuzzy_match_candidate(
        candidates: List[Dict],
        target_title: str,
        target_artist: str,
        seen_titles: set,
    ) -> Optional[Dict]:
        """Find the best candidate matching *target_title* and optionally *target_artist*.

        Matching tiers (tried in order):
          1. Exact title AND exact artist
          2. Exact title (ignoring artist)
          3. Target title is a substring of candidate title (or vice versa)
        """
        target_title_lower = target_title.lower().strip()
        target_artist_lower = target_artist.lower().strip() if target_artist else ""

        # Tier 1: exact title + artist
        if target_artist_lower:
            for c in candidates:
                c_title = str(c.get("title", "")).lower().strip()
                c_artist = str(c.get("artist", "")).lower().strip()
                if (
                    c_title == target_title_lower
                    and c_artist == target_artist_lower
                    and c.get("title", "") not in seen_titles
                ):
                    return c

        # Tier 2: exact title match only
        for c in candidates:
            c_title = str(c.get("title", "")).lower().strip()
            if c_title == target_title_lower and c.get("title", "") not in seen_titles:
                return c

        # Tier 3: substring match (bidirectional)
        for c in candidates:
            c_title = str(c.get("title", "")).strip()
            c_title_lower = c_title.lower()
            if (
                c_title not in seen_titles
                and (
                    target_title_lower in c_title_lower
                    or c_title_lower in target_title_lower
                )
            ):
                return c

        return None

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
            reason = f"「{theme}」主题与你的心情不谋而合" if theme else f"或许正是你此刻需要的旋律"
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
