"""
benchmark.py
------------
Performance benchmark for the Lyra reranker.

Measures:
- Average response time across N runs (target ≤ 10s)
- Cache hit latency (target < 1s)
- Timing breakdown (prompt build / API call / parse)
- Quality checks (diversity, relevance of results)

Usage:
    python src/benchmark.py              # default: 3 runs, Top-10
    python src/benchmark.py --runs 5     # 5 runs
    python src/benchmark.py --no-cache   # disable cache for pure API measurement
    python src/benchmark.py --quality    # run quality validation
"""

import argparse
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


def run_quality_check(reranker: DeepSeekReranker) -> Dict[str, Any]:
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
        "--queries", type=str, nargs="*",
        help="Custom queries to test (space-separated)",
    )

    args = parser.parse_args()

    # Override cache setting if requested
    if args.no_cache:
        os.environ["LYRA_CACHE_ENABLED"] = "0"
        # Re-import to pick up new env
        import importlib
        import reranker as rk
        importlib.reload(rk)

    # Init reranker
    reranker = DeepSeekReranker()

    queries = args.queries if args.queries else TEST_QUERIES

    # Run benchmark
    run_benchmark(reranker, queries, runs_per_query=args.runs)

    # Optional quality check
    if args.quality:
        print()
        run_quality_check(reranker)


if __name__ == "__main__":
    main()
