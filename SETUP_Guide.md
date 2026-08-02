# Lyra — Developer Run Guide

How to set up and run the Lyra AI music recommendation agent from zero.

---

## 1. Prerequisites

- **Python 3.10+** (developed on 3.11)
- **Git**
- **A DeepSeek API key** (free tier works: <https://platform.deepseek.com/api_keys>)
- **Windows / macOS / Linux** (tested on Windows 11)

---

## 2. Clone & Environment

```bash
git clone <repo-url>
cd lyra

# Create and activate a virtual environment
python -m venv .venv

# Windows:
.venv\Scripts\activate

# macOS / Linux:
source .venv/bin/activate
```

---

## 3. Install Dependencies

```bash
# Core dependencies (torch, sentence-transformers, chromadb, FastAPI, etc.)
pip install -r requirements.txt

# If you're in China and pip is slow, use a mirror:
pip install -r requirements.txt -i https://pypi.tuna.tsinghua.edu.cn/simple
```

> ⚠️ `torch` is ~2.5 GB. The first install may take several minutes.

---

## 4. Configure Environment

Copy the example and fill in your API key:

```bash
# Create .env from scratch:
echo HF_ENDPOINT=https://hf-mirror.com > .env
echo DEEPSEEK_API_KEY=sk-YOUR-KEY-HERE >> .env
echo DEEPSEEK_BASE_URL=https://api.deepseek.com >> .env
echo DEEPSEEK_MODEL=deepseek-chat >> .env
```

| Variable | Required | Description |
|----------|----------|-------------|
| `DEEPSEEK_API_KEY` | **Yes** | Your DeepSeek API key |
| `DEEPSEEK_BASE_URL` | No | Default: `https://api.deepseek.com` |
| `DEEPSEEK_MODEL` | No | Default: `deepseek-chat` |
| `HF_ENDPOINT` | No | HuggingFace mirror (set to `https://hf-mirror.com` in China) |
| `LYRA_DEBUG` | No | Set to `1` to see pipeline debug output (stderr) |
| `LYRA_CORS_ORIGINS` | No | Default: `*` (all origins) |

> `.env` is in `.gitignore` — it will never be committed.

---

## 5. Build the Song Index (First Time Only)

The BGE-M3 embedding model (~2 GB) is downloaded on first use, then cached locally.

```bash
python src/build_index.py
```

This reads `songs.json` (170 songs), embeds them, and writes to `chroma_db/`.

> `chroma_db/` is in `.gitignore`. Each teammate builds their own copy.

---

## 6. Start the Backend

```bash
# From the project root:
uvicorn backend.app:app --reload --host 0.0.0.0 --port 8000
```

Or use the helper script (Windows):

```bash
start_backend.bat
```

You should see:

```
INFO:     Uvicorn running on http://127.0.0.1:8000
[retriever] INFO Loading embedding model BAAI/bge-m3...
[retriever] INFO Collection 'lyra_songs' loaded (170 songs).
```

Verify the health endpoint:

```bash
curl http://127.0.0.1:8000/health
# {"status":"ok","version":"1.0.0","modules":{"recommendation":"stable",...}}
```

---

## 7. Open the Frontend

Open `frontend/index.html` directly in a browser, or use the helper script:

```bash
start_frontend.bat
```

The health indicator in the UI turns green when the backend is reachable.

> The frontend connects to `http://127.0.0.1:8000` by default.
> To use a different backend URL, open with a query parameter:
> `frontend/index.html?api=http://other-host:8000`

---

## 8. CLI Demo (Alternative)

You can also run Lyra directly in the terminal:

```bash
python src/main.py
```

Type a mood or situation ("加班到凌晨，不想听太吵的歌") and get song recommendations with AI-generated reasons.

---

## 9. Run Tests

```bash
# Smoke tests (fast — verifies all endpoints)
python backend/smoke_test.py

# Pipeline benchmark
python src/benchmark.py --runs 3 --timing

# Full benchmark suite (diversity, LLM judge, pipeline timing)
python src/benchmark.py --full
```

---

## 10. Troubleshooting

### "No module named 'src.xxx'" or "No module named 'api'"

Ensure you're running from the **project root** (`lyra/`), not from inside `src/` or `backend/`.
The backend adds `src/` to `sys.path` automatically.

### "Collection 'lyra_songs' loaded (0 songs)" or ChromaDB errors

The index was never built or is corrupted. Run:

```bash
python src/build_index.py
```

### DeepSeek API errors (401, 403, timeout)

1. Verify your API key: **<https://platform.deepseek.com/api_keys>**
2. Check your account balance (free tier has limits)
3. Run the diagnostic tool:

```bash
python diagnose_api.py
```

The recommendation pipeline degrades gracefully: if the API is unreachable,
it falls back to vector ranking results (no AI-generated reasons).

### HuggingFace model download fails

Set the mirror in `.env`:

```
HF_ENDPOINT=https://hf-mirror.com
```

### Frontend shows "Backend unreachable"

Make sure the backend is running (`uvicorn backend.app:app --reload`).
Check that the port matches the frontend URL (`http://127.0.0.1:8000` by default).

### Port 8000 already in use

```bash
# Windows: find and kill the process
netstat -ano | findstr :8000
taskkill /PID <PID> /F

# Then restart on a different port:
uvicorn backend.app:app --reload --port 8001
# And open: frontend/index.html?api=http://127.0.0.1:8001
```
