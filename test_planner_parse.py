"""Quick smoke test for Planner — no API calls, just parsing logic."""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "src"))

from planner import Planner

test_cases = [
    ("direct object", '{"emotion":["疲惫"],"scene":["深夜"],"listener_need":["放松"],"energy_level":"low","avoid":["吵闹"]}'),
    ("with markdown fence", '```json\n{"emotion":["思念"],"scene":["雨夜"],"listener_need":["安静"],"energy_level":"low","avoid":[]}\n```'),
    ("with text wrapper", '分析结果：{"emotion":["开心"],"scene":["聚会"],"listener_need":["欢乐"],"energy_level":"high","avoid":["悲伤"]}完成'),
    ("trailing comma repair", '{"emotion":["疲惫"],"scene":["深夜"],"listener_need":["放松"],"energy_level":"low","avoid":["吵闹"],}'),
    ("minimal intent", '{"emotion":[],"scene":[],"listener_need":[],"energy_level":"medium","avoid":[]}'),
]

for name, raw in test_cases:
    parsed = Planner._extract_json(raw)
    if parsed:
        if isinstance(parsed, list):
            parsed = parsed[0] if parsed else {}
        validated = Planner._validate_intent(parsed)
        print(f"  [OK] {name}: {validated}")
    else:
        print(f"  [FAIL] {name}: extraction returned None")

# Test _build_free_text
intent = {"emotion":["悲伤","思念"],"scene":["雨夜"],"listener_need":["安静"],"energy_level":"low","avoid":["欢快"]}
free = Planner._build_free_text("失恋了想一个人静静", intent)
print(f"\n  free_text preview: {free[:150]}...")

# Test fallback
fb = Planner._fallback("test input")
print(f"  fallback: free_text={fb['free_text']}, energy={fb['energy_level']}")

# Test energy_level normalisation
assert Planner._validate_intent({"energy_level": "低"})["energy_level"] == "low"
assert Planner._validate_intent({"energy_level": "HIGH"})["energy_level"] == "high"
assert Planner._validate_intent({"energy_level": "unknown"})["energy_level"] == "medium"
print("\n  Energy level normalisation: OK")

# Test non-JSON fallback
none_result = Planner._extract_json("抱歉我无法理解")
assert none_result is None, f"Expected None, got {none_result}"
print("  Non-JSON fallback: OK")

print("\nAll Planner static tests passed!")
