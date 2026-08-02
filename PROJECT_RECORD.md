# 🎵 Lyra — 项目记录 (Project Record)

> 更新日期：2026-08-02
> 项目：AI 驱动的音乐推荐智能体
>
> **推荐后端已功能完备。** 待开发：前端界面、听歌识曲、AI 作曲。

---

## 一、项目概述

**Lyra** 是一个 AI 音乐推荐智能体（Agent），核心理念是 **语义理解** 而非关键词匹配——理解用户的情绪与人生状态，然后推荐有意义的音乐。

- **知识库**：170 首精心挑选的中文歌曲（`songs.json`）
- **检索方式**：BGE-M3 语义嵌入 + ChromaDB 向量数据库
- **重排序**：DeepSeek API 驱动的 AI 精排，输出个性化推荐理由
- **Agent 层**：Planner（意图理解）→ LyraAgent（编排）→ LLMResponse（自然对话），含模板降级
- **反馈系统**：JSONL 持久化用户反馈，为未来个性化做准备
- **可观测性**：结构化日志 + 增强基准测试（含多样性指标、LLM 评委）
- **API 层**：`recommend()` 返回结构化数据，前端集成即用
- **开发阶段**：推荐后端已功能完备，前端尚未开始

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
| `f7ccf1c` | **Phase 2.1**：实现 Agent 层 — Planner（意图理解）+ Agent（编排）+ Response（自然对话） |
| *(未提交)* | **Phase 2.2**：推荐后端升级 — LLM 自然对话、用户反馈存储、avoid 过滤、结构化日志、`recommend()` API、增强基准测试 |

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
│   ├── agent.py             # Agent 编排器（Planner → Retriever → Reranker → LLMResponse）
│   ├── planner.py           # 意图理解模块（DeepSeek → 结构化音乐意图）
│   ├── response.py          # 模板化回复生成器（LLMResponse 的降级方案）
│   ├── response_llm.py      # LLM 自然对话生成器（DeepSeek API，温暖共情风格）
│   ├── build_index.py       # 读取 songs.json → 嵌入 → 写入 ChromaDB
│   ├── retriever.py         # 加载 ChromaDB + BGE-M3，执行 Top-K 检索
│   ├── reranker.py          # DeepSeek API 重排序模块（含 avoid 过滤、多样性控制）
│   ├── reranker_cache.py    # 带 TTL 的 LRU 内存缓存
│   ├── feedback.py          # 用户反馈存储（JSONL 追加写入）
│   ├── logger.py            # 结构化日志模块（时间戳、模块名、计时器）
│   ├── api.py               # 薄封装 API，供前端集成使用
│   └── benchmark.py         # 性能基准测试 + 多样性指标 + LLM 评委 + 管道计时
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

> 注：`requests` 在 `planner.py` 和 `reranker.py` 中直接使用，但作为 `chromadb` 等包的间接依赖已自动安装。

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

#### `test_planner_parse.py`
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

#### `src/agent.py`
**LyraAgent — 轻量级编排器。** 无外部框架依赖。
- **`LyraAgent`**：协调 Planner → Retriever → Reranker → LLMResponse 全流程
- **`recommend(user_input) -> dict`**：**主接口。** 返回完整结构化数据：
  - `intent`：Planner 提取的结构化意图
  - `candidates`：向量检索 Top-15 候选
  - `ranked_results`：重排序后的 Top-5 推荐
  - `response_text`：LLM 生成的自然对话文本
  - `metadata`：各阶段耗时、缓存信息、计数
- **`chat(user_input) -> str`**：兼容封装，内部调用 `recommend()` 后仅返回 `response_text`
- **`_make_serializable()`**：递归转换 numpy 标量等非 JSON 类型，确保返回值可序列化
- **`LYRA_DEBUG` 模式**：设置 `LYRA_DEBUG=1` 开启管道可观测性，输出写入 stderr 不干扰 spinner
  - 打印每个阶段的完整追踪：用户输入 → Planner intent → 检索 query → retriever 结果 → reranker 上下文 → 最终排名
- 约 220 行代码

#### `src/planner.py`
**意图理解模块 — 将自然语言转化为结构化音乐意图。** 使用 DeepSeek API。
- **`Planner`**：
  - **`analyze(user_input) -> dict`**：提取 emotion / scene / listener_need / energy_level / avoid / free_text
  - **`_call_api()`**：调用 DeepSeek API（轻量级，max_tokens=200, timeout=10s）
  - **`_parse_intent()`**：多策略 JSON 提取（直接解析 → 去代码块 → 修复尾随逗号 → 正则提取对象）
  - **`_validate_intent()`**：字段标准化，energy_level 支持中英文映射
  - **`_build_free_text()`**：将结构化 intent 转为**自然叙述段落**（非标签拼接），提升 BGE-M3 嵌入质量
    - 例如：「用户感到疲惫、压抑，正处于深夜、独处的场景中，需要放松、安静陪伴的音乐，希望听到安静舒缓的音乐。不想听到吵闹、节奏快风格的歌曲。用户说：『加班到凌晨……』」
  - **`_fallback()`**：API 失败时返回 `free_text = 原始用户输入`，优雅降级
- 系统提示词明确约束：不推荐歌曲、不提取关键词、只提取情绪/场景信息
- 使用模块级 logger（`get_logger("planner")`），受 `LYRA_DEBUG` / `LYRA_PLANNER_DEBUG` 控制

#### `src/response_llm.py`（🆕 Phase 2.2）
**LLM 自然对话生成器 — 温暖、共情的音乐推荐回复。** 使用 DeepSeek API。
- **`LLMResponse`**：
  - **`generate(user_input, intent, recommendations) -> str`**
- 系统提示词：像一个懂音乐、懂人心的朋友在聊天，不是客服，不是机器人
- 先共情用户情绪 → 自然引出推荐 → 温暖的结尾
- 不使用 markdown，不用编号列表，用自然段落叙述
- 配置：`temperature=0.7`, `max_tokens=300`, `timeout=8s`
- **优雅降级**：API 调用失败时自动回退到模板化 `Response`，管道不中断
- 与 `Response` 接口完全一致，`agent.py` 无需任何额外修改

#### `src/response.py`
**模板化回复生成器 — LLMResponse 的降级方案。**
- 保留 Phase 2.1 的模板逻辑，作为 LLM 生成失败时的安全网
- 接口与 `LLMResponse` 完全一致：`generate(user_input, intent, recommendations) -> str`
- 同理心开场白 + 歌曲列表 + 温暖结尾
- 零额外 API 调用，零延迟

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
- **Intent 集成**：Planner 的结构化意图**前置**（prepend）于候选列表之前，作为"必须严格参考的情绪画像"而非"仅供参考"
- **🆕 Avoid 过滤** (`_filter_by_avoid`)：在构建 prompt 前，对候选歌曲的 emotion / core_theme / suitable_scene / keywords / energy_level 做关键词重叠检查，剔除用户明确不想听到的风格。若过滤后不足 5 首则保留原始列表
- **🆕 多样性控制**：系统提示词要求同一歌手不超过 1 首、覆盖不同年代和风格
- **🆕 增强系统提示词**：明确排序权重（情感匹配 > 场景匹配 > 主题匹配 > 避免违规），增加多样性要求
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

#### `src/logger.py`（🆕 Phase 2.2）
**结构化日志模块 — 统一管道可观测性。**
- **`Logger`**：零依赖，输出到 stderr（保持 stdout 干净）
- 方法：`debug()` / `info()` / `warn()` / `error()` + `start_timer()` / `end_timer()`
- 全局开关：`LYRA_DEBUG=1` 启用所有模块的 debug 日志
- 模块级开关：`LYRA_PLANNER_DEBUG`、`LYRA_RESPONSE_DEBUG`、`LYRA_CACHE_DEBUG` 等
- 替代了各模块中散落的 `print()` 调用

#### `src/feedback.py`（🆕 Phase 2.2）
**用户反馈存储 — 为未来个性化做准备。**
- **`FeedbackStore`**：追加写入 JSONL 文件（`feedback.jsonl`），零依赖
- 每条记录包含：timestamp、user_query、intent、song_ids、song_titles、ratings（like/dislike/neutral）、comment
- 方法：`save()`（追加一条）、`load_all()`（读取全部）、`stats()`（汇总统计）
- CLI 中通过简单 y/n 交互收集反馈（见 `main.py`）

#### `src/api.py`（🆕 Phase 2.2）
**薄封装 API — 供前端集成使用。**
- 模块级单例 `LyraAgent`（惰性初始化，首次调用时才加载模型）
- **`recommend(user_input) -> dict`**：返回完整 JSON 可序列化结构
- **`chat(user_input) -> str`**：返回显示文本
- 前端（FastAPI / Flask）集成只需 `from src.api import recommend`

#### `src/benchmark.py`
性能基准测试与质量验证工具（Phase 2.2 大幅增强）。
- **基准测试**：5 个测试查询（涵盖失恋、晨跑、加班、庆祝、思念等场景），可配置运行次数
- **指标**：平均延迟、P50/P90/P95、标准差
- **目标**：平均响应时间 ≤ 10 秒
- **质量验证**：结果数量、无重复、推荐理由完整性、必要字段完整性
- **🆕 多样性指标** (`--diversity`)：Top-5 歌曲在 emotion / core_theme / genre 上的成对 Jaccard 距离
- **🆕 LLM 评委** (`--judge`)：调用 DeepSeek 对推荐理由评分（相关性 / 情感共鸣 / 多样性，每项 1-5 分）
- **🆕 管道计时** (`--timing`)：展示 Planner / Retriever / Reranker / Response 各阶段平均耗时
- **CLI 参数**：`--runs N`、`--no-cache`、`--quality`、`--diversity`、`--judge`、`--timing`、`--full`、`--queries ...`

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
| 意图理解 | DeepSeek API (deepseek-chat) | 轻量级结构化 intent 提取 |
| 重排序 | DeepSeek API (deepseek-chat) | LLM 驱动的语义理解与排序，含 avoid 过滤 |
| 自然对话 | DeepSeek API (deepseek-chat) | LLM 生成温暖共情回复，模板降级 |
| 缓存 | 内存 LRU + TTL | 减少 API 调用，提速 |
| 反馈存储 | JSONL 追加写入 | 零依赖，为个性化做准备 |
| 日志 | 自定义 Logger | 结构化输出到 stderr，含计时器 |
| 深度学习 | PyTorch + sentence-transformers | 模型推理 |
| 语言 | Python 3.11 | 全项目统一 |

---

## 六、数据流

### Phase 2.2 — Agent-based pipeline（当前）

```
用户查询（自然语言）
    │
    ▼
LyraAgent.recommend()
    │
    ▼
Planner.analyze()          ← DeepSeek API（意图提取）
    │  输出: {emotion, scene, listener_need, energy_level, avoid, free_text}
    │  free_text 为自然叙述段落，用于高质量语义嵌入
    ▼
Retriever.query(free_text) ← BGE-M3 嵌入 + ChromaDB
    │  输出: Top-15 候选
    ▼
Reranker.rerank(query, candidates, intent=intent)  ← DeepSeek API（精排）
    │  intent 作为「必须严格参考的情绪画像」前置
    │  含 avoid 关键词预过滤 + 多样性控制
    │  输出: Top-5 + 个性化理由
    ▼
LLMResponse.generate()     ← DeepSeek API（自然对话）
    │  温暖共情的叙述风格
    │  失败时自动降级到 Response.generate()（模板）
    │  输出: 自然对话文本
    ▼
结构化返回
    │  recommend() 返回完整 dict：
    │  {intent, candidates, ranked_results, response_text, metadata}
    │  chat() 仅返回 response_text（向后兼容）
    ▼
终端展示 + 反馈收集
```

### Phase 2.1 — 模板化回复（已被 Phase 2.2 替代）

```
用户查询 → Planner → Retriever → Reranker → Response（模板） → 终端
```

### Phase 1 — RAG pipeline（已被 Phase 2 替代）

```
用户查询 → Retriever (BGE-M3) → ChromaDB → Reranker (DeepSeek) → 终端
```

---

## 七、已完成 vs 待完成

### ✅ 已完成
- 音乐知识库（170 首中文歌曲，结构化元数据）
- BGE-M3 语义嵌入 + ChromaDB 向量索引
- 检索引擎（Retriever）
- DeepSeek API 重排序 + 个性化推荐理由（Reranker）
- 🆕 Reranker avoid 关键词预过滤 + 多样性控制
- LRU 缓存（减少重复 API 调用）
- API 诊断工具（独立于项目运行）
- 解析器单元测试（Reranker 15 种 + Planner 场景覆盖）
- 性能基准测试 + 质量验证工具
- 🆕 增强基准测试（多样性指标 + LLM 评委 + 管道计时）
- 自动加载环境变量（.env）
- Agent 编排层（LyraAgent）— Planner → Retriever → Reranker → LLMResponse
- 意图理解模块（Planner）— 结构化音乐意图提取 + 优雅降级
- 🆕 Planner free_text 自然叙述段落，提升嵌入质量
- 🆕 LLM 自然对话生成器（LLMResponse）— 温暖共情风格，模板降级
- 🆕 用户反馈存储（FeedbackStore）— JSONL 持久化
- 🆕 结构化日志模块（Logger）— 统一管道可观测性
- 🆕 薄封装 API（api.py）— `recommend()` 返回结构化数据，前端即用
- LYRA_DEBUG 管道可观测性模式

### 🚧 待完成
- 前端界面 / 聊天 UI
- 听歌识曲功能（独立模块）
- AI 作曲功能（独立模块）
- 基于反馈数据的个性化推荐
- Phase 2.3：反馈驱动的推荐策略优化

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
python test_planner_parse.py

# 6. 性能基准测试
python src/benchmark.py --runs 3 --quality

# 7. 增强基准测试（多样性 + LLM 评委 + 管道计时）
python src/benchmark.py --diversity
python src/benchmark.py --judge
python src/benchmark.py --timing
python src/benchmark.py --full        # 运行全部

# 8. 管道调试（查看 Agent 各阶段内部状态）
LYRA_DEBUG=1 python src/main.py

# 9. 反馈统计
python -c "from src.feedback import FeedbackStore; print(FeedbackStore().stats())"
```
