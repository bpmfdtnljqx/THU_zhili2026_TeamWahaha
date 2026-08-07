"""Quick smoke test for the backend — run to verify everything wires up.

Usage:
    python backend/smoke_test.py
"""

import io
import sys
import os

# Add project root + src/ to the path
_project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, _project_root)
sys.path.insert(0, os.path.join(_project_root, "src"))

from backend.app import app
from fastapi.testclient import TestClient

client = TestClient(app)

# ── 1. Health check ──────────────────────────────────────────────────
r = client.get("/health")
assert r.status_code == 200, f"Health failed: {r.status_code}"
data = r.json()
assert data["status"] == "ok"
assert data["modules"]["recommendation"] == "stable"
assert data["modules"]["recognition"] == "not_implemented"
print("[PASS] GET /health")

# ── 2. Recommend (missing body → validation error) ───────────────────
r = client.post("/recommend", json={})
assert r.status_code == 422, f"Expected 422, got {r.status_code}"
err = r.json()
assert err["success"] is False
assert "validation" in err["error"].lower()
print(f"[PASS] POST /recommend validation: {err['detail']}")

# ── 3. Recommend (valid body) ────────────────────────────────────────
r = client.post("/recommend", json={"user_input": "test"})
# Will likely return 500 (no API key) or 400 (pipeline failed) — either is fine
print(f"[OK]   POST /recommend (valid): status={r.status_code}")
if r.status_code != 200:
    body = r.json()
    print(f"       error={body.get('error', 'unknown')}")

# ── 4. Feedback ──────────────────────────────────────────────────────
r = client.post("/feedback", json={
    "user_query": "test query",
    "song_titles": ["夜曲", "平凡之路"],
    "ratings": {"夜曲": "like", "平凡之路": "dislike"},
})
assert r.status_code == 200, f"Feedback failed: {r.status_code}"
data = r.json()
assert data["success"] is True
print(f"[PASS] POST /feedback")

# ── 5. Recognition — placeholder result (200) ────────────────────────
# Create a minimal valid WAV file (44-byte header + 1 sample).
_wav_header = (
    b"RIFF"
    + (36 + 2).to_bytes(4, "little")
    + b"WAVE"
    + b"fmt "
    + (16).to_bytes(4, "little")
    + (1).to_bytes(2, "little")     # PCM format
    + (1).to_bytes(2, "little")     # 1 channel
    + (44100).to_bytes(4, "little")  # sample rate
    + (88200).to_bytes(4, "little")  # byte rate
    + (2).to_bytes(2, "little")     # block align
    + (16).to_bytes(2, "little")    # bits per sample
    + b"data"
    + (2).to_bytes(4, "little")     # data size
    + b"\x00\x00"                   # one silent sample
)
assert len(_wav_header) == 46

# Upload as a valid WAV file.
r = client.post(
    "/recognition",
    files={"file": ("test.wav", io.BytesIO(_wav_header), "audio/wav")},
)
assert r.status_code == 200, (
    f"Expected 200 for recognition placeholder, got {r.status_code}: "
    f"{r.json()}"
)
data = r.json()
assert data["success"] is True, f"Expected success=true: {data}"
assert data["module"] == "recognition"
assert "data" in data
assert data["data"]["title"] == ""
assert data["data"]["artist"] == ""
assert data["data"]["confidence"] == 0.0
assert "message" in data
print(f"[PASS] POST /recognition → 200 (placeholder)")

# Also test unsupported format rejection.
r = client.post(
    "/recognition",
    files={"file": ("test.txt", io.BytesIO(b"not audio"), "text/plain")},
)
assert r.status_code == 400, (
    f"Expected 400 for unsupported format, got {r.status_code}"
)
data = r.json()
assert data["success"] is False
assert "unsupported" in data.get("error", "").lower()
print(f"[PASS] POST /recognition unsupported format → 400")

# ── 6. Composition — placeholder result (200) ─────────────────────────
r = client.post("/composition", json={
    "prompt": "Create a relaxing piano melody",
    "duration": 30,
})
assert r.status_code == 200, (
    f"Expected 200 for composition placeholder, got {r.status_code}: "
    f"{r.json()}"
)
data = r.json()
assert data["success"] is True
assert data["module"] == "composition"
assert "data" in data
assert data["data"]["audio_url"] is None
assert data["data"]["duration"] == 30
assert "message" in data
print(f"[PASS] POST /composition → 200 (placeholder)")

# Test composition with optional fields.
r = client.post("/composition", json={
    "prompt": "Upbeat jazz with piano and drums",
    "duration": 60,
    "style": "jazz",
    "tempo": 120,
    "key": "C major",
})
assert r.status_code == 200, (
    f"Expected 200, got {r.status_code}: {r.json()}"
)
data = r.json()
assert data["success"] is True
print(f"[PASS] POST /composition with optional fields → 200")

# ── 7. OpenAPI schema ────────────────────────────────────────────────
schema = app.openapi()
assert "/health" in schema["paths"]
assert "/recommend" in schema["paths"]
assert "/feedback" in schema["paths"]
assert "/recognition" in schema["paths"]
assert "/composition" in schema["paths"]
print(f"[PASS] OpenAPI schema has all 5 endpoints")

# ── 8. Verify recognition schema uses multipart/form-data ─────────────
recognition_schema = schema["paths"]["/recognition"]["post"]
# The request body should be multipart/form-data (file upload).
req_body = recognition_schema.get("requestBody", {})
content_types = req_body.get("content", {})
assert "multipart/form-data" in content_types, (
    f"Expected multipart/form-data, got: {list(content_types.keys())}"
)
print(f"[PASS] /recognition uses multipart/form-data")

print("\n✅ All smoke tests passed!")
