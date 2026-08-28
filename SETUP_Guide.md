# Lyra 项目接手与部署指南

> Lyra — AI Music Companion  
> 当前模块：Recommendation / Recognition / Composition

---

## 1. 项目概览

Lyra 是一个 AI 音乐助手，目前包含三个模块：

| 模块 | 状态 | 说明 |
|---|---|---|
| Recommendation | ✅ 已完成 | 语义理解用户情绪与场景，并进行歌曲推荐 |
| Recognition | ✅ 已完成 | 通过识曲 provider 调用云端识曲服务 |
| Composition | ✅ 已完成 | 通过火山引擎音乐 OpenAPI 生成歌曲并在前端播放 |

### 当前运行架构

```text
浏览器（frontend/index.html）
        │
        │ HTTP
        ▼
FastAPI 后端（port 8000）
        │
        ├── /recommend
        │      ├── DeepSeek API
        │      └── BGE-M3 + ChromaDB
        │
        ├── /recognition
        │      └── Recognition Provider
        │
        └── /composition
               └── 火山引擎音乐 OpenAPI
                    ├── GenSongForTime
                    └── QuerySong
```

### 作曲模块工作流

```text
用户输入 prompt
      ↓
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

火山引擎接口的歌曲生成任务状态为：

```text
0 = 等待中
1 = 处理中
2 = 成功
3 = 失败
```

---

## 2. 环境要求

### 必须

| 工具 | 推荐版本 | 说明 |
|---|---|---|
| Python | **3.11** | 项目已验证版本；不要直接使用 Python 3.14 |
| Git | 任意新版本 | 用于拉取和提交仓库 |
| DeepSeek API Key | — | Recommendation 模块使用 |
| 火山引擎 AccessKey ID / Secret Access Key | — | Composition 模块使用 |

> ⚠️ 不建议把 Python 3.14 直接用于本项目。当前项目依赖组合已经按照 Python 3.11 验证。

### 可选

| 工具 | 说明 |
|---|---|
| Docker + Docker Compose | 如果当前分支需要运行 Auris/其他独立服务 |
| Node.js + pnpm | 仅在需要开发相关前端工程时使用 |

---

## 3. 获取代码

```bash
git clone <你的私有仓库地址>
cd lyra
```

查看当前分支：

```bash
git branch --show-current
```

查看远程仓库：

```bash
git remote -v
```

---

## 4. 创建 Python 虚拟环境

Windows：

```bat
py -3.11 -m venv .venv
.venv\Scripts\activate
```

也可以：

```bat
python -m venv .venv
.venv\Scripts\activate
```

确认版本：

```bat
python --version
```

应该看到：

```text
Python 3.11.x
```

升级 pip：

```bat
python -m pip install --upgrade pip
```

安装依赖：

```bat
pip install -r requirements.txt
```

---

## 5. 配置 `.env`

在项目根目录创建：

```text
.env
```

不要把 `.env` 提交到 Git。

推荐内容：

```env
# =========================
# DeepSeek
# =========================

DEEPSEEK_API_KEY=sk-你的密钥
DEEPSEEK_BASE_URL=https://api.deepseek.com
DEEPSEEK_MODEL=deepseek-chat

# 国内网络环境可使用 HuggingFace 镜像
HF_ENDPOINT=https://hf-mirror.com


# =========================
# Volcengine Music API
# =========================

VOLC_ACCESS_KEY_ID=你的AccessKeyID
VOLC_SECRET_ACCESS_KEY=你的SecretAccessKey

VOLC_HOST=open.volcengineapi.com
VOLC_REGION=cn-beijing
VOLC_SERVICE=imagination

# 后付费账号使用 GenSongForTime
VOLC_SONG_ACTION=GenSongForTime
VOLC_SONG_VERSION=2024-08-12

# 当前项目默认使用 v4.3
VOLC_MODEL_VERSION=v4.3

# Composition task polling
VOLC_POLL_INTERVAL=2
VOLC_TASK_TIMEOUT=240

# Generated audio
LYRA_GENERATED_DIR=static/generated
```

### 火山引擎 AK/SK 注意事项

Composition 使用的是火山引擎 OpenAPI 的 **AccessKey ID + Secret Access Key**，不是其他产品的 API Key。

公共鉴权参数：

```text
Host      = open.volcengineapi.com
Region    = cn-beijing
Service   = imagination
```

签名使用 HMAC-SHA256。

---

## 6. Recommendation 向量索引

如果仓库中没有：

```text
chroma_db/
```

先执行：

```bash
python src/build_index.py
```

第一次运行 BGE-M3 时可能需要下载模型，因此第一次初始化可能需要网络。

生成后的：

```text
chroma_db/
```

属于运行时生成目录，不应提交到 Git（除非团队明确决定把索引作为版本资产保存）。

---

## 7. 启动后端

项目根目录执行：

```bash
uvicorn backend.app:app --reload
```

默认地址：

```text
http://127.0.0.1:8000
```

API 文档：

```text
http://127.0.0.1:8000/docs
```

健康检查：

```text
http://127.0.0.1:8000/health
```

正常情况下应该看到：

```json
{
  "status": "ok",
  "version": "1.0.0",
  "modules": {
    "recommendation": "stable",
    "recognition": "stable",
    "composition": "stable"
  }
}
```

---

## 8. 启动前端

前端是纯 HTML/CSS/JS，无需构建。

最简单的方式：

直接打开：

```text
frontend/index.html
```

页面默认请求：

```text
http://127.0.0.1:8000
```

也可以通过 URL 参数指定后端地址：

```text
frontend/index.html?api=http://127.0.0.1:8000
```

### 作曲音频为什么可以直接播放？

Composition service 会把火山引擎返回的音频下载到：

```text
static/generated/
```

FastAPI 会把：

```text
/static/*
```

映射到这个目录。

因此生成后的歌曲类似：

```text
static/generated/2d0c....mp3
```

浏览器访问：

```text
http://127.0.0.1:8000/static/generated/2d0c....mp3
```

---

## 9. Composition 使用方式

进入前端：

```text
🎹 Compose
```

填写：

```text
Prompt:
请创作一首关于夏夜校园的中文流行歌曲，整体温柔、青春、治愈，
副歌要有明显的旋律记忆点。

Duration:
30

Style:
pop

Tempo:
90

Key:
C major
```

点击：

```text
Generate
```

正常流程：

```text
GenSongForTime
    ↓
TaskID
    ↓
QuerySong
    ↓
Status = 0 / 1
    ↓
继续轮询
    ↓
Status = 2
    ↓
AudioUrl
    ↓
下载 mp3
    ↓
浏览器播放
```

当前火山音乐接口要求生成时长为：

```text
30–240 秒
```

所以 Lyra 的 Composition API 和前端也采用这个范围。

---

## 10. Composition 参数说明

Lyra API：

```http
POST /composition
Content-Type: application/json
```

请求：

```json
{
  "prompt": "一首关于夏夜校园的温柔中文流行歌曲",
  "duration": 60,
  "style": "pop",
  "tempo": 90,
  "key": "C major"
}
```

字段：

| 字段 | 必填 | 说明 |
|---|---|---|
| prompt | ✅ | 音乐内容、情绪、场景等 |
| duration | 否 | 30–240 秒 |
| style | 否 | 曲风描述 |
| tempo | 否 | BPM |
| key | 否 | 如 `C major`、`A# minor` |

为了避免用户自由输入的 `style / tempo / key` 与火山模型内部枚举不一致，当前 Composition service 会把这些条件安全地融合进 Prompt，而不是强行传给严格枚举字段。

因此类似：

```text
style = pop
tempo = 90
key = C major
```

最终会作为创作要求的一部分传给模型。

---

## 11. Recommendation

请求：

```http
POST /recommend
Content-Type: application/json
```

示例：

```json
{
  "user_input": "加班到凌晨，不想听太吵的歌"
}
```

系统流程：

```text
用户自然语言
    ↓
Planner
    ↓
Intent
    ↓
BGE-M3 + ChromaDB
    ↓
Reranker
    ↓
Response LLM
    ↓
推荐结果
```

---

## 12. Recognition

前端选择：

```text
🎤 Recognize
```

上传：

```text
mp3 / wav / flac / ogg / m4a
```

然后点击：

```text
Recognize
```

Recognition API：

```http
POST /recognition
Content-Type: multipart/form-data
```

---

## 13. Git 忽略文件

至少确保 `.gitignore` 中包含：

```gitignore
# Secrets
.env
.env.*
!.env.example

# Python
.venv/
__pycache__/
*.py[cod]

# Vector database
chroma_db/

# Runtime logs / user feedback
feedback.jsonl

# Generated audio
static/generated/
*.mp3
*.wav

# IDE
.vscode/
.idea/

# OS
.DS_Store
Thumbs.db
```

> 即使仓库是私有的，也建议不要提交真实 AK/SK 和 DeepSeek Key。这样可以避免未来仓库改为公开、转移仓库或误 push 到其他远程时发生密钥泄露。

---

## 14. 推荐提交到仓库的文件

应该提交：

```text
src/composition/service.py
backend/app.py
backend/models.py
backend/routers/composition.py
frontend/index.html
requirements.txt
SETUP_Guide.md
.env.example
.gitignore
```

不要提交：

```text
.env
.venv/
chroma_db/
static/generated/
feedback.jsonl
```

---

## 15. `.env.example`

推荐在仓库根目录提交：

```env
DEEPSEEK_API_KEY=your_deepseek_api_key
DEEPSEEK_BASE_URL=https://api.deepseek.com
DEEPSEEK_MODEL=deepseek-chat
HF_ENDPOINT=https://hf-mirror.com

VOLC_ACCESS_KEY_ID=your_volcengine_access_key_id
VOLC_SECRET_ACCESS_KEY=your_volcengine_secret_access_key
VOLC_HOST=open.volcengineapi.com
VOLC_REGION=cn-beijing
VOLC_SERVICE=imagination
VOLC_SONG_ACTION=GenSongForTime
VOLC_SONG_VERSION=2024-08-12
VOLC_MODEL_VERSION=v4.3

VOLC_POLL_INTERVAL=2
VOLC_TASK_TIMEOUT=240
LYRA_GENERATED_DIR=static/generated
```

队友配置时：

```text
.env.example
    ↓ copy
.env
    ↓
填自己的 Key
```

Windows CMD：

```bat
copy .env.example .env
```

PowerShell：

```powershell
Copy-Item .env.example .env
```

---

## 16. 常见问题

### `InvalidAccessKey`

例如：

```text
HTTP 401
InvalidAccessKey
```

优先检查：

1. `VOLC_ACCESS_KEY_ID` 是否真的是火山 AccessKey ID。
2. `VOLC_SECRET_ACCESS_KEY` 是否对应同一组密钥。
3. 不要把其他产品的 API Key 当作 AK。
4. `.env` 修改后重启 uvicorn。

---

### `InvalidRequestParams`

检查：

1. `VOLC_MODEL_VERSION=v4.3`
2. Duration 是否在 30–240。
3. AK/SK 已经能够通过鉴权。
4. 如果只是想先测试生成，可以只填 Prompt + Duration，Style / Tempo / Key 留空。

---

### 生成成功但播放器显示 `0:00`

检查：

```text
http://127.0.0.1:8000/static/generated/
```

对应的 MP3 是否实际存在。

如果 MP3 存在，检查前端是否使用最新版 `index.html`。

当前前端已经会将：

```text
/static/generated/xxx.mp3
```

自动拼接为：

```text
http://127.0.0.1:8000/static/generated/xxx.mp3
```

---

### Backend status 中没有 Composition

检查 `backend/app.py` 的 `/health` 是否返回：

```json
"composition": "stable"
```

---

## 17. 团队第一次运行的最短流程

```bat
git clone <仓库地址>
cd lyra

py -3.11 -m venv .venv
.venv\Scripts\activate

pip install -r requirements.txt

copy .env.example .env
```

编辑 `.env`：

```text
填 DeepSeek API Key
填 Volcengine AK/SK
```

然后：

```bat
python src/build_index.py
uvicorn backend.app:app --reload
```

最后打开：

```text
frontend/index.html
```

---

## 18. 当前项目关键文件

```text
lyra/
├── src/
│   ├── agent.py
│   ├── planner.py
│   ├── retriever.py
│   ├── reranker.py
│   ├── response_llm.py
│   ├── response.py
│   ├── feedback.py
│   ├── build_index.py
│   ├── recognition/
│   └── composition/
│       └── service.py        ← 火山音乐 API
│
├── backend/
│   ├── app.py                ← FastAPI + /static
│   ├── models.py
│   └── routers/
│       └── composition.py
│
├── frontend/
│   └── index.html
│
├── static/
│   └── generated/            ← 运行时生成，不提交 Git
│
├── chroma_db/                ← 构建后生成，不提交 Git
├── .env                      ← 本地密钥，不提交 Git
├── .env.example
├── requirements.txt
└── SETUP_Guide.md
```

---

## 19. 当前已验证功能

截至当前版本：

```text
✅ Recommendation
✅ Recognition
✅ Composition
✅ Volcengine music task creation
✅ QuerySong polling
✅ Audio download
✅ FastAPI static audio serving
✅ Browser audio playback
```
