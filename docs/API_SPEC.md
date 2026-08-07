# Lyra API Specification

> Version: 1.1
> Date: 2026-08-07
> Status: **Recommendation — Stable. Recognition / Composition — Placeholder (200 OK).**

---

## Design Principles

1. **Stable interfaces.** Once a module reaches v1.0, its public contract is frozen. New fields may be added, but existing fields will not be removed or renamed without a major version bump.

2. **Backward compatibility.** Consumers written against v1.0 will continue to work with all v1.x releases.

3. **JSON-first.** All module inputs and outputs are JSON-serializable. No binary blobs, no pickle, no platform-specific types.

4. **Module independence.** Each module (Recommendation, Recognition, Composition) is independently developed and deployed. They share common response conventions but have no runtime dependencies on each other.

5. **Errors are in-band.** Errors are reported via `success: false` and an `error` field in the standard response envelope, not via HTTP status codes or exceptions. This keeps the contract transport-agnostic.

---

## Common Response Conventions

Every module response shares a common envelope:

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `success` | `bool` | Always | `true` if the request completed normally |
| `module` | `string` | Always | Module name: `"recommendation"`, `"recognition"`, `"composition"` |
| `error` | `string` | On failure | Human-readable error description (present only when `success` is `false`) |
| `timing` | `object` | Always | Timing breakdown (see below) |
| `metadata` | `object` | When available | Module-specific metadata (cache info, counts, model versions, etc.) |

### Timing Object

Every response includes a `timing` object with at least:

| Field | Type | Description |
|-------|------|-------------|
| `total_s` | `float` | Total wall-clock time in seconds |

Module-specific timing fields (e.g., `planner_s`, `reranker_s`) are documented per-module.

---

## Recommendation

**Status:** Stable (v1.0).

**Purpose:** Given a user's natural-language description of their mood, situation, or listening needs, return a ranked list of song recommendations with personalized reasons and a natural-language response.

### Input

A single function call:

```
recommend(user_input: str) -> dict
```

| Parameter | Type | Description |
|-----------|------|-------------|
| `user_input` | `string` | Free-form natural language. Examples: "失恋了，下雨的夜晚想一个人静静", "周末早晨阳光很好，想去公园跑步" |

No additional parameters are required. The pipeline handles intent extraction, retrieval, ranking, and response generation automatically.

### Output

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
    "free_text": "用户感到疲惫、压抑，正处于深夜、独处的场景中，需要放松、安静陪伴的音乐，希望听到安静舒缓的音乐。不想听到吵闹、节奏快风格的歌曲。用户说：「加班到凌晨，不想听太吵的歌」"
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
    },
    {
      "title": "平凡之路",
      "artist": "朴树",
      "album": "猎户星座",
      "year": "2014",
      "genre": "民谣摇滚",
      "reason": "低沉的嗓音与克制的编曲，适合深夜独自消化一天的疲惫",
      "distance": 0.3892
    },
    {
      "title": "安和桥",
      "artist": "宋冬野",
      "album": "安和桥北",
      "year": "2013",
      "genre": "民谣",
      "reason": "简单干净的吉他和弦，像老朋友在你身边安静地坐着",
      "distance": 0.4510
    },
    {
      "title": "晚风",
      "artist": "陈婧霏",
      "album": "晚风",
      "year": "2020",
      "genre": "独立流行",
      "reason": "温柔的嗓音像深夜的微风，轻轻拂过你紧绷的肩膀",
      "distance": 0.5123
    },
    {
      "title": "无问",
      "artist": "毛不易",
      "album": "平凡的一天",
      "year": "2018",
      "genre": "流行",
      "reason": "毛不易的歌声有一种看透世事后的平静，恰好抚慰此刻的你",
      "distance": 0.4678
    }
  ],
  "response": "加班到凌晨的滋味我太懂了——那种身体疲惫但脑子还在转的感觉。这时候不需要太用力的音乐，只要有人轻轻接住你的疲惫就好。\n\n为你找到这几首歌，它们的共同点是安静、有温度、不喧闹。周杰伦的《夜曲》像一杯温水，朴树的《平凡之路》陪你消化这一天的辛苦，宋冬野的《安和桥》简单干净，像老朋友在身边默默陪着。\n\n辛苦了。希望这些旋律能让你紧绷的肩膀慢慢放松下来。",
  "timing": {
    "total_s": 3.521,
    "planner_s": 0.823,
    "retriever_s": 0.145,
    "reranker_s": 2.103,
    "response_s": 0.450
  },
  "metadata": {
    "candidate_count": 15,
    "result_count": 5,
    "cache_info": {
      "size": 3,
      "hits": 1,
      "misses": 2,
      "max_size": 1000,
      "ttl_s": 1800
    }
  }
}
```

### Field Reference

| Field | Type | Description |
|-------|------|-------------|
| `success` | `bool` | Always `true` for completed recommendations |
| `module` | `string` | Always `"recommendation"` |
| `query` | `string` | The original user input, echoed back |
| `intent` | `object` | Structured intent extracted by the Planner |
| `intent.emotion` | `string[]` | Detected emotions (e.g., `["疲惫", "压抑"]`) |
| `intent.scene` | `string[]` | Detected scenes (e.g., `["深夜", "独处"]`) |
| `intent.listener_need` | `string[]` | Inferred listening needs (e.g., `["放松", "安静陪伴"]`) |
| `intent.energy_level` | `string` | One of `"low"`, `"medium"`, `"high"` |
| `intent.avoid` | `string[]` | Styles/emotions the user wants to avoid |
| `intent.free_text` | `string` | Natural narrative synthesized for embedding |
| `recommendations` | `object[]` | Ranked Top-5 song list |
| `recommendations[].title` | `string` | Song title |
| `recommendations[].artist` | `string` | Artist name |
| `recommendations[].album` | `string` | Album name |
| `recommendations[].year` | `string` | Release year |
| `recommendations[].genre` | `string` | Music genre |
| `recommendations[].reason` | `string` | Personalized recommendation reason (20-40 chars) |
| `recommendations[].distance` | `float` | Cosine distance from vector search (lower = more similar) |
| `response` | `string` | Natural-language response text (150-250 chars) |
| `timing.total_s` | `float` | Total pipeline wall-clock time |
| `timing.planner_s` | `float` | Planner stage duration |
| `timing.retriever_s` | `float` | Retriever stage duration |
| `timing.reranker_s` | `float` | Reranker stage duration |
| `timing.response_s` | `float` | Response generation duration |
| `metadata.candidate_count` | `int` | Number of candidates before reranking |
| `metadata.result_count` | `int` | Number of final recommendations (typically 5) |
| `metadata.cache_info` | `object\|null` | LRU cache statistics (or `null` if cache disabled) |

### Usage

**Python (direct):**

```python
from src.api import recommend

result = recommend("今天心情很低落")
print(result["response"])

for song in result["recommendations"]:
    print(f"{song['title']} — {song['artist']}: {song['reason']}")
```

**FastAPI (future):**

```python
from src.api import recommend

@app.post("/recommend")
def recommend_endpoint(request: RecommendRequest):
    return recommend(request.user_input)
```

**CLI (via chat wrapper):**

```python
from src.api import chat

text = chat("今天心情很低落")
print(text)  # display-ready string
```

---

## Recognition (Placeholder)

**Status:** Placeholder — returns an empty result via the standard response envelope. Ready for model integration.

**Purpose:** Identify a song from an uploaded audio file (mp3, wav, flac, ogg, m4a, webm).

### Input

`POST /recognition` — multipart/form-data file upload.

| Parameter | Type | Description |
|-----------|------|-------------|
| `file` | `file` (required) | Audio file. Supported formats: mp3, wav, flac, ogg, m4a, webm. |

### Output (current placeholder)

```json
{
  "success": true,
  "module": "recognition",
  "data": {
    "title": "",
    "artist": "",
    "confidence": 0.0
  },
  "message": "Recognition service placeholder"
}
```

**When real model is integrated**, `data.title`, `data.artist`, and `data.confidence` will be populated:

```json
{
  "success": true,
  "module": "recognition",
  "data": {
    "title": "夜曲",
    "artist": "周杰伦",
    "confidence": 0.95
  },
  "message": "Recognition completed"
}
```

### Integration point

Service layer: `src/recognition/service.py` → `Recognizer.recognize(audio_file, filename)`

Router: `backend/routers/recognition.py` (thin HTTP wrapper — should not need changes).

---

## Composition (Placeholder)

**Status:** Placeholder — returns an empty result via the standard response envelope. Ready for model integration.

**Purpose:** Generate original music from a text prompt with optional creative constraints.

### Input

`POST /composition` — JSON body.

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `prompt` | `string` | yes | — | Natural-language description of desired music (max 1000 chars) |
| `duration` | `int` | no | 30 | Target duration in seconds (1–300) |
| `style` | `string` | no | `null` | Musical style reference (max 200 chars) |
| `tempo` | `int` | no | `null` | BPM hint (20–300) |
| `key` | `string` | no | `null` | Musical key hint (e.g. "C major", max 30 chars) |

### Output (current placeholder)

```json
{
  "success": true,
  "module": "composition",
  "data": {
    "audio_url": null,
    "duration": 30
  },
  "message": "Composition service placeholder"
}
```

**When real model is integrated**, `data.audio_url` will point to the generated file:

```json
{
  "success": true,
  "module": "composition",
  "data": {
    "audio_url": "/static/generated/a1b2c3d4.wav",
    "duration": 28
  },
  "message": "Composition completed"
}
```

### Integration point

Service layer: `src/composition/service.py` → `Composer.generate(prompt, duration, style, tempo, key)`

Router: `backend/routers/composition.py` (thin HTTP wrapper — should not need changes).

---

## Appendix: Error Response

When a module encounters a recoverable error, it returns:

```json
{
  "success": false,
  "module": "recommendation",
  "error": "Reranker API returned empty content after 2 retries",
  "timing": {
    "total_s": 5.123
  },
  "metadata": {}
}
```

The `error` field is a human-readable string suitable for logging and debugging. It is not intended for programmatic branching — use `success` for control flow.
