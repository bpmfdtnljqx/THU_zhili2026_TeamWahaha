关于可能遇到的一点配置问题 

目前的配置是**claude+deepseek-v4-pro**，如果使用vscode（Windows系统）的话，Claude在**powershell**是没法正常运行的，需要在终端输入**powershell -ExecutionPolicy Bypass -Command "claude"**（只管用一次），或者以管理员身份打开powershell输入**Set-ExecutionPolicy RemoteSigned -Scope CurrentUser**（但是会让当前所有外来脚本都可以跑），或者写一个脚本，好像挺麻烦的，这里就不记了  

另一种替代方法是点击**终端**字样右边一个向下的箭头，看着像展开的符号，选择git bash，同时还可以直接在里面用Linux的命令，非常方便  

---

## 环境变量配置（必需）

由于国内网络环境，直接下载 HuggingFace 模型可能会失败。项目使用 `HF_ENDPOINT` 镜像来加速模型下载。

### 1. 配置 `.env` 文件

项目根目录下已创建 `.env` 文件，内容如下：

```
HF_ENDPOINT=https://hf-mirror.com
```

如果你需要使用其他镜像源，可以修改此文件。

### 2. 安装依赖

```bash
pip install -r requirements.txt -i https://pypi.tuna.tsinghua.edu.cn/simple
```

确保 `python-dotenv` 已安装。程序启动时会自动加载 `.env` 中的环境变量，无需手动 `export`。
