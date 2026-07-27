# 🎵 Lyra — 项目记录 (Project Record)

> 生成日期：2026-07-27  
> 项目：AI 驱动的音乐推荐智能体

---

## 一、项目概述

**Lyra** 是一个 AI 音乐推荐智能体（Agent），核心理念是 **语义理解** 而非关键词匹配——理解用户的情绪与人生状态，然后推荐有意义的音乐。

- **知识库**：170 首精心挑选的中文歌曲（`songs.json`）
- **检索方式**：BGE-M3 语义嵌入 + ChromaDB 向量数据库
- **重排序**：DeepSeek API 驱动的 AI 精排，输出个性化推荐理由
- **开发阶段**：检索引擎已完成，前端尚未开始

---

## 二、开发历史

| 提交 | 说明 |
|------|------|
| `0025552` | 编写 README 和 SETUP_Guide |
| `b18d87e` | 初步构建歌曲知识库 songs.json |
| `74ef0ca` | 创建 CLAUDE.md，明确项目开发原则 |
| `162871f` | **Phase 1 MVP**：实现 BGE-M3 嵌入 + ChromaDB 检索引擎 |
| `30b1325` | 修复：启动时不再需要手动配置镜像变量（自动加载 .env） |
| `4e901da` | 接入 DeepSeek API 重排序模块，大幅缩短响应时间 |
| `8cb72ec` | 修复 API 调用问题，优化运行界面 |
| *(pending)* | **Phase 2.1**：引入 Agent 层 — Planner（意图理解）+ Agent（编排）+ Response（自然对话） |

---

## 三、项目目录结构

```
lyra/
├── .env                    # 环境变量（API key、镜像源等）
├── .gitignore              # Git 忽略规则
├── README.md               # 项目介绍（面向用户）
├── CLAUDE.md               # 项目开发原则（面向 AI 助手）
├── SETUP_Guide.md           # 配置指南（环境变量、依赖安装）
├── PROJECT_RECORD.md        # 本文件 — 项目记录
├── requirements.txt         # Python 依赖
├── songs.json              # 音乐知识库（170首歌曲，源数据）
├── diagnose_api.py          # DeepSeek API 独立诊断工具
├── test_reranker_parse.py   # 重排序器 JSON 解析单元测试
├── test_planner_parse.py    # Planner JSON 解析单元测试
├── src/
│   ├── main.py              # CLI 交互入口，使用 LyraAgent
│   ├── agent.py             # 🆕 Agent 编排器（Planner → Retriever → Reranker → Response）
│   ├── planner.py           # 🆕 意图理解模块（DeepSeek → 结构化音乐意图）
│   ├── response.py          # 🆕 自然对话生成器（模板化，可替换为 LLM）
│   ├── build_index.py       # 读取 songs.json → 嵌入 → 写入 ChromaDB
│   ├── retriever.py         # 加载 ChromaDB + BGE-M3，执行 Top-K 检索
│   ├── reranker.py          # DeepSeek API 重排序模块（已扩展接受 intent 参数）
│   ├── reranker_cache.py    # 带 TTL 的 LRU 内存缓存
│   └── benchmark.py         # 性能基准测试 + 质量验证
└── chroma_db/               # ChromaDB 持久化向量数据库（自动生成）
    ├── chroma.sqlite3
    └── 2198d989-.../        # 向量索引数据文件
```

---

## 四、各文件详细说明

### 根目录文件

#### `.env`
环境变量配置文件，包含：
- `HF_ENDPOINT`：HuggingFace 镜像源（国内加速）
- `DEEPSEEK_API_KEY`：DeepSeek API 密钥
- `DEEPSEEK_BASE_URL`：DeepSeek API 基础 URL
- `DEEPSEEK_MODEL`：使用的模型名称（`deepseek-chat`）

#### `.gitignore`
忽略 `.venv/`、`chroma_db/`、`__pycache__/`、`.env`，防止敏感信息和生成文件入库。

#### `README.md`
面向用户的 README。介绍 Lyra 的三大功能：
- 🎤 听歌识曲
- 🎧 语义音乐推荐
- 🎶 AI 作曲

提及项目正在参加"智理杯"大赛，使用 MIT 协议。

#### `CLAUDE.md`
面向 AI 助手的开发原则：
1. **语义检索优先** — 不使用关键词匹配
2. **Agent 优先** — 业务逻辑独立于前端
3. **songs.json 是唯一数据源** — 不可自动覆写
4. **简洁架构** — 避免过度工程化
5. **当前里程碑** — 专注后端检索引擎，不碰前端

#### `SETUP_Guide.md`
配置问题指南：
- Claude 在 Windows PowerShell 中的运行问题及解决方案（使用 Git Bash 替代）
- 环境变量配置说明（`.env` + `python-dotenv` 自动加载）
- 依赖安装命令（使用清华 pypi 镜像）

#### `requirements.txt`
Python 依赖（4 个包）：
- `torch` — PyTorch 深度学习框架
- `sentence-transformers` — BGE-M3 嵌入模型
- `chromadb` — 向量数据库
- `python-dotenv` — .env 文件加载

#### `songs.json`
**音乐知识库**（170 首中文歌曲），每首歌包含：
- 基础信息：`title`（歌名）、`artist`（歌手）、`album`（专辑）、`year`（年份）、`genre`（风格）、`language`（语言）
- 语义标签：`core_theme`（核心主题）、`emotion`（情绪）、`suitable_scene`（适合场景）、`listener_need`（听众需求）
- 评估维度：`energy_level`（能量水平）、`valence`（情感正负）
- 推荐文案：`description`（歌曲描述）、`recommendation_reason`（推荐理由）
- 检索辅助：`keywords`（关键词列表）

#### `diagnose_api.py`
DeepSeek API 独立诊断工具，不依赖项目的其他模块。测试项目：
1. API Key 格式检查
2. 网络可达性（DNS + TCP）
3. 当前配置的 API 调用测试
4. 备选 URL 格式测试（不含 `/v1` 前缀）
5. 备选模型测试
6. 可用模型列表查询

每个测试输出详细的诊断信息（状态码、响应头、延迟等），帮助排查 API 连接问题。

#### `test_reranker_parse.py`
重排序器 JSON 解析能力的单元测试（15 个测试用例 + 7 个提取策略测试），覆盖场景：
- 标准 JSON 数组
- `{"selected": [...]}` 包装对象
- Markdown 代码块
- JSON 前后夹杂文本
- 单曲对象（非数组）
- `{"recommendations": [...]}` / `{"result": [...]}` 包装
- 索引模式
- 尾随逗号（JSON 修复）
- 模糊标题匹配
- 空响应 / 非 JSON 垃圾
- BOM 字符前缀

#### `test_planner_parse.py`  🆕
Planner JSON 解析能力的单元测试，覆盖场景：
- 标准 intent JSON 对象
- Markdown 代码块包装
- JSON 前后夹杂解释文本
- 尾随逗号修复
- 最小 intent（全部空字段）
- 非 JSON 输入 → None（触发 fallback）
- energy_level 中文/英文标准化

### `src/` 目录

#### `src/main.py`
CLI 交互入口。
- **启动流程**：检查 `chroma_db/` 是否存在 → 不存在则自动调用 `build_index.py` 构建索引 → 加载 `LyraAgent`
- **查询流程**：用户输入 → `agent.chat(query)` → 格式化输出
- **UX 优化**：等待时显示 spinner 动画（"Thinking..."），推荐理由带 💭 图标
- 输入 `quit` 退出

#### `src/agent.py`  🆕
**LyraAgent — 轻量级编排器。** 无外部框架依赖。
- **`LyraAgent`**：协调 Planner → Retriever → Reranker → Response 全流程
- **`chat(user_input) -> str`**：接收用户自然语言，返回格式化推荐结果字符串
- Agent 本身不含业务逻辑 — 只负责组件间的数据传递
- 约 50 行代码

#### `src/planner.py`  🆕
**意图理解模块 — 将自然语言转化为结构化音乐意图。** 使用 DeepSeek API。
- **`Planner`**：
  - **`analyze(user_input) -> dict`**：提取 emotion / scene / listener_need / energy_level / avoid
  - **`_call_api()`**：调用 DeepSeek API（轻量级，max_tokens=200, timeout=10s）
  - **`_parse_intent()`**：多策略 JSON 提取（直接解析 → 去代码块 → 修复尾随逗号 → 正则提取）
  - **`_validate_intent()`**：字段标准化，energy_level 支持中英文映射
  - **`_build_free_text()`**：将结构化 intent 转为自然语言段落，用于 BGE-M3 嵌入
  - **`_fallback()`**：API 失败时返回 `free_text = 原始用户输入`，优雅降级
- 系统提示词明确约束：不推荐歌曲、不提取关键词、只提取情绪/场景信息
- 调试日志：`LYRA_PLANNER_DEBUG=1` 或 `LYRA_VERBOSE=1` 开启

#### `src/response.py`  🆕
**自然对话生成器 — 将推荐数据转化为终端友好的对话文本。**
- **`Response`**：
  - **`generate(user_input, intent, recommendations) -> str`**
- Phase 2.1 使用模板（快速、可预测、无额外 API 调用）
- 开场白根据 intent.emotion / intent.scene 定制同理心语句
- 结尾语根据 intent.listener_need 定制温暖的收尾
- 接口设计为可替换：未来换 LLM 生成只需相同 `generate()` 签名

#### `src/build_index.py`
索引构建器，将 `songs.json` 转化为 ChromaDB 向量数据库。
- **`load_songs()`**：读取 songs.json
- **`build_embedding_text()`**：将每首歌拼成自然语言段落（description + core_theme + emotion + suitable_scene + listener_need），用于语义嵌入
- **`build_collection()`**：加载 BGE-M3 模型 → 批量嵌入 170 首歌 → 存入 ChromaDB（余弦距离空间）
- 可独立运行：`python src/build_index.py`

#### `src/retriever.py`
向量检索引擎。
- 模型：`BAAI/bge-m3`（BGE-M3 多语言嵌入模型）
- 数据库：ChromaDB 持久化客户端
- 集合名：`lyra_songs`
- **强制离线模式**：设置 `HF_HUB_OFFLINE=1`、`TRANSFORMERS_OFFLINE=1` 避免运行时网络检查
- **`query(text, k)`**：将用户查询文本嵌入 → 在 ChromaDB 中检索 Top-K → 返回歌曲元数据列表（含距离分数）

#### `src/reranker.py`
**核心模块** — DeepSeek API 驱动的重排序器。
- **架构**：接收 Top-15 向量检索候选 + 用户查询 → 调用 DeepSeek API 综合评估 → 返回 Top-5 + 文采优美的推荐理由
- **容错**：API 失败时优雅降级为向量检索 Top-5
- **候选标准化** (`_normalize_candidate`)：支持 dict、string、list 等多种输入格式，自动从 songs.json 补充元数据
- **提示词构建** (`_build_candidates_text`)：每首歌压缩为一行（歌名-歌手 | 主题 | 情绪 | 场景）
- **API 调用** (`_call_api`)：支持重试（最多 2 次）、多模型自动切换、全面诊断日志
- **响应解析** (`_parse_response`)：6 层 JSON 提取策略
  1. 直接解析
  2. 去除 Markdown 代码块
  3. 修复尾随逗号
  4. 修复 + 去代码块
  5. 正则提取 JSON 数组
  6. 正则提取 JSON 对象
- **歌曲匹配**：索引匹配 → 标题+歌手精确匹配 → 标题精确匹配 → 子串模糊匹配
- **配置**：temperature=0, max_tokens=600, top_p=0.9, timeout=20s
- **缓存**：通过 `RerankerCache` 实现 LRU + TTL 缓存（默认 30 分钟）

#### `src/reranker_cache.py`
线程安全的内存 LRU 缓存。
- **缓存键**：`SHA256(query + sorted(候选ID列表))`
- **TTL**：默认 1800 秒（30 分钟）
- **容量**：默认 1000 条
- **LRU 驱逐**：基于最后访问时间
- **统计**：hits / misses / size / max_size / ttl_s
- 配置：`LYRA_CACHE_ENABLED`、`LYRA_CACHE_TTL`、`LYRA_CACHE_MAX_SIZE`

#### `src/benchmark.py`
性能基准测试与质量验证工具。
- **基准测试**：5 个测试查询（涵盖失恋、晨跑、加班、庆祝、思念等场景），可配置运行次数
- **指标**：平均延迟、P50/P90/P95、标准差
- **目标**：平均响应时间 ≤ 10 秒
- **质量验证**：结果数量、无重复、推荐理由完整性、必要字段完整性
- **CLI 参数**：`--runs N`、`--no-cache`、`--quality`、`--queries ...`

### `chroma_db/` 目录

ChromaDB 持久化向量数据库（由 `build_index.py` 生成，已加入 `.gitignore`），包含：
- `chroma.sqlite3`：元数据数据库
- `2198d989-.../`：向量索引二进制文件（data、header、length、link_lists）

---

## 五、技术栈

| 组件 | 技术 | 说明 |
|------|------|------|
| 嵌入模型 | BAAI/bge-m3 | 多语言语义嵌入，~2GB |
| 向量数据库 | ChromaDB | 持久化存储，余弦距离 |
| 重排序 | DeepSeek API (deepseek-chat) | LLM 驱动的语义理解与排序 |
| 缓存 | 内存 LRU + TTL | 减少 API 调用，提速 |
| 深度学习 | PyTorch + sentence-transformers | 模型推理 |
| 语言 | Python 3.11 | 全项目统一 |

---

## 六、数据流

### Phase 2.1 — Agent-based pipeline

```
用户查询（自然语言）
    │
    ▼
LyraAgent.chat()
    │
    ▼
Planner.analyze()          ← DeepSeek API（意图提取）
    │  输出: {emotion, scene, listener_need, energy_level, avoid, free_text}
    ▼
Retriever.query(free_text) ← BGE-M3 嵌入 + ChromaDB
    │  输出: Top-15 候选
    ▼
Reranker.rerank(query, candidates, intent=intent)  ← DeepSeek API（精排）
    │  intent 为辅助参考，用户原始查询为主信号
    │  输出: Top-5 + 个性化理由
    ▼
Response.generate()        ← 模板化自然对话
    │  输出: 带同理心的推荐回复
    ▼
终端展示
```

### Phase 1 — RAG pipeline（被替代）

```
用户查询 → Retriever (BGE-M3) → ChromaDB → Reranker (DeepSeek) → 终端
```

---

## 七、已完成 vs 待完成

### ✅ 已完成
- 音乐知识库（170 首中文歌曲，结构化元数据）
- BGE-M3 语义嵌入 + ChromaDB 向量索引
- 检索引擎（Retriever）
- DeepSeek API 重排序 + 个性化推荐理由
- LRU 缓存（减少重复 API 调用）
- API 诊断工具（独立于项目运行）
- 解析器单元测试（Reranker 15 种 + Planner 场景覆盖）
- 性能基准测试 + 质量验证工具
- 自动加载环境变量（.env）
- **🆕 Agent 编排层（LyraAgent）**
- **🆕 意图理解模块（Planner）— 结构化音乐意图提取**
- **🆕 自然对话生成器（Response）— 同理心开场 + 温暖收尾**
- **🆕 Reranker 扩展支持 intent 辅助上下文**

### 🚧 待完成
- 推荐 Agent（检索 + 推理 + 回复生成独立化）
- 前端界面 / 聊天 UI
- 听歌识曲功能
- AI 作曲功能

---

## 八、运行方式

```bash
# 1. 安装依赖
pip install -r requirements.txt

# 2. 配置 .env（API key 等）
# HF_ENDPOINT=https://hf-mirror.com
# DEEPSEEK_API_KEY=sk-xxxxx

# 3. 首次运行（自动构建索引）
python src/main.py

# 4. API 诊断（如遇连接问题）
python diagnose_api.py

# 5. 解析器测试
python test_reranker_parse.py

# 6. 性能基准测试
python src/benchmark.py --runs 3 --quality
```
