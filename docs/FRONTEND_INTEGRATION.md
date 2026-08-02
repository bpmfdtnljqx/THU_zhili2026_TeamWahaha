# Lyra Backend — Frontend Integration Guide

## Run the backend locally

```bash
# From the project root (D:\lyra):
uvicorn backend.app:app --reload --host 127.0.0.1 --port 8000
```

Swagger UI opens at `http://127.0.0.1:8000/docs`.

---

## API Endpoints

### `GET /health`

Returns module availability. Frontends should call this on startup to discover which features are live.

**Response** `200`

```json
{
  "status": "ok",
  "version": "1.0.0",
  "modules": {
    "recommendation": "stable",
    "recognition": "not_implemented",
    "composition": "not_implemented"
  }
}
```

---

### `POST /recommend`

Recommend songs from natural-language input.

**Request**

```json
{
  "user_input": "加班到凌晨，不想听太吵的歌"
}
```

| Field | Type | Required | Notes |
|-------|------|----------|-------|
| `user_input` | `string` | Yes | 1–2000 characters |

**Response** `200`

```json
{
  "success": true,
  "module": "recommendation",
  "query": "加班到凌晨，不想听太吵的歌",
  "intent": {
    "emotion": ["疲惫", "压抑"],
    "scene": ["深夜", "独处"],
    "listener_need": ["放松", "安静陪伴"],
    "energy_level": "low",
    "avoid": ["吵闹", "节奏快"],
    "free_text": "用户感到疲惫、压抑，正处于深夜、独处的场景中，需要放松、安静陪伴的音乐……"
  },
  "recommendations": [
    {
      "title": "夜曲",
      "artist": "周杰伦",
      "album": "十一月的萧邦",
      "year": "2005",
      "genre": "流行",
      "reason": "夜的静谧与钢琴的温柔交织，像一杯温水，安抚你疲惫的神经",
      "distance": 0.4231
    }
  ],
  "response": "加班到凌晨的滋味我太懂了……希望这些旋律能让你紧绷的肩膀慢慢放松下来。",
  "timing": {
    "total_s": 3.52,
    "planner_s": 0.82,
    "retriever_s": 0.14,
    "reranker_s": 2.10,
    "response_s": 0.45
  },
  "metadata": {
    "candidate_count": 15,
    "result_count": 5,
    "cache_info": { "size": 3, "hits": 1, "misses": 2, "max_size": 1000, "ttl_s": 1800 }
  }
}
```

**`CacheInfo` is `null` when caching is disabled.** The `recommendations` array always contains up to 5 songs.

**Error** (example: validation)

```json
{
  "success": false,
  "module": "backend",
  "error": "Request validation failed",
  "detail": "body → user_input: Field required"
}
```

**Error** (example: pipeline failure)

```json
{
  "success": false,
  "module": "backend",
  "error": "Recommendation pipeline failed",
  "detail": "Reranker API returned empty content after 2 retries"
}
```

Always check `success` before consuming the response. Errors on `/recommend` return HTTP `400`; validation errors return `422`; unexpected server errors return `500`.

---

### `POST /feedback`

Submit per-song ratings for a previous recommendation.

**Request**

```json
{
  "user_query": "加班到凌晨，不想听太吵的歌",
  "song_titles": ["夜曲", "平凡之路", "安和桥", "晚风", "无问"],
  "ratings": {
    "夜曲": "like",
    "平凡之路": "dislike"
  },
  "comment": "夜曲真的很适合深夜听"
}
```

| Field | Type | Required | Notes |
|-------|------|----------|-------|
| `user_query` | `string` | Yes | Original user input |
| `song_titles` | `string[]` | Yes | Song titles from the recommendation |
| `ratings` | `object` | No | `"like"` / `"dislike"` / `"neutral"` keyed by song title |
| `comment` | `string` | No | Free-text comment |

**Response** `200`

```json
{
  "success": true,
  "module": "feedback",
  "message": "Feedback recorded. Thank you!"
}
```

---

### `POST /recognition` (placeholder)

Returns HTTP `501 Not Implemented`. Reserved for the future Music Recognition module.

### `POST /composition` (placeholder)

Returns HTTP `501 Not Implemented`. Reserved for the future AI Composition module.
