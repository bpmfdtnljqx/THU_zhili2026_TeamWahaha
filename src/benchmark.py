"""
benchmark.py
------------
Performance benchmark for the Lyra reranker.

Measures:
- Average response time across N runs (target ≤ 10s)
- Cache hit latency (target < 1s)
- Timing breakdown (pipeline stages)
- Quality checks (diversity, relevance of results)
- Diversity metrics (Jaccard distance on emotion/theme/genre)
- LLM judge evaluation (reason quality scoring)

Usage:
    python src/benchmark.py                 # default: 3 runs
    python src/benchmark.py --runs 5        # 5 runs
    python src/benchmark.py --no-cache      # disable cache
    python src/benchmark.py --quality       # basic quality validation
    python src/benchmark.py --diversity     # diversity metrics
    python src/benchmark.py --judge         # LLM judge evaluation (uses API)
    python src/benchmark.py --full          # run all checks
"""

import argparse
import json
import os
import statistics
import sys
import time
from typing import Any, Dict, List

# Ensure we can import from src/
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from reranker import DeepSeekReranker, CACHE_ENABLED


# ---------------------------------------------------------------------------
# Test queries — diverse emotional scenarios
# ---------------------------------------------------------------------------

TEST_QUERIES = [
    "失恋了，下雨的夜晚，想一个人静静",
    "周末早晨阳光很好，想去公园跑步",
    "加班到深夜，感觉很疲惫但很充实",
    "和朋友们一起庆祝生日，特别开心",
    "想念远方的人，希望能快点见面",
]


# ---------------------------------------------------------------------------
# Benchmark runner
# ---------------------------------------------------------------------------


def run_benchmark(
    reranker: DeepSeekReranker,
    queries: List[str],
    runs_per_query: int = 3,
) -> List[Dict[str, Any]]:
    """Run benchmark across queries and collect timing stats."""

    results: List[Dict[str, Any]] = []
    all_latencies: List[float] = []

    print("=" * 60)
    print("  Lyra Reranker — Performance Benchmark")
    print(f"  Queries: {len(queries)} | Runs per query: {runs_per_query}")
    print(f"  Cache: {'ON' if CACHE_ENABLED else 'OFF'}")
    print("=" * 60)
    print()

    # Need a retriever to get real candidates
    try:
        from retriever import Retriever
        retriever = Retriever()
    except Exception as e:
        print(f"[ERROR] Cannot load Retriever: {e}")
        print("Make sure chroma_db index exists. Run main.py first.")
        sys.exit(1)

    for qi, query in enumerate(queries):
        candidates = retriever.query(query, k=10)
        print(f"Query {qi + 1}: \"{query}\"")
        print(f"  Candidates: {len(candidates)}")

        query_latencies: List[float] = []

        for run in range(1, runs_per_query + 1):
            t0 = time.time()
            recs = reranker.rerank(query, candidates)
            elapsed = time.time() - t0

            query_latencies.append(elapsed)
            all_latencies.append(elapsed)

            print(
                f"  Run {run}: {elapsed:.2f}s | "
                f"Top-5: {[r['title'] for r in recs]}"
            )
            time.sleep(1)  # Brief pause to avoid rate limiting

        avg = statistics.mean(query_latencies)
        print(f"  → Avg: {avg:.2f}s | Min: {min(query_latencies):.2f}s | "
              f"Max: {max(query_latencies):.2f}s")
        if runs_per_query > 1:
            print(f"  → StdDev: {statistics.stdev(query_latencies):.2f}s")
        print()

        results.append({
            "query": query,
            "avg_s": avg,
            "min_s": min(query_latencies),
            "max_s": max(query_latencies),
            "runs": query_latencies,
        })

    # Summary
    print("=" * 60)
    print("  SUMMARY")
    print("=" * 60)
    overall_avg = statistics.mean(all_latencies)
    overall_min = min(all_latencies)
    overall_max = max(all_latencies)

    print(f"  Total runs:      {len(all_latencies)}")
    print(f"  Overall average: {overall_avg:.2f}s")
    print(f"  Overall min:     {overall_min:.2f}s")
    print(f"  Overall max:     {overall_max:.2f}s")

    if all_latencies:
        print(f"  P50:             {_percentile(all_latencies, 50):.2f}s")
        print(f"  P90:             {_percentile(all_latencies, 90):.2f}s")
        print(f"  P95:             {_percentile(all_latencies, 95):.2f}s")

    # Cache stats
    if reranker.cache_stats:
        print()
        print(f"  Cache size:  {reranker.cache_stats['size']}")
        print(f"  Cache hits:  {reranker.cache_stats['hits']}")
        print(f"  Cache misses:{reranker.cache_stats['misses']}")

    print()
    if overall_avg <= 10:
        print("  ✅ PASS: Average ≤ 10 seconds target")
    else:
        print(f"  ❌ FAIL: Average {overall_avg:.2f}s exceeds 10s target")

    return results


def run_quality_check(reranker: DeepSeekReranker) -> Dict[str, bool]:
    """Quick quality validation: diversity, relevance, output format."""
    print("=" * 60)
    print("  Quality Validation")
    print("=" * 60)
    print()

    try:
        from retriever import Retriever
        retriever = Retriever()
    except Exception as e:
        print(f"[ERROR] Cannot load Retriever: {e}")
        sys.exit(1)

    checks: Dict[str, bool] = {}

    for query in TEST_QUERIES:
        candidates = retriever.query(query, k=10)
        recs = reranker.rerank(query, candidates)

        # Check 1: Correct count
        count_ok = len(recs) == 5
        checks.setdefault("count == 5", True)
        checks["count == 5"] = checks["count == 5"] and count_ok

        # Check 2: No duplicate titles
        titles = [r["title"] for r in recs]
        unique_ok = len(titles) == len(set(titles))
        checks.setdefault("no_duplicates", True)
        checks["no_duplicates"] = checks["no_duplicates"] and unique_ok

        # Check 3: All have reasons
        reasons_ok = all(
            r.get("reason") and len(r["reason"]) > 5 for r in recs
        )
        checks.setdefault("has_reasons", True)
        checks["has_reasons"] = checks["has_reasons"] and reasons_ok

        # Check 4: Required fields present
        fields_ok = all(
            all(k in r for k in ["title", "artist", "album", "year", "genre", "reason", "distance"])
            for r in recs
        )
        checks.setdefault("all_fields", True)
        checks["all_fields"] = checks["all_fields"] and fields_ok

        # Print per-query results
        print(f'Query: "{query}"')
        print(f"  Count={len(recs)} Unique={unique_ok} Reasons={reasons_ok} Fields={fields_ok}")
        for i, r in enumerate(recs, 1):
            print(f"  {i}. {r['title']} — {r['artist']} | {r['reason'][:40]}...")
        print()

    # Summary
    print("=" * 60)
    print("  QUALITY SUMMARY")
    print("=" * 60)
    all_pass = True
    for check_name, passed in checks.items():
        status = "✅" if passed else "❌"
        if not passed:
            all_pass = False
        print(f"  {status} {check_name}")

    if all_pass:
        print("\n  ✅ All quality checks passed!")
    else:
        print("\n  ❌ Some quality checks failed.")

    return checks


# ---------------------------------------------------------------------------
# Diversity metrics
# ---------------------------------------------------------------------------


def run_diversity_check() -> None:
    """Measure diversity of Top-5 recommendations using Jaccard distance."""
    print("=" * 60)
    print("  Diversity Metrics")
    print("=" * 60)
    print()

    try:
        from retriever import Retriever
        from agent import LyraAgent
        agent = LyraAgent()
    except Exception as e:
        print(f"[ERROR] Cannot load pipeline: {e}")
        return

    all_scores: Dict[str, List[float]] = {
        "emotion": [],
        "core_theme": [],
        "genre": [],
    }

    for query in TEST_QUERIES:
        result = agent.recommend(query)
        ranked = result["ranked_results"]

        # Compute pairwise Jaccard distances
        scores = _compute_diversity(ranked)
        for key in all_scores:
            all_scores[key].extend(scores.get(key, []))

        # Per-query summary
        avg_emo = statistics.mean(scores["emotion"]) if scores["emotion"] else 0
        avg_theme = statistics.mean(scores["core_theme"]) if scores["core_theme"] else 0
        avg_genre = statistics.mean(scores["genre"]) if scores["genre"] else 0
        print(f'Query: "{query}"')
        print(f"  emotion Jaccard dist:    {avg_emo:.3f}")
        print(f"  core_theme Jaccard dist: {avg_theme:.3f}")
        print(f"  genre Jaccard dist:      {avg_genre:.3f}")
        # Also show the titles for quick scan
        titles = [r.get("title", "?") for r in ranked]
        artists = [r.get("artist", "?") for r in ranked]
        genres = [r.get("genre", "?") for r in ranked]
        print(f"  Titles:  {titles}")
        print(f"  Artists: {artists}")
        print(f"  Genres:  {genres}")
        print()

    # Overall summary
    print("=" * 60)
    print("  DIVERSITY SUMMARY")
    print("=" * 60)
    for key, label in [("emotion", "Emotion"), ("core_theme", "Theme"), ("genre", "Genre")]:
        vals = all_scores[key]
        if vals:
            avg = statistics.mean(vals)
            print(f"  {label} Jaccard distance (avg): {avg:.3f}  "
                  f"(higher = more diverse, range 0-1)")
    print()
    print("  Note: Jaccard distance of 1.0 means completely disjoint sets.")
    print("  Values > 0.5 indicate good diversity.")


def _compute_diversity(ranked: List[Dict]) -> Dict[str, List[float]]:
    """Compute pairwise Jaccard distances for emotion, core_theme, genre."""
    scores: Dict[str, List[float]] = {
        "emotion": [],
        "core_theme": [],
        "genre": [],
    }

    for i in range(len(ranked)):
        for j in range(i + 1, len(ranked)):
            for field in scores:
                set_i = _to_set(ranked[i].get(field, []))
                set_j = _to_set(ranked[j].get(field, []))
                dist = _jaccard_distance(set_i, set_j)
                scores[field].append(dist)

    return scores


def _to_set(value) -> set:
    """Normalize a value to a set of strings."""
    if isinstance(value, list):
        return set(str(v).strip().lower() for v in value if v)
    if isinstance(value, str) and value.strip():
        return {value.strip().lower()}
    return set()


def _jaccard_distance(a: set, b: set) -> float:
    """Jaccard distance: 1 - |intersection| / |union|.  1.0 = totally different."""
    union = a | b
    if not union:
        return 0.0  # both empty → identical (no diversity signal)
    intersection = a & b
    return 1.0 - len(intersection) / len(union)


# ---------------------------------------------------------------------------
# LLM Judge evaluation
# ---------------------------------------------------------------------------


def run_judge_evaluation() -> None:
    """Use the LLM to score recommendation quality."""
    print("=" * 60)
    print("  LLM Judge Evaluation")
    print("  (Scores reason quality on relevance, emotional resonance,")
    print("   and diversity. Uses the DeepSeek API — this is slow.)")
    print("=" * 60)
    print()

    try:
        from agent import LyraAgent
        agent = LyraAgent()
    except Exception as e:
        print(f"[ERROR] Cannot load pipeline: {e}")
        return

    import requests

    api_key = os.getenv("DEEPSEEK_API_KEY", "")
    model = os.getenv("DEEPSEEK_MODEL", "deepseek-chat")
    raw_base = os.getenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com")
    base_url = raw_base.rstrip("/")
    if not base_url.endswith("/v1"):
        base_url += "/v1"

    judge_prompt = (
        "你是音乐推荐质量评估专家。请对以下推荐结果进行评分。\n\n"
        "评分维度（每项1-5分）：\n"
        "1. 相关性(relevance): 推荐理由是否与歌曲本身的特点匹配？\n"
        "2. 情感共鸣(emotional_resonance): 推荐理由是否有文采、能打动人心？\n"
        "3. 多样性(diversity): 5首歌的推荐理由是否各不相同，各有侧重？\n\n"
        "只输出JSON，格式："
        '{{"relevance": 4, "emotional_resonance": 5, "diversity": 3, '
        '"comment": "简短评价"}}'
    )

    all_scores: List[Dict] = []

    for query in TEST_QUERIES:
        result = agent.recommend(query)
        ranked = result["ranked_results"]

        # Build evaluation input
        rec_text = "\n".join(
            f"{i}. 《{r.get('title','?')}》— {r.get('artist','?')}\n"
            f"   理由：{r.get('reason','')}"
            for i, r in enumerate(ranked, 1)
        )

        eval_message = (
            f"用户查询：{query}\n\n"
            f"推荐结果：\n{rec_text}\n\n"
            f"请对以上推荐进行评分（输出JSON）。"
        )

        payload = {
            "model": model,
            "messages": [
                {"role": "system", "content": judge_prompt},
                {"role": "user", "content": eval_message},
            ],
            "temperature": 0.0,
            "max_tokens": 150,
        }

        url = f"{base_url}/chat/completions"
        try:
            response = requests.post(
                url,
                headers={
                    "Authorization": f"Bearer {api_key}",
                    "Content-Type": "application/json",
                },
                json=payload,
                timeout=15,
            )
            if response.status_code == 200:
                data = response.json()
                content = data.get("choices", [{}])[0].get("message", {}).get("content", "")
                # Extract JSON
                scores = _extract_judge_scores(content)
                if scores:
                    all_scores.append(scores)
                    print(f'Query: "{query}"')
                    print(f"  Relevance: {scores.get('relevance','?')}/5")
                    print(f"  Emotional: {scores.get('emotional_resonance','?')}/5")
                    print(f"  Diversity: {scores.get('diversity','?')}/5")
                    print(f"  Comment: {scores.get('comment','')}")
                    print()
                else:
                    print(f'Query: "{query}" — could not parse judge response')
                    print(f"  Raw: {content[:200]}")
                    print()
            else:
                print(f'Query: "{query}" — API error {response.status_code}')
                print()
        except Exception as e:
            print(f'Query: "{query}" — error: {e}')
            print()

        time.sleep(1)  # avoid rate limiting

    # Summary
    if all_scores:
        print("=" * 60)
        print("  JUDGE SUMMARY")
        print("=" * 60)
        for dim, label in [
            ("relevance", "Relevance"),
            ("emotional_resonance", "Emotional Resonance"),
            ("diversity", "Diversity"),
        ]:
            vals = [s.get(dim, 0) for s in all_scores if dim in s]
            if vals:
                print(f"  {label}: avg={statistics.mean(vals):.2f}/5  "
                      f"(min={min(vals)}, max={max(vals)})")
        print()


def _extract_judge_scores(raw: str) -> Dict[str, Any]:
    """Extract judge scores from raw API response (JSON with fallbacks)."""
    import re

    # Try direct parse
    try:
        result = json.loads(raw)
        if isinstance(result, dict) and "relevance" in result:
            return result
    except json.JSONDecodeError:
        pass

    # Try stripping markdown fences
    cleaned = re.sub(r"^```(?:json|JSON)?\s*\n?", "", raw, flags=re.MULTILINE)
    cleaned = re.sub(r"\n?```\s*$", "", cleaned, flags=re.MULTILINE)
    try:
        result = json.loads(cleaned.strip())
        if isinstance(result, dict) and "relevance" in result:
            return result
    except json.JSONDecodeError:
        pass

    # Regex extract object
    match = re.search(r'\{[^}]+\}', raw)
    if match:
        try:
            result = json.loads(match.group(0))
            if isinstance(result, dict):
                return result
        except json.JSONDecodeError:
            pass

    return {}


# ---------------------------------------------------------------------------
# Pipeline timing
# ---------------------------------------------------------------------------


def run_pipeline_timing() -> None:
    """Show per-stage pipeline timing from agent.recommend()."""
    print("=" * 60)
    print("  Pipeline Timing Breakdown")
    print("=" * 60)
    print()

    try:
        from agent import LyraAgent
        agent = LyraAgent()
    except Exception as e:
        print(f"[ERROR] Cannot load pipeline: {e}")
        return

    all_stages: Dict[str, List[float]] = {
        "planner_s": [],
        "retriever_s": [],
        "reranker_s": [],
        "response_s": [],
        "pipeline_time_s": [],
    }

    for query in TEST_QUERIES:
        result = agent.recommend(query)
        stages = result["metadata"].get("stages", {})
        total = result["metadata"].get("pipeline_time_s", 0)

        for key in all_stages:
            if key == "pipeline_time_s":
                all_stages[key].append(total)
            else:
                all_stages[key].append(stages.get(key, 0))

        print(f'Query: "{query}"')
        print(f"  Planner:   {stages.get('planner_s', 0):.2f}s")
        print(f"  Retriever: {stages.get('retriever_s', 0):.2f}s")
        print(f"  Reranker:  {stages.get('reranker_s', 0):.2f}s")
        print(f"  Response:  {stages.get('response_s', 0):.2f}s")
        print(f"  Total:     {total:.2f}s")
        print()

    # Averages
    print("=" * 60)
    print("  STAGE AVERAGES")
    print("=" * 60)
    for key, label in [
        ("planner_s", "Planner"),
        ("retriever_s", "Retriever"),
        ("reranker_s", "Reranker"),
        ("response_s", "Response"),
        ("pipeline_time_s", "Total Pipeline"),
    ]:
        vals = all_stages[key]
        if vals:
            avg = statistics.mean(vals)
            pct = (avg / statistics.mean(all_stages["pipeline_time_s"]) * 100
                   if key != "pipeline_time_s" else 100)
            print(f"  {label:15s}: avg {avg:.2f}s ({pct:.0f}%)")
    print()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _percentile(data: List[float], p: float) -> float:
    """Calculate the p-th percentile of sorted data."""
    sorted_data = sorted(data)
    k = (len(sorted_data) - 1) * (p / 100.0)
    f = int(k)
    c = k - f
    if f + 1 < len(sorted_data):
        return sorted_data[f] * (1 - c) + sorted_data[f + 1] * c
    return sorted_data[f]


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def main():
    parser = argparse.ArgumentParser(
        description="Lyra Reranker Benchmark",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "--runs", type=int, default=3,
        help="Number of runs per query (default: 3)",
    )
    parser.add_argument(
        "--no-cache", action="store_true",
        help="Disable cache for pure API measurement",
    )
    parser.add_argument(
        "--quality", action="store_true",
        help="Run quality validation after benchmark",
    )
    parser.add_argument(
        "--diversity", action="store_true",
        help="Run diversity metrics on recommendations",
    )
    parser.add_argument(
        "--judge", action="store_true",
        help="Run LLM judge evaluation (uses API, slow)",
    )
    parser.add_argument(
        "--timing", action="store_true",
        help="Show per-stage pipeline timing breakdown",
    )
    parser.add_argument(
        "--full", action="store_true",
        help="Run all checks (quality + diversity + judge + timing)",
    )
    parser.add_argument(
        "--queries", type=str, nargs="*",
        help="Custom queries to test (space-separated)",
    )

    args = parser.parse_args()

    # Override cache setting if requested
    if args.no_cache:
        os.environ["LYRA_CACHE_ENABLED"] = "0"
        import importlib
        import reranker as rk
        importlib.reload(rk)

    queries = args.queries if args.queries else TEST_QUERIES

    # Init reranker
    reranker = DeepSeekReranker()

    # Run benchmark
    run_benchmark(reranker, queries, runs_per_query=args.runs)

    # Optional checks
    if args.quality or args.full:
        print()
        run_quality_check(reranker)

    if args.diversity or args.full:
        print()
        run_diversity_check()

    if args.judge or args.full:
        print()
        run_judge_evaluation()

    if args.timing or args.full:
        print()
        run_pipeline_timing()


if __name__ == "__main__":
    main()
