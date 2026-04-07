# Tencent Doc Review Skill

基于 LLM 的文章审核与 Word 批注工具。

> 先说结论：
>
> - 这个项目当前**需要先安装**，因为真正执行审核的是本地命令 `tencent-doc-review`
> - `skills/` 目录里的内容只是 **OpenClaw 原生 skill 的说明、调用模板和工作流约定**
> - 所以不是“把整个仓库随便丢进 OpenClaw 的 skill 文件夹里就能直接运行”
> - 推荐做法是：**把这个仓库当成 OpenClaw 工作区来用**；或者先安装项目，再把 [skills/tencent_doc_review_native](E:/VibeCoding/tencent-doc-review/skills/tencent_doc_review_native) 单独复制到 OpenClaw 的 `skills/` 目录

## 5 分钟上手

第一次接触这个项目，按下面 5 步走就够了。

### 1. 安装项目

Windows:

```powershell
cd <project-root>
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -e .
```

macOS:

```bash
cd /path/to/tencent-doc-review
python3 -m venv .venv
source .venv/bin/activate
pip install -e .
```

安装完成后，本地会有命令：

```bash
tencent-doc-review
```

### 2. 配置 `.env`

复制模板：

Windows:

```powershell
Copy-Item .env.example .env
```

macOS:

```bash
cp .env.example .env
```

最少建议填写：

```env
TENCENT_DOCS_TOKEN=你的腾讯文档 MCP token
SKILL_MCP_CLIENT=openclaw
FACT_CHECK_MODE=auto
LLM_PROVIDER=deepseek
LLM_API_KEY=你的模型 key
```

如果你当前是通过 `OpenClaw` 或 `Claude Code` 使用这个项目，推荐先把事实核查模式设为：

```env
FACT_CHECK_MODE=auto
```

这表示：

- 优先使用 Agent 自带联网能力进行事实核查
- 如果 Agent 侧走不通，再 fallback 到 API 搜索

如果你是纯本地 CLI 运行，更推荐：

```env
FACT_CHECK_MODE=api
SEARCH_PROVIDER=tavily
SEARCH_API_KEY=你的搜索 key
```

默认情况下，`review-docx` 和 `skill-run` 每次都会自动生成调试包，默认目录是：

```text
<project-root>/debug-output
```

如果你想改位置，还可以额外填写：

```env
REVIEW_DEBUG_OUTPUT_DIR=<project-root>/debug-output
```

这样调试包会改写到你指定的目录。无论默认目录还是自定义目录，程序都会生成一个**可直接上传到 issue 的单文件调试包**，文件名类似：

```text
tdr-debug-20260330-153012-RIVE产品调研报告-Michael-deepseek.json
```

调试包会自动对本地用户名、绝对路径、腾讯文档文档 ID 做脱敏。

腾讯文档 MCP token 获取页面：

- [腾讯文档 OpenClaw 场景页](https://docs.qq.com/scenario/open-claw.html?nlc=1)

### 3. 确认环境正常

```bash
openclaw --help
tencent-doc-review doctor
tencent-doc-review debug-config
```

如果 OpenClaw 在它自己的工作区里调用本项目，程序会自动尝试从多个位置寻找 `.env`。
如果你的环境比较特殊，也可以显式指定：

Windows:

```powershell
$env:TENCENT_DOC_REVIEW_ENV_FILE="C:\path\to\your\.env"
```

macOS:

```bash
export TENCENT_DOC_REVIEW_ENV_FILE="/path/to/your/.env"
```

### 4. 让 OpenClaw 发现这个 skill

推荐方式：

- 直接把这个仓库作为 OpenClaw 工作区打开
- 因为仓库里已经带了原生 skill：
  - [skills/tencent_doc_review_native/SKILL.md](E:/VibeCoding/tencent-doc-review/skills/tencent_doc_review_native/SKILL.md)

如果你的 OpenClaw 工作区不是这个仓库，也可以：

- 先安装本项目
- 再把 [skills/tencent_doc_review_native](E:/VibeCoding/tencent-doc-review/skills/tencent_doc_review_native) 复制或软链接到：
  - `<workspace>/skills/tencent_doc_review_native`
  - 或 `~/.openclaw/skills/tencent_doc_review_native`

### 5. 在 OpenClaw 里直接使用

推荐这样说：

```text
请使用 tencent_doc_review_native skill 审核这篇腾讯文档：
https://docs.qq.com/doc/你的文档ID

要求：
1. 下载为 Word
2. 生成带原生 Word 评论气泡的批注版
3. 上传到我指定的腾讯文档文件夹
4. 返回新文档链接和审核摘要
```

这个 skill 内部会调用本地命令：

```bash
tencent-doc-review review-docx --input-docx "<本地docx路径>" --title "<文档标题>"
```

也就是说：

- `skills/` 目录负责告诉 OpenClaw“什么时候该用这个 skill、该跑什么命令”
- `tencent-doc-review` 负责真正执行审核
- 两者缺一不可

当前主流程是：

1. 通过 OpenClaw 或其他 bridge 下载腾讯文档对应的 `.docx`
2. 在本地执行语言审核、事实核查、结构核对、前后矛盾检查
3. 生成带 Word 原生评论气泡的批注版 `.docx`
4. 文件超过 10MB 时自动压缩
5. 上传批注版到腾讯文档指定位置

当前默认主模型是 `DeepSeek`，`MiniMax M2.7` 可以作为备选模型共存。

## 事实核查模式说明

当前项目把“事实核查由谁执行”单独建模成一个统一配置：

```env
FACT_CHECK_MODE=auto|agent|api|offline
```

推荐理解如下：

- `auto`：优先使用 OpenClaw / Claude Code 自带联网能力；如果走不通，再 fallback 到搜索 API
- `agent`：强制使用 Agent 侧联网事实核查，不走搜索 API
- `api`：强制使用搜索 API 事实核查
- `offline`：不做联网事实核查，只做本地规则、结构、语言等审核

推荐默认值：

- `OpenClaw` / `Claude Code`：`auto`
- 纯本地 CLI：`api`
- 明确不想联网：`offline`

需要特别注意：

- 当前阶段已经先把配置模型与文档口径收口好了
- `FACT_CHECK_MODE` 已加入配置体系和诊断输出
- 运行时模式调度已经接入：
  - `offline` 会跳过联网检索
  - `api` 会直接走搜索 API
  - `agent` 会保留 Agent 路径与留痕，但当前运行时还没有独立 Agent 搜索执行器
  - `auto` 会优先尝试 Agent 路径，并在当前运行时自动 fallback 到 API
- 因此当前 `auto` 的主要价值是：
  - 保留统一模式语义
  - 把 fallback 信息写进检索痕迹
  - 为后续接入真实 Agent 侧事实核查执行器预留挂点

## 腾讯文档接入方式说明

当前项目支持两种不同的腾讯文档接入方式，但**当前面向用户的主路径是 OpenClaw + 腾讯文档 MCP**。OpenAPI 直连保留给开发调试和兼容用途。

### 1. OpenClaw + 腾讯文档 MCP

这是我们之前做真实下载、上传、批注联调时实际使用的路径。

特点：

- 通过 `OpenClaw CLI` 调腾讯文档 MCP
- 由 OpenClaw / 腾讯文档 MCP 负责登录态和 token
- 本项目本身**不会直接读取** `TENCENT_DOCS_CLIENT_ID` 和 `TENCENT_DOCS_OPEN_ID`
- 但我们建议你仍然把 **MCP token** 统一填在本项目 `.env` 的 `TENCENT_DOCS_TOKEN` 里，项目会把它透传给 bridge 子进程
- 你主要需要配置的是：
  - `TENCENT_DOCS_TOKEN`
  - `SKILL_MCP_CLIENT=openclaw`
  - bridge 配置通常可以留空，程序会自动推断

关于 token 获取，腾讯文档 MCP 官方说明页在这里：

- [腾讯文档 MCP 概述](https://docs.qq.com/open/document/mcp/)
- 官方文档中给出的 token 获取跳转入口会进入这个页面：[腾讯文档 OpenClaw 场景页](https://docs.qq.com/scenario/open-claw.html)

根据官方文档，腾讯文档 MCP 是“基于 Open API 的能力兼容 MCP 协议，需要登录 QQ/微信后方可操作对应账号的数据”。这意味着如果你走 MCP 路径，`client_id/open_id` 不需要用户在这个项目里手工填写，但 **token 仍然需要获取**。[腾讯文档 MCP 概述](https://docs.qq.com/open/document/mcp/)

推荐做法：

1. 打开 [腾讯文档 OpenClaw 场景页](https://docs.qq.com/scenario/open-claw.html?nlc=1)
2. 按页面提示登录腾讯文档
3. 在页面里获取或重置 token
4. 把 token 填到 `.env` 的 `TENCENT_DOCS_TOKEN`

### 2. 项目内置 Tencent Docs OpenAPI 直连

这是项目里保留的一条直连能力，主要给开发调试：

- `analyze --doc-id`
- `debug-doc`
- `list-files`

这条链路使用的是 [tencent_doc_client.py](/E:/VibeCoding/tencent-doc-review/src/tencent_doc_review/tencent_doc_client.py)，代码里会**同时强制检查**：

- `TENCENT_DOCS_TOKEN`
- `TENCENT_DOCS_CLIENT_ID`
- `TENCENT_DOCS_OPEN_ID`

少任意一个都会直接报错。

## 用户需要改哪些文件

用户层主要只需要关心两类文件：

### 1. 统一配置文件

- [`.env.example`](/E:/VibeCoding/tencent-doc-review/.env.example)
- 实际使用时复制为 `.env`

这里统一配置：

- 默认模型与 API Key
- 搜索配置
- MCP bridge 配置
- OpenClaw / Claude Code bridge 配置
- 当前使用哪套模板

当前默认使用场景下，用户通常**不需要**填写 OpenAPI 直连那组 `TENCENT_DOCS_*` 字段。
当前默认使用场景下，用户通常只需要填写：

- `TENCENT_DOCS_TOKEN`
- `SKILL_MCP_CLIENT`
- `FACT_CHECK_MODE`

`OPENCLAW_MCP_BRIDGE_EXECUTABLE` 和 `OPENCLAW_MCP_BRIDGE_ARGS` 在 OpenClaw 主路径下通常可以留空，程序会自动：

- 使用当前 Python 解释器启动 bridge
- 使用项目内置的 [openclaw_bridge.py](/E:/VibeCoding/tencent-doc-review/src/tencent_doc_review/access/openclaw_bridge.py)
- 在系统 PATH 或常见安装目录中查找 `openclaw` / `openclaw.cmd`

默认情况下，`review-docx` / `skill-run` 的调试包会自动输出到：

```text
<project-root>/debug-output
```

只有你想改位置时，才需要在 `.env` 里填写 `REVIEW_DEBUG_OUTPUT_DIR`。

只有在自动探测失败时，才需要手动填写这两项。

### 2. 模板目录

- [`templates`](/E:/VibeCoding/tencent-doc-review/templates)

这里单独存放模板内容本身：

- [`default_product_research_review_rules.md`](/E:/VibeCoding/tencent-doc-review/templates/default_product_research_review_rules.md)
- [`default_product_research_structure_template.md`](/E:/VibeCoding/tencent-doc-review/templates/default_product_research_structure_template.md)

也就是说：

- 想切换“用哪套模板”，改 `.env`
- 想修改“模板正文内容”，改 `templates/`

## 项目目录

```text
E:\VibeCoding\tencent-doc-review
├─ .env.example
├─ README.md
├─ skills/
├─ templates/
├─ downloads/
├─ tests/
└─ src/tencent_doc_review/
   ├─ access/
   ├─ analyzer/
   ├─ document/
   ├─ domain/
   ├─ llm/
   ├─ skill/
   ├─ templates/   # 包内 fallback，不建议直接修改
   ├─ workflows/
   └─ writers/
```

## OpenClaw 原生 Skill 包

仓库里已经带了可直接加载的 OpenClaw skill 目录：

- [`skills/tencent_doc_review_native/SKILL.md`](/E:/VibeCoding/tencent-doc-review/skills/tencent_doc_review_native/SKILL.md)

如果你把这个仓库本身作为 OpenClaw 工作区使用，那么 `skills/` 会被 OpenClaw 自动发现。

如果你的 OpenClaw 工作区不是这个仓库，可以把下面这个目录复制或软链接到：

- `<workspace>/skills/tencent_doc_review_native`
或
- `~/.openclaw/skills/tencent_doc_review_native`

这个原生 skill 的工作方式是：

1. OpenClaw 自己通过腾讯文档 MCP 下载 `.docx`
2. 本项目通过本地命令处理已下载的 `.docx`
3. OpenClaw 再把批注版 `.docx` 上传回腾讯文档

也就是说，原生 skill 模式下**不建议**在 OpenClaw 内再次调用 `tencent-doc-review skill-run`，而应该使用下面这个本地命令：

```bash
tencent-doc-review review-docx --input-docx "<本地docx路径>" --title "<文档标题>"
```

这个命令会返回 JSON，里面包含：

- `annotated_word_path`
- `upload_candidate_path`
- `markdown_report_path`
- `review_summary`

OpenClaw 原生 skill 应该上传 `upload_candidate_path`，而不是原始下载文件。

## 环境要求

### Python

- Python `>= 3.10`
- 推荐 Python `3.11` 或 `3.12`

### Python 依赖

核心依赖见 [`pyproject.toml`](/E:/VibeCoding/tencent-doc-review/pyproject.toml)：

- `httpx`
- `pydantic`
- `pydantic-settings`
- `python-docx`
- `Pillow`
- `loguru`
- `click`
- `rich`
- `tqdm`
- `aiofiles`

开发依赖：

- `pytest`
- `pytest-asyncio`
- `pytest-cov`
- `black`
- `isort`
- `mypy`
- `flake8`
- `pre-commit`

### 外部依赖

根据使用方式不同，还需要：

- 纯本地审核：
  - 一个可用的 LLM API Key
- 联网事实核查：
  - 如果走 `FACT_CHECK_MODE=agent`，需要你的 Agent 环境本身支持联网搜索
  - 如果走 `FACT_CHECK_MODE=api`，需要一个可用的搜索 API Key，目前接入的是 `Tavily`
  - 如果走 `FACT_CHECK_MODE=auto`，建议仍准备好一个可用搜索 API Key，便于 Agent 联网失败时 fallback
- 腾讯文档端到端：
  - 可用的 `OpenClaw CLI`
  - OpenClaw 中腾讯文档 MCP 已登录且可正常访问你的文档
  - 如果使用 OpenClaw + 腾讯文档 MCP，请优先在腾讯文档 OpenClaw 场景页完成 token 获取或登录流程：[腾讯文档 OpenClaw 场景页](https://docs.qq.com/scenario/open-claw.html)

## Windows 部署

### 1. 创建虚拟环境

```powershell
cd <project-root>
python -m venv .venv
.venv\Scripts\Activate.ps1
```

### 2. 安装项目

运行时安装：

```powershell
pip install -e .
```

开发依赖安装：

```powershell
pip install -e ".[dev]"
```

### 3. 配置环境变量

```powershell
Copy-Item .env.example .env
```

然后编辑 [`.env.example`](/E:/VibeCoding/tencent-doc-review/.env.example) 对应字段，填入你自己的 `.env`。

### 4. 验证配置

```powershell
tencent-doc-review doctor
```

## macOS 部署

### 1. 创建虚拟环境

```bash
cd /path/to/tencent-doc-review
python3 -m venv .venv
source .venv/bin/activate
```

### 2. 安装项目

```bash
pip install -e .
pip install -e ".[dev]"
```

### 3. 配置环境变量

```bash
cp .env.example .env
```

### 4. 验证配置

```bash
tencent-doc-review doctor
```

## `.env` 里建议关注的关键字段

### 默认模型

```env
LLM_PROVIDER=deepseek
LLM_API_KEY=your_key
LLM_BASE_URL=https://api.deepseek.com/v1
LLM_MODEL=deepseek-chat
```

### MiniMax 备选模型

```env
MINIMAX_API_KEY=your_minimax_key
MINIMAX_BASE_URL=https://api.minimaxi.com/v1
MINIMAX_MODEL=MiniMax-M2.7
```

### 搜索配置

```env
FACT_CHECK_MODE=api
SEARCH_PROVIDER=tavily
SEARCH_API_KEY=your_tavily_key
SEARCH_BASE_URL=https://api.tavily.com/search
SEARCH_MAX_RESULTS=5
SEARCH_TIMEOUT=20
SEARCH_DEPTH=basic
SEARCH_TOPIC=general
```

如果你当前是 Agent 场景，也可以改成：

```env
FACT_CHECK_MODE=auto
SEARCH_PROVIDER=tavily
SEARCH_API_KEY=your_tavily_key
```

这样 Agent 能联网时优先走 Agent，走不通时再回退到 API。

### 模板路径选择

```env
REVIEW_RULES_TEMPLATE_PATH=templates/default_product_research_review_rules.md
REVIEW_STRUCTURE_TEMPLATE_PATH=templates/default_product_research_structure_template.md
```

### OpenClaw bridge

Windows 示例：

```env
TENCENT_DOCS_TOKEN=your_tencent_docs_mcp_token
SKILL_MCP_CLIENT=openclaw
FACT_CHECK_MODE=auto
MCP_BRIDGE_TIMEOUT=240
# 通常留空，程序会自动推断
OPENCLAW_MCP_BRIDGE_EXECUTABLE=
OPENCLAW_MCP_BRIDGE_ARGS=
```

macOS 示例：

```env
TENCENT_DOCS_TOKEN=your_tencent_docs_mcp_token
SKILL_MCP_CLIENT=openclaw
FACT_CHECK_MODE=auto
MCP_BRIDGE_TIMEOUT=240
# 通常留空，程序会自动推断
OPENCLAW_MCP_BRIDGE_EXECUTABLE=
OPENCLAW_MCP_BRIDGE_ARGS=
```

如果你走的是 OpenClaw + 腾讯文档 MCP，通常不需要在本项目里再额外填写 `TENCENT_DOCS_CLIENT_ID / TENCENT_DOCS_OPEN_ID`，但仍然建议填写 `TENCENT_DOCS_TOKEN`。

如果自动探测失败，再手动补：

- `OPENCLAW_MCP_BRIDGE_EXECUTABLE`
  - Windows 通常填 `python`
  - macOS 通常填 `python3`
- `OPENCLAW_MCP_BRIDGE_ARGS`
  - 一般是：
    - `openclaw_bridge.py` 的路径
    - `--openclaw-executable`
    - 你的 `openclaw` 或 `openclaw.cmd` 路径
    - `--agent-id main --no-local`

也就是说，正常情况下你现在只需要填 `TENCENT_DOCS_TOKEN`，然后直接运行 `skill-run --mcp-client openclaw` 就够了。

### Claude Code bridge

阶段 C 之后，`claude_code` 已经不再只是占位入口，而是补上了最小 bridge 骨架：

- 内置 [claude_code_bridge.py](/E:/VibeCoding/tencent-doc-review/src/tencent_doc_review/access/claude_code_bridge.py)
- 默认会尝试自动探测：
  - 当前 Python 解释器
  - `claude` CLI
- 自动生成 bridge 启动参数

推荐最小配置：

```env
TENCENT_DOCS_TOKEN=your_tencent_docs_mcp_token
SKILL_MCP_CLIENT=claude_code
FACT_CHECK_MODE=auto
CLAUDE_CODE_MCP_BRIDGE_EXECUTABLE=
CLAUDE_CODE_MCP_BRIDGE_ARGS=
```

当前默认自动推断依赖：

- `claude` 命令在 PATH 中可用
- 当前 Python 可用于启动 bridge 脚本

如果自动探测失败，再手动填写：

- `CLAUDE_CODE_MCP_BRIDGE_EXECUTABLE`
  - Windows 通常填 `python`
  - macOS 通常填 `python3`
- `CLAUDE_CODE_MCP_BRIDGE_ARGS`
  - 一般会包含：
    - `claude_code_bridge.py` 的路径
    - `--claude-executable`
    - 你的 `claude` 路径
    - `--permission-mode acceptEdits`
    - `--cwd <project-root>`

需要注意：

- 这个 bridge 当前属于“最小闭环版本”，已经能承接统一下载 / 上传协议
- 但它仍然需要后续实机联调来确认不同机器上的权限、MCP 调用和上传行为
- 如果你的 Claude Code 环境在无头模式下仍然触发权限拦截，可能还需要按实际环境补充 bridge 参数

## 默认模板说明

当前默认模板分两层：

- 审核规则模板：
  - [`default_product_research_review_rules.md`](/E:/VibeCoding/tencent-doc-review/templates/default_product_research_review_rules.md)
- 结构模板：
  - [`default_product_research_structure_template.md`](/E:/VibeCoding/tencent-doc-review/templates/default_product_research_structure_template.md)

代码会优先读取根目录 [`templates`](/E:/VibeCoding/tencent-doc-review/templates)。

## 本地审核命令

使用默认模板审核本地文件：

```bash
tencent-doc-review analyze --input-file article.md --default-template --output report.md
```

输出 JSON：

```bash
tencent-doc-review analyze --input-file article.md --default-template --format json --output report.json
```

输出 HTML：

```bash
tencent-doc-review analyze --input-file article.md --default-template --format html --output report.html
```

## Skill 工作流命令

### Windows + OpenClaw

```powershell
tencent-doc-review skill-run ^
  --doc-id "your_doc_id" ^
  --title "your_doc_title" ^
  --target-folder-id "your_target_folder_id" ^
  --target-space-type personal_space ^
  --target-path "/更改" ^
  --download-dir "<project-root>\\downloads" ^
  --mcp-client openclaw ^
  --provider deepseek
```

### macOS + OpenClaw

```bash
tencent-doc-review skill-run \
  --doc-id "your_doc_id" \
  --title "your_doc_title" \
  --target-folder-id "your_target_folder_id" \
  --target-space-type personal_space \
  --target-path "/更改" \
  --download-dir "/path/to/tencent-doc-review/downloads" \
  --mcp-client openclaw \
  --provider deepseek
```

### macOS + Claude Code

```bash
tencent-doc-review skill-run \
  --doc-id "your_doc_id" \
  --title "your_doc_title" \
  --target-folder-id "your_target_folder_id" \
  --target-space-type personal_space \
  --target-path "/更改" \
  --download-dir "/path/to/tencent-doc-review/downloads" \
  --mcp-client claude_code \
  --provider deepseek
```

这条命令默认依赖：

- 你已经用 `claude mcp add ...` 配好了腾讯文档 MCP
- 本机 `claude` 命令可用
- 当前 Python 能启动 `claude_code_bridge.py`

## Claude Code 说明

当前项目：

- 已预留 `claude_code` 入口
- CLI 已支持 `--mcp-client claude_code`
- 协议层与 bridge 层都已抽象
- 配置层已支持 `FACT_CHECK_MODE`
- 已补 `claude_code_bridge.py` 最小 bridge 骨架
- 已补自动探测 `claude` CLI 与默认 bridge 参数生成逻辑

但需要明确：

- `OpenClaw` 已完成真实腾讯文档联调
- `Claude Code` 现在是“已有最小 bridge 闭环，待实机联调验证”

如果现在要稳定使用，仍然优先推荐 `OpenClaw`。

如果你准备把这个 GitHub 仓库直接发给 `Claude Code` 或 `OpenClaw` 辅助配置，建议先让它回答这三件事：

1. 当前运行环境是 `OpenClaw`、`Claude Code` 还是纯本地 CLI
2. 事实核查优先走 `agent`、`api` 还是 `auto`
3. 如果当前环境无法直连联网，是否现在配置 API Key

## 输出产物

在 [`downloads`](/E:/VibeCoding/tencent-doc-review/downloads) 下通常会生成：

- `*-annotated.docx`
- `*-annotated-compressed.docx`
- `*.review.md`

Word 文末会写入：

- 审核时间
- 审核模型
- 审核过程评分
- 各模块运行情况
- fallback 情况

## 常见问题

### 为什么现在多了 `FACT_CHECK_MODE`？

因为事实核查不一定总是靠搜索 API 完成。

在 `OpenClaw` 或 `Claude Code` 场景下，有些模型本身就具备联网搜索能力，所以现在需要显式区分：

- 当前是 Agent 直连联网
- 还是 API 联网
- 还是允许自动 fallback
- 还是完全离线

这比把所有联网事实核查都默认理解成“必须先配 API Key”更准确。

### 为什么模板找不到？

现在请优先看根目录：

- [`templates`](/E:/VibeCoding/tencent-doc-review/templates)

不要优先去 `src/tencent_doc_review/templates` 里找。

### 为什么上传后的文件名不对？

当前版本已经修复“临时下载目录名跑到腾讯文档标题里”的问题。

如果你还看到旧名称，优先确认是不是打开了旧上传链接。

### 为什么批注会跑到最后一段？

当前逻辑已经改成：

- 能可靠命中原文段落时，挂原文
- 找不到可靠锚点时，进入文末 `AI审核总结`

如果仍然看到挂正文最后一段，优先确认是不是旧版本产物。

## 开发验证

```bash
pytest tests/unit/test_phaseE_skill_workflow.py -q
pytest tests/unit/test_default_review_template.py -q
python -m compileall src/tencent_doc_review
```

## 许可

MIT License
