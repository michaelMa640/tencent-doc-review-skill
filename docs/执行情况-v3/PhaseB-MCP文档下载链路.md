# Phase B 执行情况：MCP 文档下载链路

- 阶段: Phase B
- 日期: 2026-03-25
- 状态: 已完成

## 本阶段目标

把 v3 路线里的“官方 MCP -> 下载 Word -> 本地临时落盘”基础链路定义清楚，并形成可复用的访问层骨架。

## 本阶段任务状态

- [x] 定义 MCP 输入输出协议
- [x] 设计下载管理器与临时目录策略
- [x] 明确 Word 下载产物命名规范
- [x] 定义目标文档与模板文档下载路径

## 本次完成内容

### 1. MCP 协议模型落地

已新增 `src/tencent_doc_review/access/mcp_adapter.py`，定义：

- `TencentDocReference`
- `DownloadFormat`
- `MCPDownloadPayload`
- `MCPDocumentClient` 协议

这意味着后续无论是 OpenClaw、Claude Code 还是别的 MCP 客户端，只要能返回统一下载结果，就能接到同一条 Word 工作流里。

### 2. 下载管理器落地

已新增 `src/tencent_doc_review/access/download_manager.py`，提供：

- `DownloadManager`
- `DownloadPlan`
- `DownloadedDocument`

当前下载管理器负责：

- 计算临时下载目录
- 生成稳定文件名
- 将 MCP 返回的字节流落盘
- 保留目的用途，如 `document` / `template`

### 3. 临时目录策略确定

当前默认规则：

- 根目录: 系统临时目录下的 `tencent-doc-review/downloads`
- 子目录: 按 `doc_id` 建立目录
- 文件命名:
  - 普通文档: `文档标题.docx`
  - 模板文档: `文档标题-template.docx`

这一策略兼容 Windows 和 macOS，不依赖 PowerShell 特性。

### 4. 文件命名规范确定

命名规则已明确：

- 非法字符统一替换为 `-`
- 空标题回退到 `doc_id`
- 下载格式驱动扩展名

## 验证结果

已新增 `tests/unit/test_phaseB_mcp_download_flow.py`，覆盖：

- MCP 下载结果可落盘为 `.docx`
- 模板文档路径命名规则
- 非法字符文件名清洗

执行结果：

- `python -m unittest tests.unit.test_phaseB_mcp_download_flow` 通过
- `python -m compileall src/tencent_doc_review` 通过

## 当前结论

Phase B 已完成。项目现在已经有了稳定的 MCP 下载访问层骨架，后续可以在不改审核引擎的情况下继续推进 Word 解析与批注。

## 下一步建议

进入 Phase C，开始：

1. 选型 Word 批注处理库
2. 建立 Word 结构定位模型
3. 把审核问题写进 `.docx`
