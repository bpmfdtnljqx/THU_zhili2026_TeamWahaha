"""
planner.py
----------
Intent extraction module for the Lyra Agent.

Converts raw natural-language user input into structured music intent
via the DeepSeek API.  The Planner understands *who the user is and what
they need* — it NEVER recommends songs.

Design principles
------------------
- Single-responsibility: understand intent, nothing else.
- Graceful degradation: if the API call fails, returns the raw user
  input as ``free_text`` so downstream retrieval still works.
- Debug-friendly: all Planner output is logged when ``LYRA_VERBOSE=1``
  or ``LYRA_PLANNER_DEBUG=1``.
- Reuses the same multi-strategy JSON extraction patterns as
  ``reranker.py`` for robust parsing.
"""

import json
import os
import re
import time
from typing import Any, Dict, List, Optional

import requests
from dotenv import load_dotenv

from logger import get_logger

load_dotenv()

# ---------------------------------------------------------------------------
# Logger
# ---------------------------------------------------------------------------

PLANNER_DEBUG = (
    os.getenv("LYRA_VERBOSE", "0") == "1"
    or os.getenv("LYRA_PLANNER_DEBUG", "0") == "1"
)
_log = get_logger("planner", enabled=PLANNER_DEBUG)

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

API_TEMPERATURE = 0.0
API_MAX_TOKENS = 200  # intent is small — ~100 tokens is plenty
API_TIMEOUT = 10  # seconds — planner should be fast

SYSTEM_PROMPT = (
    "你是音乐推荐系统的「意图理解」模块。"
    "你的职责是深入理解用户的情绪状态、生活场景和聆听需求。\n\n"
    "重要原则：\n"
    "1. 你只负责理解用户——绝不推荐歌曲，绝不提及任何歌手或歌名。\n"
    "2. 提取情绪和场景信息，而不是机械地抓取关键词。\n"
    "  例：用户说「加班到凌晨，不想听吵的歌」\n"
    "  → 情绪：疲惫、压抑  /  场景：深夜、独处  /  听众需求：放松、安静陪伴  /  避免：吵闹、节奏快\n"
    "3. 如果用户没有明确提及某个维度，可以合理推断（如「加班到凌晨」暗示 energy_level 偏低），"
    "但不要编造不存在的信息。\n"
    "4. 只输出 JSON，不要任何解释文字，不要 markdown 代码块。"
)

USER_TEMPLATE = (
    "用户输入：{user_input}\n\n"
    "输出 JSON 格式（严格按此结构，字段可为空数组/空字符串）：\n"
    "{{\n"
    '  "emotion": ["情绪1", "情绪2"],\n'
    '  "scene": ["场景1", "场景2"],\n'
    '  "listener_need": ["需求1", "需求2"],\n'
    '  "energy_level": "low / medium / high（推断）",\n'
    '  "avoid": ["用户想避免的风格/情绪/氛围"]\n'
    "}}"
)

# ---------------------------------------------------------------------------
# Planner
# ---------------------------------------------------------------------------


class Planner:
    """Extract structured music-listening intent from raw user input.

    Uses the DeepSeek API with a strict system prompt that scopes the
    model to intent extraction *only*.  Results are validated and
    enriched with a ``free_text`` field suitable for downstream embedding.
    """

    def __init__(self, verbose: bool = None):
        self.api_key = os.getenv("DEEPSEEK_API_KEY", "")
        self.model = os.getenv("DEEPSEEK_MODEL", "deepseek-chat")

        raw_base = os.getenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com")
        self.base_url = raw_base.rstrip("/")
        if not self.base_url.endswith("/v1"):
            self.base_url += "/v1"

        # verbose flag controls whether the Planner itself logs;
        # when explicitly passed, it overrides the env-var setting.
        if verbose is not None:
            global _log
            from logger import Logger
            _log = Logger("planner", enabled=verbose)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def analyze(self, user_input: str) -> Dict[str, Any]:
        """Convert raw user input into structured music intent.

        Returns a dict with keys:
          emotion, scene, listener_need, energy_level, avoid, free_text

        On any failure the method falls back to a minimal intent dict
        whose ``free_text`` is the original user input — downstream
        retrieval degrades gracefully to the pre-agent behaviour.
        """
        t0 = time.time()

        # ── Call API ──
        try:
            raw_response, api_ms = self._call_api(user_input)
        except Exception as exc:
            _log.warn(f"API call failed → fallback.  ({exc})")
            return self._fallback(user_input)

        # ── Parse ──
        try:
            intent = self._parse_intent(raw_response)
        except Exception as exc:
            _log.warn(f"Parse failed → fallback.  ({exc})")
            _log.debug(f"Raw response was: {raw_response[:300]}")
            return self._fallback(user_input)

        # ── Validate & enrich ──
        intent = self._validate_intent(intent)
        intent["free_text"] = self._build_free_text(user_input, intent)

        elapsed = (time.time() - t0) * 1000
        _log.debug(
            f"Done in {elapsed:.0f}ms | api={api_ms:.0f}ms | "
            f"intent={json.dumps({k: v for k, v in intent.items() if k != 'free_text'}, ensure_ascii=False)}"
        )

        return intent

    # ------------------------------------------------------------------
    # API call
    # ------------------------------------------------------------------

    def _call_api(self, user_input: str) -> tuple:
        """Call DeepSeek API for intent extraction.

        Returns (raw_text, latency_ms).  Raises RuntimeError on failure.
        """
        user_message = USER_TEMPLATE.format(user_input=user_input)

        payload = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": user_message},
            ],
            "temperature": API_TEMPERATURE,
            "max_tokens": API_MAX_TOKENS,
        }

        url = f"{self.base_url}/chat/completions"

        _log.debug(
            f"→ API | model={self.model} | "
            f"input_len={len(user_input)} | timeout={API_TIMEOUT}s"
        )

        t0 = time.time()
        response = requests.post(
            url,
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
            },
            json=payload,
            timeout=API_TIMEOUT,
        )
        api_ms = (time.time() - t0) * 1000

        if response.status_code != 200:
            body_preview = response.text[:300]
            raise RuntimeError(
                f"Planner API returned HTTP {response.status_code}: {body_preview}"
            )

        data = response.json()
        choices = data.get("choices", [])
        if not choices:
            raise RuntimeError(
                f"Planner API returned no choices. Keys: {list(data.keys())}"
            )

        content = choices[0].get("message", {}).get("content", "")
        if not content:
            finish = choices[0].get("finish_reason", "unknown")
            raise RuntimeError(f"Planner API returned empty content (finish_reason={finish})")

        _log.debug(f"← API | {api_ms:.0f}ms | content_len={len(content)}")
        return content, api_ms

    # ------------------------------------------------------------------
    # JSON parsing (reuses the multi-strategy pattern from reranker.py)
    # ------------------------------------------------------------------

    def _parse_intent(self, raw: str) -> Dict[str, Any]:
        """Extract a validated intent dict from the raw API response."""
        parsed = self._extract_json(raw)

        if parsed is None:
            raise ValueError(f"Could not extract JSON from: {raw[:200]}")

        # If the API returned a list, take the first element
        if isinstance(parsed, list):
            if len(parsed) == 0:
                raise ValueError("Parsed JSON is an empty list")
            parsed = parsed[0]

        if not isinstance(parsed, dict):
            raise ValueError(f"Expected dict, got {type(parsed).__name__}: {str(parsed)[:200]}")

        return parsed

    @staticmethod
    def _extract_json(raw: str) -> Optional[Any]:
        """Multi-strategy JSON extraction (same pattern as reranker.py)."""
        text = raw.strip().lstrip("﻿")  # strip BOM

        strategies = [
            # 1) Direct parse
            lambda t: Planner._try_json_loads(t),
            # 2) Strip markdown fences
            lambda t: Planner._try_strip_fences(t),
            # 3) Repair trailing commas
            lambda t: Planner._try_repair_commas(t),
            # 4) Regex-extract JSON object
            lambda t: Planner._try_extract_object(t),
        ]

        for strategy in strategies:
            result = strategy(text)
            if result is not None:
                return result

        return None

    @staticmethod
    def _try_json_loads(text: str) -> Optional[Any]:
        try:
            result = json.loads(text)
            if isinstance(result, (list, dict)):
                return result
        except (json.JSONDecodeError, ValueError):
            pass
        return None

    @staticmethod
    def _try_strip_fences(text: str) -> Optional[Any]:
        cleaned = re.sub(r"^```(?:json|JSON)?\s*\n?", "", text, flags=re.MULTILINE)
        cleaned = re.sub(r"\n?```\s*$", "", cleaned, flags=re.MULTILINE)
        cleaned = cleaned.strip()
        if cleaned == text:
            return None
        return Planner._try_json_loads(cleaned)

    @staticmethod
    def _try_repair_commas(text: str) -> Optional[Any]:
        repaired = re.sub(r",\s*([}\]])", r"\1", text)
        if repaired == text:
            return None
        return Planner._try_json_loads(repaired)

    @staticmethod
    def _try_extract_object(text: str) -> Optional[Any]:
        """Find the largest JSON object via brace-matching."""
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

        for obj_str in sorted(objects, key=len, reverse=True):
            result = Planner._try_json_loads(obj_str)
            if isinstance(result, dict):
                # Accept if it has at least one intent-like key
                if any(k in result for k in ("emotion", "scene", "listener_need", "energy_level", "avoid")):
                    return result
                # Also accept as a last resort if it just looks like JSON
                if len(result) >= 2:
                    return result

        return None

    # ------------------------------------------------------------------
    # Validation
    # ------------------------------------------------------------------

    @staticmethod
    def _validate_intent(intent: Dict[str, Any]) -> Dict[str, Any]:
        """Ensure the intent dict has all expected fields with sensible defaults.

        Returns a clean dict — never mutates the original.
        """
        validated: Dict[str, Any] = {}

        # List fields — normalise to list of strings
        for field in ("emotion", "scene", "listener_need", "avoid"):
            raw = intent.get(field, [])
            if isinstance(raw, list):
                validated[field] = [str(v).strip() for v in raw if str(v).strip()]
            elif isinstance(raw, str) and raw.strip():
                validated[field] = [raw.strip()]
            else:
                validated[field] = []

        # energy_level — must be one of low/medium/high
        raw_energy = str(intent.get("energy_level", "")).strip().lower()
        if raw_energy in ("low", "medium", "high"):
            validated["energy_level"] = raw_energy
        elif "低" in raw_energy or "low" in raw_energy:
            validated["energy_level"] = "low"
        elif "高" in raw_energy or "high" in raw_energy:
            validated["energy_level"] = "high"
        else:
            validated["energy_level"] = "medium"  # sensible default

        return validated

    # ------------------------------------------------------------------
    # Free-text synthesis
    # ------------------------------------------------------------------

    @staticmethod
    def _build_free_text(user_input: str, intent: Dict[str, Any]) -> str:
        """Build a rich, natural-language query string from structured intent.

        Produces flowing narrative prose (not bullet points) so BGE-M3
        can embed the full emotional context more meaningfully.

        Example output:
          "用户感到疲惫、压抑，正处于深夜、独处的场景中，
           需要放松、安静陪伴的音乐，希望听到安静舒缓的音乐。
           不想听到吵闹、节奏快风格的歌曲。用户说：「加班到凌晨...」"
        """
        parts = []

        emotion = intent.get("emotion", [])
        scene = intent.get("scene", [])
        need = intent.get("listener_need", [])
        energy = intent.get("energy_level", "")
        avoid = intent.get("avoid", [])

        # Build a flowing narrative sentence
        sentence_parts = []
        if emotion:
            sentence_parts.append(f"用户感到{'、'.join(emotion)}")
        if scene:
            sentence_parts.append(f"正处于{'、'.join(scene)}的场景中")
        if need:
            sentence_parts.append(f"需要{'、'.join(need)}的音乐")

        energy_map = {"low": "安静舒缓", "medium": "中等节奏", "high": "高能量"}
        if energy and energy in energy_map:
            sentence_parts.append(f"希望听到{energy_map[energy]}的音乐")

        if sentence_parts:
            parts.append("，".join(sentence_parts) + "。")

        if avoid:
            parts.append(f"不想听到{'、'.join(avoid)}风格的歌曲。")

        # Always append the original user input as an anchor
        parts.append(f"用户说：「{user_input}」")

        return " ".join(parts)

    # ------------------------------------------------------------------
    # Fallback
    # ------------------------------------------------------------------

    @staticmethod
    def _fallback(user_input: str) -> Dict[str, Any]:
        """Minimal intent — degrades gracefully to the pre-agent behaviour."""
        return {
            "emotion": [],
            "scene": [],
            "listener_need": [],
            "energy_level": "medium",
            "avoid": [],
            "free_text": user_input,
        }
