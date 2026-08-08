# Lyra 环境搭建指南

> 给by饱饱和jy饱饱，让他们快速配置现在已经使用的环境。

---
# 先把最重要的放在最前边吧，deepseek专家模式不如gpt一般模式写prompt写的好，建议跟gpt提供你想干什么让他给你写prompt给Claude
---
# 记得最后把这个文档删了
## 1. 项目概览


| 模块 | 状态 | 说明 |
|---|---|---|
| **推荐（Recommendation）** | 已完成 | 语义理解用户情绪 → 智能推荐歌曲 |
| **识曲（Recognition）** | 代码已集成 | 通过 Auris 引擎进行音频指纹识别 |
| **作曲（Composition）** | 接口预留 | 等待模型接入 |

### 当前运行时架构

```
浏览器 (frontend/index.html)
    │  HTTP
    ▼
FastAPI 后端 (port 8000)
    │
    ├── /recommend   → DeepSeek API（意图理解 + 重排序 + 对话生成）
    │                   BGE-M3 + ChromaDB（语义检索）
    │
    ├── /recognition → Auris Engine (port 8001, Docker)
    │
    └── /composition → placeholder
```

- **Lyra 后端**：Python 直接运行（无 Docker）
- **Auris 引擎**：Docker Compose 启动（独立的外部服务）
- **前端**：纯 HTML/CSS/JS，无需构建，**有一种可能的更新换代方式，就是当我们的电脑都在校园网环境下时我们可以通过访问电脑的内网IP访问前端，但是我没有验证过**

---

## 2. 环境要求

### 必须

| 工具 | 版本 | 说明 |
|---|---|---|
| **Python** | **3.11** | ⚠️ 已验证版本。更高版本在某些 API 依赖/集成场景中曾出现兼容性问题，无法保证正常运行，**我们电脑上现在装的3.14不行哦** |
| **Git** | 任意 | 克隆仓库 |
| **DeepSeek API Key** | — | 这个是我注册的，点进去第一个是项目的key，第二个是vibe的key：[platform.deepseek.com/api_keys](https://platform.deepseek.com/api_keys) |

### 可选

| 工具 | 版本 | 说明 |
|---|---|---|
| **Docker + Docker Compose** | 任意 | 仅启动 Auris 识曲引擎时需要 |
| **Node.js + pnpm** | Node 20+ | 仅开发 Auris 前端时需要 |

### 已验证平台

- Windows 11

---

## 3. 项目结构

```
lyra/
├── src/                     # 核心业务逻辑
│   ├── agent.py             #   LyraAgent 编排器
│   ├── planner.py           #   意图理解（DeepSeek API）
│   ├── retriever.py         #   语义检索（BGE-M3 + ChromaDB）
│   ├── reranker.py          #   AI 重排序（DeepSeek API）
│   ├── response_llm.py      #   自然对话生成（DeepSeek API）
│   ├── response.py          #   模板降级回复
│   ├── feedback.py          #   用户反馈持久化
│   ├── build_index.py       #   构建向量索引
│   ├── recognition/         #   识曲模块
│   │   ├── service.py       #     Recognizer 引擎
│   │   └── providers/       #     引擎适配层
│   │       └── auris.py     #       Auris HTTP 通信
│   └── composition/         #   作曲模块（placeholder）
│       └── service.py
├── backend/                 # FastAPI 服务层
│   ├── app.py               #   应用工厂 + CORS
│   ├── models.py            #   Pydantic 模型
│   ├── routers/             #   API 路由
│   ├── smoke_test.py        #   冒烟测试
│   └── requirements.txt     #   后端额外依赖
├── frontend/                # 前端 Demo
│   └── index.html           #   单页应用（纯 HTML/CSS/JS，零框架）
├── auris-engine/            # Auris 指纹识别引擎（独立项目，Docker 启动）
├── docs/                    # 技术文档
├── songs.json               # 音乐知识库（170+ 首）
├── requirements.txt         # Python 依赖（推荐使用）
├── chroma_db/               # 向量数据库（生成目录，已 gitignore）
└── .env                     # 环境变量（已 gitignore）
```

### 生成目录

| 目录/文件 | 说明 | 如何生成 |
|---|---|---|
| `chroma_db/` | ChromaDB 向量索引 | `python src/build_index.py` |
| `feedback.jsonl` | 用户反馈日志 | 后端运行时自动追加 |
| `.venv/` | Python 虚拟环境 | `python -m venv .venv` |

---

## 4. 配置说明

### 4.1 Lyra 后端（`.env`）

在项目根目录创建 `.env` 文件：

```
DEEPSEEK_API_KEY=sk-你的密钥
DEEPSEEK_BASE_URL=https://api.deepseek.com
DEEPSEEK_MODEL=deepseek-chat
HF_ENDPOINT=https://hf-mirror.com
```

#### 必填

| 变量 | 说明 | 示例值 |
|---|---|---|
| `DEEPSEEK_API_KEY` | DeepSeek API 密钥。推荐、重排序、对话生成三个环节都需要 | `sk-xxxxx` |

#### 可选

| 变量 | 默认值 | 说明 |
|---|---|---|
| `DEEPSEEK_BASE_URL` | `https://api.deepseek.com` | API 地址。如使用代理或自定义端点，在此修改 |
| `DEEPSEEK_MODEL` | `deepseek-chat` | 模型名称。重排序器在失败时会自动尝试 `deepseek-reasoner` |
| `HF_ENDPOINT` | — | HuggingFace 镜像（国内建议设为 `https://hf-mirror.com`） |

> **注意**：`src/retriever.py` 在加载 BGE-M3 模型时强制使用离线模式（`HF_HUB_OFFLINE=1`），但首次下载模型时仍需网络。`HF_ENDPOINT` 主要用于 `build_index.py` 构建索引阶段。

#### 调试开关（可选）

| 变量 | 作用 |
|---|---|
| `LYRA_DEBUG=1` | 开启所有模块的调试日志（输出到 stderr） |
| `LYRA_VERBOSE=1` | Planner + Reranker 详细日志 |
| `LYRA_PLANNER_DEBUG=1` | 仅 Planner 日志 |
| `LYRA_RESPONSE_DEBUG=1` | 仅 Response 日志 |
| `LYRA_CACHE_DEBUG=1` | 仅缓存日志 |
| `LYRA_CORS_ORIGINS` | CORS 允许的域名，默认 `*` |

#### 缓存配置（可选）

| 变量 | 默认值 | 说明 |
|---|---|---|
| `LYRA_CACHE_ENABLED` | `1` | 是否启用重排序结果缓存 |
| `LYRA_CACHE_TTL` | `1800` | 缓存有效期（秒），默认 30 分钟 |
| `LYRA_CACHE_MAX_SIZE` | `1000` | 最大缓存条目数 |

#### 识曲配置（可选）

| 变量 | 默认值 | 说明 |
|---|---|---|
| `AURIS_API_URL` | `http://127.0.0.1:8001` | Auris 引擎地址。Auris 不可用时，识曲接口自动返回空结果（不报错） |

---

### 4.2 Auris 引擎（`auris-engine/.env`）

仅当需要运行识曲功能时才需配置。参考 `auris-engine/.env.example`：

| 变量 | 必填 | 说明 |
|---|---|---|
| `DATABASE_URL` | 是 | PostgreSQL 连接字符串，如 `postgres://user:pass@localhost:5432/auris` |
| `RUSTFS_ENDPOINT` | 是 | S3 兼容存储地址（Docker 内为 `http://rustfs:9000`） |
| `RUSTFS_ACCESS_KEY` | 是 | 存储访问密钥 |
| `RUSTFS_SECRET_KEY` | 是 | 存储密钥 |
| `RUSTFS_BUCKET_NAME` | 是 | 存储桶名称 |
| `POSTGRES_USER` | 是 | 数据库用户名（Docker Compose 使用） |
| `POSTGRES_PASSWORD` | 是 | 数据库密码（Docker Compose 使用） |
| `POSTGRES_DB` | 是 | 数据库名称（Docker Compose 使用） |
| `BIND_ADDR` | 否 | 服务监听地址，默认 `0.0.0.0:8000` |
| `RUST_LOG` | 否 | 日志级别，默认 `info` |
| `CORS_ALLOWED_ORIGINS` | 否 | CORS 域名，默认 `http://localhost:5173` |

Docker Compose 会自动将上述变量注入 Auris 各容器。详见 [auris-engine/README.md](auris-engine/README.md)。

---

## 5. 本地启动步骤

### 5.1 克隆仓库

```bash
git clone <repo-url>
cd lyra
```

### 5.2 创建 Python 虚拟环境

```bash
# 创建虚拟环境（必须使用 Python 3.11）
python3.11 -m venv .venv

# 激活
# Windows:
.venv\Scripts\activate
# macOS / Linux:
source .venv/bin/activate
```

### 5.3 安装依赖

```bash
# 使用根目录的 requirements.txt（推荐）
pip install -r requirements.txt

# 国内加速（清华镜像）
pip install -r requirements.txt -i https://pypi.tuna.tsinghua.edu.cn/simple
```

> `torch` 约 2.5 GB，首次安装需要几分钟。

> **关于 requirements 文件**：项目当前有两个 `requirements.txt`。根目录的版本已包含全部依赖（FastAPI + 推荐引擎 + 识曲通信），**推荐使用根目录版本**。`backend/requirements.txt` 是早期遗留，内容有重复，后续可以考虑合并或清理。

### 5.4 配置环境变量

```bash
# 在项目根目录创建 .env，填入你的 DeepSeek API Key
echo DEEPSEEK_API_KEY=sk-你的密钥 > .env
echo DEEPSEEK_BASE_URL=https://api.deepseek.com >> .env
echo DEEPSEEK_MODEL=deepseek-chat >> .env
```

> `.env` 已在 `.gitignore` 中，不会被提交。

### 5.5 构建 ChromaDB 索引

```bash
python src/build_index.py
```

这一步会：
1. 读取 `songs.json`（170+ 首歌曲）
2. 下载 BGE-M3 嵌入模型（~2 GB，仅首次）
3. 生成每条歌曲的语义向量
4. 写入 `chroma_db/` 目录

> 输出示例：`Done. 170 songs indexed in 'lyra_songs'.`

> `chroma_db/` 已在 `.gitignore` 中，每位开发者需自行构建。

### 5.6 启动后端

```bash
# 方式一：直接启动
uvicorn backend.app:app --reload --host 0.0.0.0 --port 8000

# 方式二：使用脚本（Windows）
start_backend.bat
```

启动后可见：
```
INFO:     Uvicorn running on http://127.0.0.1:8000
[retriever] INFO Loading embedding model BAAI/bge-m3...
[retriever] INFO Collection 'lyra_songs' loaded (170 songs).
```

验证：
```bash
curl http://127.0.0.1:8000/health
# {"status":"ok","version":"1.0.0","modules":{...}}
```

> API 文档：启动后访问 `http://127.0.0.1:8000/docs`（Swagger UI）

### 5.7 打开前端

当前前端是纯 HTML/CSS/JS，无需构建服务器，直接通过 `file://` 协议打开：

```bash
# 方式一：使用脚本（Windows）
start_frontend.bat

# 方式二：手动用浏览器打开
# 打开 frontend/index.html?api=http://127.0.0.1:8000
```

> 后端地址通过 URL 查询参数 `?api=...` 传入，默认 `http://127.0.0.1:8000`。
> 如需切换后端地址：`frontend/index.html?api=http://其他地址:8000`

前端健康指示器变绿表示已连接后端。

### 5.8 （可选）运行测试

```bash
# 冒烟测试：验证所有 API 端点
python backend/smoke_test.py

# 解析器单元测试
python test_planner_parse.py
python test_reranker_parse.py

# 性能基准
python src/benchmark.py --runs 3 --timing

# API 诊断工具（排查 DeepSeek 连接问题）
python diagnose_api.py
```

---

## 6. Docker 启动（Auris 识曲引擎）

### 为什么需要 Docker

Auris 引擎包含多个服务（PostgreSQL、RustFS 对象存储、Rust API 服务、前端界面），通过 Docker Compose 统一编排。Lyra 后端本身不需要 Docker，仅在需要运行识曲功能时才启动 Auris。

### 启动步骤

```bash
cd auris-engine

# 1. 配置环境变量
cp .env.example .env
# 编辑 .env，填入必要的数据库和存储配置

# 2. 启动全部服务
docker compose up -d
```

这会启动 6 个容器：

| 容器 | 端口 | 作用 |
|---|---|---|
| `auris-api` | `8001:8000` | Auris REST API（`/identify`, `/tracks`, `/health`） |
| `auris-worker` | — | 后台指纹提取任务 |
| `auris-frontend` | `8000:8080` | Auris 管理界面（React + Nginx） |
| `database` | `5432:5432` | PostgreSQL 18 |
| `storage` | `9000:9000` / `9001:9001` | RustFS 对象存储 |
| `auris-migrator` | — | 数据库迁移（一次性） |

> Auris 镜像来自 GitHub Container Registry（`ghcr.io/lessan-cyber/auris`），无需本地编译 Rust 代码。

### 验证

```bash
# Auris 健康检查
curl http://127.0.0.1:8001/health
```

### 停止

```bash
docker compose down
```

---

## 7. 常见问题

### 端口 8000 被占用

**原因**：如果同时启动了 Lyra 后端和 Auris 前端，两者都使用端口 8000。

**检查**：
```bash
# Windows
netstat -ano | findstr :8000
```

**解决**：
- **如果 Auris 不需要前端界面**：Auris API 映射到 `8001`，不会冲突。端口冲突仅发生在 Auris 前端也启动时。
- **换端口启动 Lyra**：`uvicorn backend.app:app --reload --port 8002`，然后访问 `frontend/index.html?api=http://127.0.0.1:8002`。
- **换端口启动 Auris 前端**：修改 `auris-engine/compose.yml` 中 `frontend` 服务的端口映射。

> 这是一个已知的端口分配问题。当前项目在开发中 Lyra 和 Auris 通常不会同时全量运行，因此一般不会触发。如果后续需要统一部署方案，建议重新规划端口分配。

---

### `No module named 'src.xxx'`

确保在项目根目录（`lyra/`）下运行命令，而非 `src/` 或 `backend/` 内部。后端启动时会自动将 `src/` 加入 `sys.path`。

---

### ChromaDB 加载歌曲数为 0

未构建索引或索引文件损坏：

```bash
python src/build_index.py
```

---

### DeepSeek API 报错（401 / 403 / 超时）

1. 确认 API Key 有效：https://platform.deepseek.com/api_keys
2. 检查账户余额（免费版有调用限制）
3. 运行诊断工具：`python diagnose_api.py`

> 推荐管道有完整的降级机制：API 不可用时，重排序器会自动回退到向量检索结果（无 AI 推荐理由），对话生成会自动回退到模板回复。

---

### BGE-M3 模型下载失败

设置 HuggingFace 镜像（国内环境）：
```
HF_ENDPOINT=https://hf-mirror.com
```

注意：`src/retriever.py` 在**加载**模型时强制离线模式（`HF_HUB_OFFLINE=1`），模型必须已下载到本地缓存。`build_index.py` 在构建索引时负责首次下载。

---

### Python 版本相关问题

- 必须在 **Python 3.11** 环境下运行。
- 某些 API 相关依赖在 Python 3.12+ 环境中出现过兼容性问题。
- 如果使用 `pyenv` 或 `conda`，请显式指定 Python 3.11。
- 如果遇到 `pip install` 失败，先确认 Python 版本：`python --version`

---

## 8. 当前局限 / 后续开发者注意事项

本节作为项目交接说明，描述当前状态中需要注意或需要后续处理的部分。

### 识曲模块：Auris 指纹数据库

**现状**：识曲模块的代码集成已经完成——Lyra 后端通过 `POST /recognition` 端点接收音频，Auris 引擎提供指纹匹配 API，两者之间的 HTTP 通信已打通。Auris 不可用时接口自动返回空结果，不会导致错误。

**遗留工作**：Auris 引擎的**指纹数据库尚未构建**。识别功能能够运行但不会返回实际匹配结果，因为数据库中还没有歌曲的指纹数据。这需要在 Auris 中上传音频文件 → 生成指纹 → 入库。后续负责此部分的开发者需要准备音频素材并执行数据导入。

**相关文件**：
- `src/recognition/service.py` — 引擎抽象层（含完整的替换指南注释）
- `src/recognition/providers/auris.py` — Auris HTTP 通信适配器
- `auris-engine/` — Auris 引擎项目

### 作曲模块

`/composition` 端点和 `src/composition/service.py` 均为占位实现，等待队友的生成模型接入。接口契约已经定义（见 `backend/models.py` 中的 `CompositionRequest/CompositionResponse`），替换指南详见 `src/composition/service.py` 文件顶部注释。

### 健康检查状态

`GET /health` 端点中，`modules.recognition` 当前返回 `"not_implemented"`。这与实际代码状态不完全一致——识别模块已经通过 Auris 集成实现了基本功能。这是在开发过程中遗留的，后续开发者可以考虑更新健康检查以反映 `"integrated"` 或 `"available"` 等更准确的状态。注意 `backend/smoke_test.py` 中也有一处与此相关的断言，修改时需要同步更新。

### Requirements 文件重复

项目根目录和 `backend/` 目录各有一个 `requirements.txt`，内容存在大量重叠。**当前建议使用根目录版本安装依赖**。后续可以清理：将 `backend/requirements.txt` 精简为仅包含后端特有依赖（如 `python-multipart`、`httpx`），作为根目录 `requirements.txt` 的补充，或者合并为单一文件。

### 前端部署方式

当前前端通过 `file://` 协议直接在浏览器中打开 HTML 文件。这种方式简单、无需构建工具，适合 Demo 演示。但如果需要部署到远程服务器或支持多用户访问，后续可以考虑将前端放到 Nginx 等 Web 服务器中，或通过 FastAPI 的 `StaticFiles` 挂载。

### 统一 Docker 方案

目前 Lyra 后端直接以 Python 进程运行，仅 Auris 使用 Docker。两者需要分别启动。如果后续需要简化部署流程（例如比赛演示时的一键启动），可以考虑为 Lyra 后端也编写 Dockerfile，并提供统一的 `docker compose up` 编排文件。

---

## 9. 快速参考

### 常用命令

```bash
# 激活虚拟环境
.venv\Scripts\activate          # Windows
source .venv/bin/activate        # macOS / Linux

# 安装依赖
pip install -r requirements.txt

# 构建索引
python src/build_index.py

# 启动后端
uvicorn backend.app:app --reload --host 0.0.0.0 --port 8000

# 打开前端
start_frontend.bat

# 冒烟测试
python backend/smoke_test.py

# API 诊断
python diagnose_api.py

# 启动 Auris
cd auris-engine && docker compose up -d
```

### 端口速查

| 端口 | 服务 | 启动方式 |
|---|---|---|
| 8000 | Lyra 后端 | `uvicorn backend.app:app --port 8000` |
| 8000 | Auris 前端（冲突风险） | Docker Compose |
| 8001 | Auris API | Docker Compose |
| 5432 | PostgreSQL（Auris） | Docker Compose |
| 9000 | RustFS 对象存储 | Docker Compose |
| 9001 | RustFS 管理控制台 | Docker Compose |


