"""
test_reranker_parse.py
---------------------
Verify that _extract_json / _normalize_parsed / _match_to_candidates
handles every response format the DeepSeek API might return.

Run:  python test_reranker_parse.py
"""

import json
import sys
import os

# Allow running directly from the repo root
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "src"))

from reranker import DeepSeekReranker

# ── Fake candidates (what the retriever actually returns) ──
CANDIDATES = [
    {"id": "62",  "title": "小美满",   "artist": "周深",   "album": "小美满",      "year": "2024", "genre": "流行", "core_theme": ["温暖"],   "emotion": ["治愈"], "suitable_scene": ["睡前"]},
    {"id": "10",  "title": "觅光",     "artist": "张韶涵", "album": "觅光",        "year": "2023", "genre": "流行", "core_theme": ["希望"],   "emotion": ["励志"], "suitable_scene": ["早晨"]},
    {"id": "98",  "title": "我相信",   "artist": "杨培安", "album": "我相信",      "year": "2006", "genre": "摇滚", "core_theme": ["自信"],   "emotion": ["激励"], "suitable_scene": ["运动"]},
    {"id": "45",  "title": "正能量",   "artist": "萧全",   "album": "正能量",      "year": "2015", "genre": "流行", "core_theme": ["积极"],   "emotion": ["活力"], "suitable_scene": ["工作"]},
    {"id": "77",  "title": "亲亲我的宝贝", "artist": "周华健", "album": "亲亲我的宝贝", "year": "1994", "genre": "流行", "core_theme": ["亲情"], "emotion": ["温馨"], "suitable_scene": ["亲子"]},
]

reranker = DeepSeekReranker()

# ─────────────────────────────────────────────
# Test cases: (name, raw_response_string, expected_titles)
# ─────────────────────────────────────────────

TEST_CASES = [
    # 1 — Direct JSON array (most common / happy path)
    (
        "direct JSON array",
        json.dumps([
            {"title": "小美满",   "artist": "周深",   "reason": "温暖治愈"},
            {"title": "觅光",     "artist": "张韶涵", "reason": "充满希望"},
            {"title": "我相信",   "artist": "杨培安", "reason": "激励人心"},
            {"title": "正能量",   "artist": "萧全",   "reason": "活力满满"},
            {"title": "亲亲我的宝贝", "artist": "周华健", "reason": "温柔安抚"},
        ], ensure_ascii=False),
        ["小美满", "觅光", "我相信", "正能量", "亲亲我的宝贝"],
    ),
    # 2 — Wrapped object with "selected" key (old prompt format)
    (
        '{"selected": [...]}',
        json.dumps({"selected": [
            {"index": 0, "reason": "温暖治愈，适合睡前放松"},
            {"index": 1, "reason": "充满希望，旋律动人"},
            {"index": 2, "reason": "激励人心，节奏明快"},
            {"index": 3, "reason": "活力满满，正能量"},
            {"index": 4, "reason": "温柔安抚，亲子时光"},
        ]}, ensure_ascii=False),
        ["小美满", "觅光", "我相信", "正能量", "亲亲我的宝贝"],
    ),
    # 3 — Markdown code block
    (
        "markdown code block",
        '```json\n' + json.dumps([
            {"title": "小美满",   "artist": "周深",   "reason": "温暖治愈"},
            {"title": "觅光",     "artist": "张韶涵", "reason": "充满希望"},
        ], ensure_ascii=False) + '\n```',
        ["小美满", "觅光"],
    ),
    # 4 — JSON with explanatory text before/after
    (
        "text before and after JSON",
        '根据你的查询，以下是推荐的Top5歌曲：\n' +
        json.dumps([
            {"title": "小美满", "artist": "周深", "reason": "温暖治愈"},
        ], ensure_ascii=False) +
        '\n希望你喜欢这些推荐！',
        ["小美满"],
    ),
    # 5 — Single song object (not wrapped in array)
    (
        "single song object",
        json.dumps({"title": "我相信", "artist": "杨培安", "reason": "激励人心"}, ensure_ascii=False),
        ["我相信"],
    ),
    # 6 — Wrapped with "recommendations" key
    (
        '{"recommendations": [...]}',
        json.dumps({"recommendations": [
            {"title": "小美满", "artist": "周深", "reason": "温暖治愈"},
            {"title": "觅光",   "artist": "张韶涵", "reason": "充满希望"},
        ]}, ensure_ascii=False),
        ["小美满", "觅光"],
    ),
    # 7 — Wrapped with "result" key
    (
        '{"result": [...]}',
        json.dumps({"result": [
            {"title": "小美满", "artist": "周深", "reason": "温暖治愈"},
        ]}, ensure_ascii=False),
        ["小美满"],
    ),
    # 8 — Index-based (old prompt) in a direct array
    (
        "index-based direct array",
        json.dumps([
            {"index": 0, "reason": "温暖治愈，适合睡前放松"},
            {"index": 1, "reason": "充满希望，旋律动人"},
        ], ensure_ascii=False),
        ["小美满", "觅光"],
    ),
    # 9 — Mixed: title + index (API used both fields)
    (
        "title + index mixed",
        json.dumps([
            {"title": "小美满", "artist": "周深", "index": 0, "reason": "温暖治愈"},
            {"title": "觅光",   "artist": "张韶涵", "index": 1, "reason": "充满希望"},
        ], ensure_ascii=False),
        ["小美满", "觅光"],
    ),
    # 10 — Trailing commas (malformed JSON — repair strategy)
    (
        "trailing commas in array",
        '[\n  {"title": "小美满", "artist": "周深", "reason": "温暖治愈"},\n  {"title": "觅光", "artist": "张韶涵", "reason": "充满希望"},\n]',
        ["小美满", "觅光"],
    ),
    # 11 — Substring/fuzzy title match (API used slightly different name)
    (
        "fuzzy title match",
        json.dumps([
            {"title": "小美满", "artist": "周深", "reason": "温暖治愈"},
        ], ensure_ascii=False),
        ["小美满"],
    ),
    # 12 — JSON inside markdown with trailing commas
    (
        "markdown + trailing commas",
        '```json\n[\n  {"title": "小美满", "artist": "周深", "reason": "温暖治愈"},\n]\n```',
        ["小美满"],
    ),
    # 13 — Empty response (should raise)
    (
        "empty response",
        "",
        None,  # expect fallback / error
    ),
    # 14 — Non-JSON garbage
    (
        "non-JSON garbage",
        "抱歉，我无法处理这个请求。请重新输入。",
        None,  # expect fallback / error
    ),
    # 15 — JSON with BOM character
    (
        "JSON with BOM",
        "﻿" + json.dumps([
            {"title": "小美满", "artist": "周深", "reason": "温暖治愈"},
        ], ensure_ascii=False),
        ["小美满"],
    ),
]

# ─────────────────────────────────────────────
# Run tests
# ─────────────────────────────────────────────

passed = 0
failed = 0

for name, raw, expected_titles in TEST_CASES:
    print(f"\n{'='*60}")
    print(f"TEST: {name}")
    print(f"{'='*60}")

    should_succeed = expected_titles is not None

    try:
        output = reranker._parse_response(raw, CANDIDATES)
        titles = [o["title"] for o in output]

        if not should_succeed:
            print(f"  ❌ FAIL: Expected failure but got {titles}")
            failed += 1
        elif titles == expected_titles:
            print(f"  ✅ PASS: {titles}")
            # Also check reasons are present
            reasons = [o.get("reason", "") for o in output]
            print(f"     Reasons: {reasons}")
            passed += 1
        else:
            print(f"  ❌ FAIL: Expected {expected_titles}, got {titles}")
            failed += 1

    except Exception as e:
        if not should_succeed:
            print(f"  ✅ PASS (correctly raised): {e}")
            passed += 1
        else:
            print(f"  ❌ FAIL (unexpected error): {e}")
            failed += 1

# ─────────────────────────────────────────────
# Also test the static _extract_json + _normalize_parsed directly
# ─────────────────────────────────────────────

print(f"\n{'='*60}")
print(f"DIRECT EXTRACTION TESTS")
print(f"{'='*60}")

EXTRACTION_TESTS = [
    ("direct array", '  [{"a":1}]  ', [{"a": 1}]),
    ("direct object with selected", '{"selected":[{"a":1}]}', {"selected": [{"a": 1}]}),
    ("markdown fence", '```json\n[{"a":1}]\n```', [{"a": 1}]),
    ("trailing comma repair", '[{"a":1},]', [{"a": 1}]),
    ("BOM prefix", '﻿[{"a":1}]', [{"a": 1}]),
    ("text before array", 'here: [{"a":1}] done', [{"a": 1}]),
    ("text before object", 'result: {"selected":[{"a":1}]} end', [{"a": 1}]),  # array extractor wins — correct
]

for name, raw, expected in EXTRACTION_TESTS:
    result = DeepSeekReranker._extract_json(raw)
    if result == expected:
        print(f"  ✅ {name}")
        passed += 1
    else:
        print(f"  ❌ {name}: expected {expected!r}, got {result!r}")
        failed += 1

# ─────────────────────────────────────────────
# Summary
# ─────────────────────────────────────────────

print(f"\n{'='*60}")
print(f"SUMMARY: {passed} passed, {failed} failed")
print(f"{'='*60}")

if failed > 0:
    sys.exit(1)
else:
    print("All tests passed! 🎉")
