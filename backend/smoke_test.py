"""Quick smoke test for the backend — run to verify everything wires up."""
import sys
import os

# Add project root + src/ to the path
_project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, _project_root)
sys.path.insert(0, os.path.join(_project_root, "src"))

from backend.app import app
from fastapi.testclient import TestClient

client = TestClient(app)

# 1. Health check
r = client.get("/health")
assert r.status_code == 200, f"Health failed: {r.status_code}"
data = r.json()
assert data["status"] == "ok"
assert data["modules"]["recommendation"] == "stable"
assert data["modules"]["recognition"] == "not_implemented"
print("[PASS] GET /health")

# 2. Recommend (missing body → validation error)
r = client.post("/recommend", json={})
assert r.status_code == 422, f"Expected 422, got {r.status_code}"
err = r.json()
assert err["success"] == False
assert "validation" in err["error"].lower()
print(f"[PASS] POST /recommend validation: {err['detail']}")

# 3. Recommend (valid body — will fail because no API key, but the endpoint works)
r = client.post("/recommend", json={"user_input": "test"})
# Will likely return 500 (no API key) or 400 (pipeline failed) — either is fine
print(f"[OK]   POST /recommend (valid): status={r.status_code}")
if r.status_code != 200:
    body = r.json()
    print(f"       error={body.get('error', 'unknown')}")

# 4. Feedback
r = client.post("/feedback", json={
    "user_query": "test query",
    "song_titles": ["夜曲", "平凡之路"],
    "ratings": {"夜曲": "like", "平凡之路": "dislike"},
})
assert r.status_code == 200, f"Feedback failed: {r.status_code}"
data = r.json()
assert data["success"] == True
print(f"[PASS] POST /feedback")

# 5. Recognition placeholder → 501
r = client.post("/recognition", json={"audio": "dGVzdA=="})
assert r.status_code == 501, f"Expected 501, got {r.status_code}"
data = r.json()
assert data["success"] == False
assert "recognition" in data["module"]
print(f"[PASS] POST /recognition → 501")

# 6. Composition placeholder → 501
r = client.post("/composition", json={"prompt": "a calm piano piece"})
assert r.status_code == 501, f"Expected 501, got {r.status_code}"
data = r.json()
assert data["success"] == False
assert "composition" in data["module"]
print(f"[PASS] POST /composition → 501")

# 7. OpenAPI schema
schema = app.openapi()
assert "/health" in schema["paths"]
assert "/recommend" in schema["paths"]
assert "/feedback" in schema["paths"]
assert "/recognition" in schema["paths"]
assert "/composition" in schema["paths"]
print(f"[PASS] OpenAPI schema has all 5 endpoints")

print("\n✅ All smoke tests passed!")
