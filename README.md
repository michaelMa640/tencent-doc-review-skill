# Tencent Doc Review Skill

基于 LLM 的腾讯文档审核与批注工具。当前主路径是：

- 通过 MCP 下载原始 `.docx`
- 在本地生成批注版和压缩版 `.docx`
- 超过上传限制时自动压缩
- 上传到腾讯文档指定位置

## 能力概览

- 语言质量检查
- 事实核查框架
- 结构匹配
- 本地 Word 批注导出
- OpenClaw / Claude Code bridge
- Markdown / JSON / HTML 报告输出

## 安装

```bash
pip install -e .
```

开发依赖：

```bash
pip install -e ".[dev]"
```

## 环境变量

```bash
LLM_PROVIDER=deepseek
LLM_API_KEY=your_llm_key
LLM_BASE_URL=https://api.deepseek.com/v1
LLM_MODEL=deepseek-chat

TENCENT_DOCS_TOKEN=your_access_token
TENCENT_DOCS_CLIENT_ID=your_client_id
TENCENT_DOCS_OPEN_ID=your_open_id
TENCENT_DOCS_BASE_URL=https://docs.qq.com/openapi

SKILL_MCP_CLIENT=openclaw
MCP_BRIDGE_TIMEOUT=180
OPENCLAW_MCP_BRIDGE_EXECUTABLE=python
OPENCLAW_MCP_BRIDGE_ARGS=path/to/openclaw_bridge.py --openclaw-executable path/to/openclaw.cmd --agent-id main --no-local
```

## 常用命令

检查配置：

```bash
tencent-doc-review doctor
```

分析本地文件：

```bash
tencent-doc-review analyze --input-file article.md --template-file template.md --output report.md
```

输出 JSON：

```bash
tencent-doc-review analyze --input-file article.md --format json --output report.json
```

输出 HTML：

```bash
tencent-doc-review analyze --input-file article.md --format html --output report.html
```

## 默认审核模板

项目内置了默认的产品调研报告审核模板：

- [default_product_research_review_template.md](E:/VibeCoding/tencent-doc-review/src/tencent_doc_review/templates/default_product_research_review_template.md)

它默认覆盖三类检查：

- 语言问题核查
- 事实核查与来源链接
- 基于产品调研报告撰写要求的结构完整性检查

示例：

```bash
tencent-doc-review analyze --input-file article.md --template-file E:\VibeCoding\tencent-doc-review\src\tencent_doc_review\templates\default_product_research_review_template.md --output report.md
```

## Skill 工作流

```bash
tencent-doc-review skill-run ^
  --doc-id "your_doc_id" ^
  --title "your_doc_title" ^
  --target-folder-id "your_target_folder_id" ^
  --target-space-type personal_space ^
  --target-path "/target-folder" ^
  --download-dir "E:\\VibeCoding\\tencent-doc-review\\downloads" ^
  --mcp-client openclaw ^
  --bridge-executable python ^
  --bridge-args "path/to/openclaw_bridge.py --openclaw-executable path/to/openclaw.cmd --agent-id main --no-local"
```

## 目录说明

```text
src/tencent_doc_review/
  access/
  analyzer/
  document/
  domain/
  llm/
  skill/
  templates/
  workflows/

downloads/
  运行时下载与本地输出目录

tests/
  fixtures/
  unit/
  integration/
  performance/
```

## 说明

- `downloads/` 为本地运行产物目录，已忽略 Git 跟踪。
- `docs/` 和项目方案类文档默认视为本地内部文档，不再上传到 GitHub。

## 许可

MIT License
