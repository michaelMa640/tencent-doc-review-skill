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
cd E:\VibeCoding\tencent-doc-review
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
LLM_PROVIDER=deepseek
LLM_API_KEY=你的模型 key
```

如果你要收集某次审核的详细调试证据，还可以额外填写：

```env
REVIEW_DEBUG_OUTPUT_DIR=E:\VibeCoding\tencent-doc-review\debug-output
```

这样 `review-docx` / `skill-run` 会把解析结果、审核结果、锚点和产物路径写到这个目录里。

腾讯文档 MCP token 获取页面：

- [腾讯文档 OpenClaw 场景页](https://docs.qq.com/scenario/open-claw.html?nlc=1)

### 3. 确认环境正常

```bash
openclaw --help
tencent-doc-review doctor
tencent-doc-review debug-config
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

`OPENCLAW_MCP_BRIDGE_EXECUTABLE` 和 `OPENCLAW_MCP_BRIDGE_ARGS` 在 OpenClaw 主路径下通常可以留空，程序会自动：

- 使用当前 Python 解释器启动 bridge
- 使用项目内置的 [openclaw_bridge.py](/E:/VibeCoding/tencent-doc-review/src/tencent_doc_review/access/openclaw_bridge.py)
- 在系统 PATH 或常见安装目录中查找 `openclaw` / `openclaw.cmd`

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
  - 一个可用的搜索 API Key，目前接入的是 `Tavily`
- 腾讯文档端到端：
  - 可用的 `OpenClaw CLI`
  - OpenClaw 中腾讯文档 MCP 已登录且可正常访问你的文档
  - 如果使用 OpenClaw + 腾讯文档 MCP，请优先在腾讯文档 OpenClaw 场景页完成 token 获取或登录流程：[腾讯文档 OpenClaw 场景页](https://docs.qq.com/scenario/open-claw.html)

## Windows 部署

### 1. 创建虚拟环境

```powershell
cd E:\VibeCoding\tencent-doc-review
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
SEARCH_PROVIDER=tavily
SEARCH_API_KEY=your_tavily_key
SEARCH_BASE_URL=https://api.tavily.com/search
SEARCH_MAX_RESULTS=5
SEARCH_TIMEOUT=20
SEARCH_DEPTH=basic
SEARCH_TOPIC=general
```

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
MCP_BRIDGE_TIMEOUT=240
# 通常留空，程序会自动推断
OPENCLAW_MCP_BRIDGE_EXECUTABLE=
OPENCLAW_MCP_BRIDGE_ARGS=
```

macOS 示例：

```env
TENCENT_DOCS_TOKEN=your_tencent_docs_mcp_token
SKILL_MCP_CLIENT=openclaw
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
  --download-dir "E:\VibeCoding\tencent-doc-review\downloads" ^
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

## Claude Code 说明

当前项目：

- 已预留 `claude_code` 入口
- CLI 已支持 `--mcp-client claude_code`
- 协议层与 bridge 层都已抽象

但需要明确：

- `OpenClaw` 已完成真实腾讯文档联调
- `Claude Code` 目前还是“架构支持，待 bridge 实机联调”

如果现在要稳定使用，仍然优先推荐 `OpenClaw`。

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
