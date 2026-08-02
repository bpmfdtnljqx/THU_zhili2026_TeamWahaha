# 🎵  Lyra

> 你的 AI 音乐伙伴 — 听歌、推荐、造歌，一句话的事。
>
> 🚧 正在参加 “智理杯” 大赛，火热开发中！

---

## 🚀 快速开始 (Quick Start)

详见 **[SETUP_Guide.md](SETUP_Guide.md)** — 包含完整的环境搭建、依赖安装、后端启动和问题排查说明。

### 三步跑起来

```bash
# 1. 安装依赖
pip install -r requirements.txt

# 2. 配置 API Key（在 .env 中设置 DEEPSEEK_API_KEY）

# 3. 构建索引 + 启动后端
python src/build_index.py
uvicorn backend.app:app --reload
```

然后打开 `frontend/index.html` 即可使用。

---

## ✨ 它能做什么？

### 🎤 听歌识曲
周围在放什么歌？哼两句旋律也行，它能马上告诉你。

### 🎧 超懂你的推荐
不说“风格”，只聊感觉。  
“想听像下雨天窝在沙发里那种慵懒的女声” — 它真的听得懂。

### 🎶 AI 做歌
用文字描述灵感，它帮你把旋律做出来。  
你的奇怪想法，都能变成一首歌。

---

## 🛠️ 现在怎么样？

我们还在拼命写代码，功能在一点点变完整。  
欢迎点个 ⭐ star 关注进度，也欢迎提想法！

---

## 🧑‍🤝‍🧑 团队

一群喜欢音乐和代码的人，在 Vibe Coding 搞事情。

---

## 📜 License

MIT