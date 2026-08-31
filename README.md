# 🎵 Lyra

> 你的 AI 音乐伙伴 — 听歌识曲、懂你推荐、为你造歌。

「智理杯」智能体大赛参赛作品。

Lyra 是一个 AI 音乐智能体（Agent）。它不靠关键词匹配，而是先**理解你的情绪与处境**，再从音乐知识库中推荐真正合适的歌；听到一段旋律，它能告诉你这是什么歌；给它一句灵感，它能帮你把歌做出来。

---

## ✨ 三大核心能力

### 🎧 懂你的推荐
不说"风格"，只聊感觉。

> "加班到凌晨，不想听太吵的歌，但又不想让自己太低落，希望有一首安静的歌"

Lyra 先读懂你的情绪与处境，像朋友一样回应你，然后从 **395 首精选中外歌曲**（中文 276 / 英文 119）中挑出 5 首——每一首都附带一段为你此刻心情写的推荐理由。听完觉得"很懂"或"不太对"，点 👍 / 👎 告诉它，让 Lyra 下次更懂你。

### 🎤 听歌识曲
上传一段音频（mp3 / wav / flac / ogg / m4a），Lyra 调用云端识曲引擎，几秒内告诉你歌名、歌手、专辑、发行日期，甚至这段音频对应歌曲的**匹配位置**和**置信度**。

> ⚠️ 受识曲引擎曲库限制，目前暂不支持华语歌曲的识别。

### 🎶 AI 作曲
用文字描述灵感：

> "请创作一首关于夏夜校园的中文流行歌曲，整体温柔、青春、治愈，副歌要有明显的旋律记忆点。"

还可以指定时长（30–240 秒）、曲风、节奏（BPM）与调性。Lyra 调用音乐生成模型把旋律做出来，直接在页面里播放。

---

## 🚀 快速开始

### 环境要求

| 依赖 | 说明 |
|---|---|
| Python 3.11 | 项目已验证版本 |
| DeepSeek API Key | 意图理解 / 精排 / 对话生成 |
| AudD API Token | 听歌识曲 |
| 火山引擎 AccessKey | AI 作曲 |

### 1. 安装依赖

```bash
python -m venv .venv
.venv\Scripts\activate        # Windows
pip install -r requirements.txt
```

### 2. 配置密钥

```bash
copy .env.example .env
```

编辑 `.env`，填入 DeepSeek API Key、AudD Token、火山引擎 AK/SK。各字段实测时需向开发人员获取。

### 3. 构建向量索引（首次）

```bash
python src/build_index.py
```

首次运行会下载 BGE-M3 模型，需要网络。

### 4. 一键启动

```bash
start.bat
```

脚本会启动 FastAPI 后端（默认 `http://127.0.0.1:8000`）并自动打开前端页面。

- 健康检查：`http://127.0.0.1:8000/health`
- 交互式 API 文档：`http://127.0.0.1:8000/docs`

也可以分别启动：`start_backend.bat`（后端）、`start_frontend.bat`（前端）。
---

## 🧠 技术架构

![Lyra 系统架构图](docs/architecture_diagram.png)

```text
frontend/index.html        前端：原生 HTML/CSS/JS 单页应用，无需构建
        │  HTTP / JSON
        ▼
FastAPI 后端               backend/  ·  端口 8000
        │
        ├── POST /recommend ──►  LyraAgent 智能体编排 (src/agent.py)
        │                          ├─ Planner      意图理解（DeepSeek）
        │                          ├─ Retriever    语义召回（BGE-M3 + ChromaDB）
        │                          ├─ Reranker     智能精排（DeepSeek）
        │                          └─ LLMResponse  共情式回复（DeepSeek，模板降级兜底）
        │
        ├── POST /recognition ►  识曲服务 (src/recognition/) ──► AudD 云端识曲 API
        │
        ├── POST /composition ─► 作曲服务 (src/composition/) ─► 火山引擎音乐生成 OpenAPI
        │
        └── POST /feedback ───►  反馈持久化（JSONL，为个性化推荐积累数据）
```

### 推荐 Pipeline

一次推荐请求的完整流程：

1. **Planner（意图理解）**：DeepSeek 从自然语言中提取情绪、场景、偏好与"排除项"；
2. **Retriever（语义召回）**：BGE-M3 将用户意图与歌曲语义描述向量化，ChromaDB 召回候选集；
3. **Reranker（智能精排）**：DeepSeek 综合语义相关度重排，支持排除项过滤与多样性控制；
4. **LLMResponse（回复生成）**：生成自然、有温度的推荐理由；LLM 不可用时自动降级到模板回复，保证服务可用。

### 音乐知识库

`songs.json` 是推荐模块的知识源：395 首歌曲均带人工整理的结构化语义标注——主题、情绪、适用场景、听众需求、能量值（energy level）、情绪效价（valence）、推荐理由等，让"语义理解"有据可依。

### 技术栈

| 层 | 技术 |
|---|---|
| 后端 | Python 3.11 · FastAPI · uvicorn |
| 大模型 | DeepSeek（deepseek-chat） |
| 语义检索 | BGE-M3（sentence-transformers）· ChromaDB |
| 听歌识曲 | AudD 云端识曲 API |
| AI 作曲 | 火山引擎音乐生成 OpenAPI（GenSongForTime + QuerySong 轮询） |
| 前端 | 原生 HTML / CSS / JavaScript，零构建 |

---

## 🔌 API 一览

| 方法 | 路径 | 功能 |
|---|---|---|
| GET | `/health` | 服务健康检查 |
| POST | `/recommend` | 自然语言 → 歌曲推荐 |
| POST | `/recognition` | 音频文件 → 识曲结果 |
| POST | `/composition` | 文字灵感 → 生成歌曲 |
| POST | `/feedback` | 提交用户反馈 |

详细请求/响应格式见 [docs/API_SPEC.md](docs/API_SPEC.md)，架构设计见 [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md)。

---

## 📁 项目结构

```text
THU_zhili2026_TeamWahaha/
├── src/                    # 核心业务逻辑
│   ├── agent.py            #   LyraAgent 智能体编排
│   ├── planner.py          #   意图理解
│   ├── retriever.py        #   BGE-M3 + ChromaDB 语义检索
│   ├── reranker.py         #   DeepSeek 智能精排
│   ├── response_llm.py     #   LLM 回复（response.py 为模板降级）
│   ├── feedback.py         #   反馈持久化
│   ├── build_index.py      #   向量索引构建
│   ├── recognition/        #   识曲模块（service + providers）
│   └── composition/        #   作曲模块（火山引擎 OpenAPI）
├── backend/                # FastAPI 服务层（app + models + routers）
├── frontend/               # 前端单页应用（index.html）
├── static/generated/       # 生成的音频（运行时产生）
├── songs.json              # 音乐知识库（395 首）
├── docs/                   # 技术文档（API / 架构 / 前端集成）
├── start.bat               # 一键启动前后端
├── requirements.txt
└── .env.example            # 环境变量模板
```

---

## 🗺️ 后续计划

- 打磨演示体验与错误兜底
- 扩展识曲曲库，支持华语歌曲识别
- 基于已积累的用户反馈（JSONL）做个性化推荐
- 识曲结果与推荐链路联动（识别后顺势推荐相似歌曲）

---

## 🧑‍🤝‍🧑 团队

一群喜欢音乐和代码的人，在 Vibe Coding 搞事情。

---

## 📜 License

MIT
