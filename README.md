# Tencent Doc Review Skill

基于 LLM 的腾讯文档审核与批注工具。当前项目已经切到真实可用的 v3 路线：

- 通过腾讯文档 MCP 直接下载原始 `.docx`
- 在本地生成批注版和压缩版 `.docx`
- 自动在上传前压缩超限文档
- 上传到腾讯文档指定位置

## 当前能力

- 结构匹配
- 质量评估
- 事实核查框架
- 本地 Word 批注导出
- OpenClaw / Claude Code skill 桥接
- Markdown / JSON / HTML 报告输出

## 安装

```bash
pip install -e .
```

开发依赖：

```bash
pip install -e ".[dev]"
```

检查本地配置：

```bash
tencent-doc-review doctor
```

## 环境变量

```bash
LLM_PROVIDER=deepseek
LLM_API_KEY=your_llm_key
LLM_BASE_URL=https://api.deepseek.com/v1
LLM_MODEL=deepseek-chat

DEEPSEEK_API_KEY=your_deepseek_key
DEEPSEEK_BASE_URL=https://api.deepseek.com/v1
DEEPSEEK_MODEL=deepseek-chat

TENCENT_DOCS_TOKEN=your_access_token
TENCENT_DOCS_CLIENT_ID=your_client_id
TENCENT_DOCS_OPEN_ID=your_open_id
TENCENT_DOCS_BASE_URL=https://docs.qq.com/openapi

SKILL_MCP_CLIENT=openclaw
MCP_BRIDGE_TIMEOUT=180
OPENCLAW_MCP_BRIDGE_EXECUTABLE=python
OPENCLAW_MCP_BRIDGE_ARGS=E:\\VibeCoding\\tencent-doc-review\\src\\tencent_doc_review\\access\\openclaw_bridge.py --openclaw-executable C:\\Users\\VBTvisitor\\AppData\\Roaming\\npm\\openclaw.cmd --agent-id main --no-local
```

## CLI

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

## Skill 工作流

### OpenClaw bridge

```bash
tencent-doc-review skill-run ^
  --doc-id "DUnF6UXJFRGNSV1NM" ^
  --title "副本-蝉镜产品调研报告-michael" ^
  --target-folder-id "RaVWacrBtGfN" ^
  --target-space-type personal_space ^
  --target-path "/更改" ^
  --download-dir "E:\\VibeCoding\\tencent-doc-review\\downloads" ^
  --mcp-client openclaw ^
  --bridge-executable python ^
  --bridge-args "E:\\VibeCoding\\tencent-doc-review\\src\\tencent_doc_review\\access\\openclaw_bridge.py --openclaw-executable C:\\Users\\VBTvisitor\\AppData\\Roaming\\npm\\openclaw.cmd --agent-id main --no-local"
```

### 真实联调结果

已验证成功的真实链路：

- MCP 直接下载原始 `.docx`
- 批注版直接生成在下载目录旁边
- 超过 10MB 时自动压缩
- 压缩后成功上传到腾讯文档个人空间目标文件夹

示例结果：

- 原始文件：[副本-产品质量调研报告-michael.docx](E:/VibeCoding/tencent-doc-review/downloads/副本-产品质量调研报告-michael.docx)
- 批注版：[副本-产品质量调研报告-michael-annotated.docx](E:/VibeCoding/tencent-doc-review/downloads/副本-产品质量调研报告-michael-annotated.docx)
- 压缩版：[副本-产品质量调研报告-michael-annotated-compressed.docx](E:/VibeCoding/tencent-doc-review/downloads/副本-产品质量调研报告-michael-annotated-compressed.docx)
- 远端链接：[https://docs.qq.com/doc/DUnJMcW9MTUtwV0xh](https://docs.qq.com/doc/DUnJMcW9MTUtwV0xh)

## `-compressed-1600` 是什么

像 `副本-产品质量调研报告-michael-annotated-compressed-1600.docx` 这样的文件，是压缩器在尝试某一档图片宽度时生成的中间试算文件。

现在代码已经改过：

- 中间试算文件只在压缩过程中临时存在
- 压缩完成后只保留最终的 `-annotated-compressed.docx`

## 项目目录

```text
src/tencent_doc_review/
  access/
    agent_mcp_client.py
    download_manager.py
    mcp_adapter.py
    openclaw_bridge.py
    upload_manager.py
  analyzer/
  document/
    docx_compressor.py
    word_annotator.py
    word_parser.py
  skill/
  workflows/
    skill_pipeline.py
  cli.py
  config.py

docs/
  PRD-v2.md
  PRD-v3.md
  执行情况-v3/

downloads/
  运行时下载与本地输出目录（已 git ignore）

tests/
  fixtures/
  unit/
```

## 目录约定

- `downloads/`：真实联调下载、批注版、压缩版输出目录
- `docs/执行情况-v3/`：v3 路线执行记录
- `tests/.tmp/`：测试临时目录，已忽略
- `.tmp/`：运行时临时目录，已忽略

## 仓库

- Repository: [michaelMa640/tencent-doc-review-skill](https://github.com/michaelMa640/tencent-doc-review-skill)
- Email: michaelma640@163.com

## 许可

MIT License
