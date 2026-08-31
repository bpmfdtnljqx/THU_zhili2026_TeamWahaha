# 🎵 Lyra

> Lyra — 你的 AI 音乐伙伴：听歌识曲、懂你推荐、为你造歌。
>
> 「智理杯」智能体大赛参赛作品。

---

## 项目目标

Lyra 是一个 AI 音乐智能体（Agent）。核心不是简单的关键词匹配，而是先理解用户的情绪、处境、场景与音乐需求，再提供合适的音乐服务。

当前平台包含三个核心能力：

1. **Recommendation**：理解用户状态并进行语义音乐推荐
2. **Recognition**：上传音频并调用云端 AudD 识曲 API
3. **Composition**：根据文字灵感调用火山引擎音乐生成 OpenAPI 创作歌曲

项目当前处于**比赛准备与稳定性打磨阶段**。

---

## 当前项目状态

### Module 1: Recommendation（COMPLETE）

推荐系统是 Lyra 的核心 Agent 流程：

```text
用户自然语言
    ↓
Planner
    ↓
Retriever
    ↓
Reranker
    ↓
LLMResponse
    ↓
推荐结果 + 自然语言回复
```

核心组件：

- **Planner**：使用 DeepSeek 从自然语言中提取 `emotion / scene / listener_need / energy_level / avoid / free_text`。
- **Retriever**：使用 BGE-M3 + ChromaDB 进行语义召回。
- **Reranker**：使用 DeepSeek 进行智能精排，支持排除项过滤与多样性控制。
- **LLMResponse**：生成自然、有温度的推荐回复；失败时降级到模板 `Response`。
- **FeedbackStore**：将用户反馈以 JSONL 形式持久化。
- **Cache**：Reranker 使用 LRU + TTL 缓存。
- **Benchmark**：支持性能、质量、多样性和 LLM Judge 等评估。

**不要重写已经稳定工作的 Recommendation Pipeline。**

### Module 2: Recognition（INTEGRATED）

识曲模块当前使用 **AudD API**：

```text
POST /recognition
    ↓
src/recognition/service.py
    ↓
AudD provider
    ↓
AudD 云端 API
    ↓
统一识曲结果
```

稳定接口：

```python
recognize(audio_file, filename) -> dict
```

至少返回：

```text
title
artist
confidence
match_offset_secs
```

服务层通过 provider 抽象隔离具体识曲引擎。

> `auris-engine/` 属于旧的/外部的识曲实现，不是当前 Lyra 识曲主链路。未经明确要求不要修改或重新引入它。

### Module 3: Composition（INTEGRATED）

作曲模块已经接入火山引擎音乐生成 OpenAPI。

工作流：

```text
POST /composition
    ↓
Composer.generate()
    ↓
GenSongForTime
    ↓
TaskID
    ↓
QuerySong（轮询）
    ↓
Status = 2
    ↓
SongDetail.AudioUrl
    ↓
下载到 static/generated/
    ↓
返回 /static/generated/<uuid>.mp3
    ↓
浏览器播放
```

任务状态：

```text
0 = 等待中
1 = 处理中
2 = 成功
3 = 失败
```

当前默认配置：

```text
Action       = GenSongForTime
Version      = 2024-08-12
ModelVersion = v4.3
Region       = cn-beijing
Service      = imagination
```

稳定接口：

```python
generate(
    prompt,
    duration,
    style,
    tempo,
    key,
) -> {
    "audio_url": "...",
    "duration": ...
}
```

当前生成时长：

```text
30–240 秒
```

---

## 核心架构

```text
Frontend
    │
    ▼
FastAPI Backend
    │
    ├── /recommend
    │      └── LyraAgent
    │            ├── Planner       → DeepSeek
    │            ├── Retriever     → BGE-M3 + ChromaDB
    │            ├── Reranker      → DeepSeek
    │            └── LLMResponse   → DeepSeek
    │
    ├── /recognition
    │      └── Recognition service → AudD API
    │
    ├── /composition
    │      └── Composition service → Volcengine Music API
    │
    └── /feedback
           └── JSONL persistence
```

### 前端

`frontend/index.html` 是原生 HTML / CSS / JavaScript 单页应用，无构建步骤。

前端负责：

- 用户输入
- 调用后端 REST API
- 推荐结果展示
- 音频上传与识曲
- 生成歌曲播放
- 用户反馈

**不要把核心业务逻辑直接放入 frontend。**

---

## 开发原则

### 1. Semantic Retrieval

推荐系统禁止退化成简单关键词匹配。

推荐应优先使用：

```text
自然语言
→ 意图理解
→ 语义嵌入
→ 向量检索
→ AI 重排序
```

---

### 2. Agent First

Lyra 是 AI Agent。

业务逻辑保持在 `src/` 与 service/provider 层；FastAPI 负责 HTTP 封装；frontend 负责展示与交互。

不要在 frontend 中实现：

- 情绪分析
- 推荐决策
- 第三方 AI API 调用
- 模型业务逻辑

---

### 3. Stable Interfaces

除非有明确需求，不要随意修改：

```text
GET  /health
POST /recommend
POST /recognition
POST /composition
POST /feedback
```

以及：

```python
recognize(audio_file, filename)
generate(prompt, duration, style, tempo, key)
```

更换具体模型或 API 时，应优先修改 service/provider 层。

---

### 4. External API Isolation

当前外部 AI 能力：

```text
DeepSeek
    → Recommendation

AudD
    → Recognition

Volcengine Music OpenAPI
    → Composition
```

第三方服务必须通过对应模块封装。

**API Key、AccessKey、SecretKey 绝不能进入 frontend。**

---

### 5. Secrets

真实密钥只放在：

```text
.env
```

Git 中只提交：

```text
.env.example
```

`.env` 必须被 `.gitignore` 忽略。

---

### 6. Music Knowledge Base

`songs.json` 是 Recommendation 的知识源。

不要自动覆盖或重写 `songs.json`。

---

### 7. Simplicity

优先使用现有：

- Python
- FastAPI
- 原生 frontend
- 现有 service/provider 抽象

不要为了小需求引入新的大型框架。

**避免过度工程化。**

---

### 8. Reliability

外部 API 可能失败。

各模块应：

- 有明确错误处理
- 避免外部服务异常导致整个 backend 崩溃
- 尽可能优雅降级
- 保持 API 返回结构稳定
- 记录必要日志

---

### 9. Incremental Changes

优先：

```text
小改动
→ 测试
→ 再继续
```

不要在没有明确要求的情况下大规模重写稳定模块。

---

## 禁止事项

未经明确要求，不要：

- 重写 Recommendation Pipeline
- 用关键词匹配替代语义检索
- 修改稳定 REST API contract
- 修改 `Composer.generate()` / `Recognizer.recognize()` 的接口契约
- 把业务逻辑移到 frontend
- 把第三方密钥放到前端
- 自动覆盖 `songs.json`
- 将运行时生成的 MP3 提交到 Git
- 将 `.env` 提交到 Git
- 重新引入已废弃的 Auris 主链路
- 修改 `auris-engine/` 以恢复旧架构
- 为已有功能引入不必要的新框架
- 在没有测试的情况下进行大规模重构

---

## 修改指南

### Recommendation

优先修改：

```text
src/agent.py
src/planner.py
src/retriever.py
src/reranker.py
src/response_llm.py
src/response.py
```

保持：

```text
Planner → Retriever → Reranker → LLMResponse
```

### Recognition

优先修改：

```text
src/recognition/service.py
src/recognition/providers/audd.py
```

保持：

```python
recognize(audio_file, filename)
```

### Composition

优先修改：

```text
src/composition/service.py
```

保持：

```python
generate(prompt, duration, style, tempo, key)
```

router 和 frontend 不应直接了解火山引擎 API 的签名、TaskID 或 QuerySong 细节。

---

## 运行时文件

以下默认不要提交：

```text
.env
venv/
.venv/
__pycache__/
chroma_db/
feedback.jsonl
static/generated/
*.mp3
*.wav
```

Recommendation 索引通过：

```bash
python src/build_index.py
```

构建。

---

## 常用启动方式

### 推荐

项目根目录：

```text
start.bat
```

用于一键启动前后端并自动打开浏览器。

### 手动

```bat
venv\Scriptsctivate
uvicorn backend.app:app --reload
```

前端：

```bat
python -m http.server 5500 --directory frontend
```

---

## 环境要求

推荐：

```text
Python 3.11
```

安装依赖：

```bash
pip install -r requirements.txt
```

首次使用 Recommendation：

```bash
python src/build_index.py
```

---

## 比赛阶段优先级

当前重点：

```text
稳定性
>
可靠性
>
完整演示
>
文档
>
新功能
```

比赛前优先确保：

1. Recommendation 稳定运行
2. Recognition 正常调用 AudD
3. Composition 正常生成并播放歌曲
4. `start.bat` 可以降低启动复杂度
5. README / SETUP_Guide / CLAUDE.md 与当前代码保持一致

---

## 项目结构

```text
THU_zhili2026_TeamWahaha/
├── src/
│   ├── agent.py
│   ├── planner.py
│   ├── retriever.py
│   ├── reranker.py
│   ├── reranker_cache.py
│   ├── response_llm.py
│   ├── response.py
│   ├── feedback.py
│   ├── logger.py
│   ├── api.py
│   ├── build_index.py
│   ├── benchmark.py
│   ├── recognition/
│   │   ├── service.py
│   │   └── providers/
│   │       └── audd.py
│   └── composition/
│       └── service.py
│
├── backend/
│   ├── app.py
│   ├── models.py
│   ├── exception_handlers.py
│   ├── smoke_test.py
│   └── routers/
│       ├── recommend.py
│       ├── feedback.py
│       ├── recognition.py
│       └── composition.py
│
├── frontend/
│   └── index.html
├── static/
│   └── generated/
├── songs.json
├── docs/
├── requirements.txt
├── SETUP_Guide.md
├── PROJECT_RECORD.md
├── start.bat
├── .env.example
└── .gitignore
```

---

## 总原则

Lyra 的目标不是堆叠 API，而是维持清晰的音乐 Agent 架构：

```text
理解用户
   ↓
AI Agent 决策
   ↓
调用合适的音乐能力
   ↓
稳定地返回结果
```

任何修改首先检查：

```text
是否破坏已有接口？
是否破坏 Recommendation Pipeline？
是否增加不必要复杂度？
是否影响比赛演示稳定性？
是否需要同步更新文档？
```

**稳定架构 > 大规模重构**

**可靠集成 > 不必要的新功能**
