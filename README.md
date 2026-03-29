# Tencent Doc Review Skill

基于 LLM 的腾讯文档审核与 Word 批注工具。

当前已经跑通过的主链路是：

1. 通过 OpenClaw + 腾讯文档 MCP 下载原始 `.docx`
2. 在本地生成带原生 Word 评论气泡的批注版 `.docx`
3. 超过 10MB 时自动压缩
4. 上传到腾讯文档指定位置

当前默认主模型是 `DeepSeek`，`MiniMax M2.7` 可作为并存备选模型。  
审核默认模板面向“产品调研报告”场景，支持：

- 语言问题审核
- 事实核查
- 结构完整性核对
- 前后矛盾检查
- 文末审核运行简报

## 当前状态

当前真实验证情况：

- 本地 `analyze` 可用
- OpenClaw 工作流已做过多轮真实联调
- Windows 已真实跑通
- macOS 代码路径已兼容，但你自己的 OpenClaw / Claude Code bridge 仍需本机联调
- Claude Code 在架构上已支持，但还没有像 OpenClaw 一样做完真实腾讯文档端到端验证

一句话说：

- 如果你现在要落地使用，优先走 `OpenClaw`
- 如果你后面要接 `Claude Code`，当前代码基础已经有了，但还需要做 bridge 实机验证

## 目录

```text
src/tencent_doc_review/
  access/        # OpenClaw / Claude Code bridge 与 MCP 访问层
  analyzer/      # 语言、事实、结构、矛盾审核器
  document/      # Word 解析、原生评论写入、压缩
  domain/        # 统一审核结果模型
  llm/           # DeepSeek / MiniMax provider
  skill/         # skill 输入输出协议
  templates/     # 默认审核规则与结构模板
  workflows/     # 主 workflow
  writers/       # Markdown / JSON / HTML 报告输出

downloads/       # 本地下载、批注版、压缩版输出目录
tests/           # 单元测试
```

## 运行环境

### Python

- Python `>=3.10`
- 已验证环境：Python `3.13.5`
- 推荐：Python `3.11` 或 `3.12`

### 运行时依赖

核心 Python 依赖来自 [pyproject.toml](/E:/VibeCoding/tencent-doc-review/pyproject.toml)：

- `httpx`
- `pydantic`
- `pydantic-settings`
- `python-docx`
- `Pillow`
- `loguru`
- `pyyaml`
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

根据使用方式不同，还需要这些外部条件：

- 纯本地审核：
  - 一个可用的 LLM API key
- 联网事实核查：
  - 一个可用的搜索 API key，目前已接入 `Tavily`
- 腾讯文档 skill 工作流：
  - 可用的 `OpenClaw CLI`
  - OpenClaw 中腾讯文档 MCP 可正常登录并可操作你的文档

## Windows 部署

### 1. 准备 Python

建议先确认：

```powershell
python --version
pip --version
```

如果你使用虚拟环境：

```powershell
cd E:\VibeCoding\tencent-doc-review
python -m venv .venv
.venv\Scripts\Activate.ps1
```

### 2. 安装项目

运行时安装：

```powershell
cd E:\VibeCoding\tencent-doc-review
pip install -e .
```

开发依赖安装：

```powershell
pip install -e ".[dev]"
```

如果你习惯 `requirements.txt`：

```powershell
pip install -r requirements.txt
```

### 3. 配置环境变量

复制模板：

```powershell
Copy-Item .env.example .env
```

然后编辑 [\.env.example](/E:/VibeCoding/tencent-doc-review/.env.example) 对应字段，至少填下面一组。

DeepSeek 默认配置：

```env
LLM_PROVIDER=deepseek
LLM_API_KEY=your_deepseek_key
LLM_BASE_URL=https://api.deepseek.com/v1
LLM_MODEL=deepseek-chat
```

MiniMax 可选配置：

```env
LLM_PROVIDER=minimax
LLM_API_KEY=your_minimax_key
LLM_BASE_URL=https://api.minimaxi.com/v1
LLM_MODEL=MiniMax-M2.7
```

联网事实核查配置：

```env
SEARCH_PROVIDER=tavily
SEARCH_API_KEY=your_tavily_key
SEARCH_BASE_URL=https://api.tavily.com/search
SEARCH_MAX_RESULTS=5
SEARCH_TIMEOUT=20
SEARCH_DEPTH=basic
SEARCH_TOPIC=general
```

OpenClaw bridge 配置示例：

```env
SKILL_MCP_CLIENT=openclaw
MCP_BRIDGE_TIMEOUT=240
OPENCLAW_MCP_BRIDGE_EXECUTABLE=python
OPENCLAW_MCP_BRIDGE_ARGS=E:\VibeCoding\tencent-doc-review\src\tencent_doc_review\access\openclaw_bridge.py --openclaw-executable C:\Users\你的用户名\AppData\Roaming\npm\openclaw.cmd --agent-id main --no-local
```

### 4. 验证配置

```powershell
tencent-doc-review doctor
```

## macOS 部署

### 1. 准备 Python

建议确认：

```bash
python3 --version
pip3 --version
```

创建虚拟环境：

```bash
cd /path/to/tencent-doc-review
python3 -m venv .venv
source .venv/bin/activate
```

### 2. 安装项目

```bash
pip install -e .
```

开发依赖：

```bash
pip install -e ".[dev]"
```

### 3. 配置环境变量

```bash
cp .env.example .env
```

macOS 的 OpenClaw bridge 一般是这样配置：

```env
SKILL_MCP_CLIENT=openclaw
MCP_BRIDGE_TIMEOUT=240
OPENCLAW_MCP_BRIDGE_EXECUTABLE=python3
OPENCLAW_MCP_BRIDGE_ARGS=/path/to/tencent-doc-review/src/tencent_doc_review/access/openclaw_bridge.py --openclaw-executable openclaw --agent-id main --no-local
```

如果你的 `openclaw` 不在 PATH 里，改成绝对路径。

### 4. 验证配置

```bash
tencent-doc-review doctor
```

## 默认审核模板

当前默认模板分成两层：

- 审核规则：[default_product_research_review_rules.md](/E:/VibeCoding/tencent-doc-review/src/tencent_doc_review/templates/default_product_research_review_rules.md)
- 结构模板：[default_product_research_structure_template.md](/E:/VibeCoding/tencent-doc-review/src/tencent_doc_review/templates/default_product_research_structure_template.md)

CLI 中可以直接用：

```bash
tencent-doc-review analyze --input-file article.md --default-template --output report.md
```

## 本地审核用法

### 1. 审核本地文件

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

### 2. 审核腾讯文档正文并生成报告

```bash
tencent-doc-review analyze --doc-id "your_doc_id" --default-template --output report.md
```

## Skill 工作流用法

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
  --bridge-executable python ^
  --bridge-args "E:\VibeCoding\tencent-doc-review\src\tencent_doc_review\access\openclaw_bridge.py --openclaw-executable C:\Users\你的用户名\AppData\Roaming\npm\openclaw.cmd --agent-id main --no-local" ^
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
  --bridge-executable python3 \
  --bridge-args "/path/to/tencent-doc-review/src/tencent_doc_review/access/openclaw_bridge.py --openclaw-executable openclaw --agent-id main --no-local" \
  --provider deepseek
```

### 输出内容

`skill-run` 会生成：

- 原始下载 Word
- 批注版 Word
- 压缩后的上传版 Word
- Markdown 审核报告

当前批注形式：

- 句级问题：Word 原生评论气泡
- 整篇层面问题：文末 `AI审核总结`

## Claude Code 说明

当前代码已经预留 `claude_code` 入口：

- CLI 已支持 `--mcp-client claude_code`
- 协议层已抽象
- bridge 配置入口已留好

但需要明确：

- `OpenClaw` 已做真实腾讯文档联调
- `Claude Code` 目前还是“架构支持，待真实 bridge 验证”

也就是说：

- 可以为 Claude Code 接入
- 但目前项目默认推荐的生产使用路径仍然是 `OpenClaw`

## 输出与日志

### 常见输出文件

在 [downloads](/E:/VibeCoding/tencent-doc-review/downloads) 下常见产物有：

- `*-annotated.docx`
- `*-annotated-compressed.docx`
- `*.review.md`

### 审核运行简报

当前 Word 文末会写入：

- 审核时间戳
- 审核模型
- 审核过程评分
- 质量评估状态
- 结构核对状态
- 事实核查状态
- 语言审核状态
- 矛盾检查状态

## 常见问题

### 1. 为什么上传后的文件名不对？

当前版本已经修复“临时目录名跑到远端标题里”的问题。  
如果仍然出现异常，优先检查：

- 你是否运行的是旧版本代码
- OpenClaw 是否复用了旧上下文
- 目标腾讯文档是否其实是旧上传链接

### 2. 为什么批注会跑到最后一段？

当前逻辑已经改成：

- 能可靠命中原文段落时，挂原文
- 找不到可靠锚点时，进入文末 `AI审核总结`

如果你还看到“批注挂在正文最后一段”，优先排查是否打开的是旧上传文档。

### 3. 为什么事实核查有时没有侧边批注？

因为现在的策略是：

- 只有“有问题的事实项”才进入事实核查详细输出
- 确认无问题的事实，不会堆到文末
- 搜索层如果没有找到可靠冲突来源，也不会强行标红

### 4. 为什么重新运行时本地文件覆盖失败？

如果某个 `.docx` 正被 Word、WPS 或腾讯文档同步进程占用，压缩阶段可能失败。  
最稳妥的方式：

- 关闭正在打开的目标文件
- 或换一个新的 `--download-dir`

### 5. Windows 中文路径安全吗？

当前项目能处理中文路径，但在某些 PowerShell / 控制台编码场景下，终端显示可能乱码。  
如果你只关心稳定运行，优先建议：

- 项目目录用正常英文路径
- 输出目录可用英文或中文，但要确保当前 Python 进程有写权限

## 开发验证

运行核心回归：

```bash
pytest tests/unit/test_phaseE_skill_workflow.py -q
python -m compileall src/tencent_doc_review
```

## 许可

MIT License
