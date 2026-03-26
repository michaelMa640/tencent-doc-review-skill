# 基于 LLM 的腾讯文档文章审核批注工具 PRD v3

## 1. 文档信息

- 版本: v3
- 日期: 2026-03-25
- 状态: 草案
- 目标读者: 产品、研发、测试、项目负责人

## 2. 背景与问题

前一版方案默认把“直接在腾讯文档在线文档内写回审核结果或原生批注”作为主交付路径，但实际验证显示：

- 腾讯文档官方 MCP 在 OpenClaw 中可以跑通读取文档
- 当前未验证到稳定可用的“原生批注”能力
- 自建 OpenAPI 凭据链路在个人开发者场景下受 token / 权限限制，短期不稳定

因此产品路线调整为：

1. 优先使用腾讯文档官方 MCP 获取文档访问能力
2. 将目标文档下载为 Word 文档
3. 以本地 Word 文档为审核与批注载体
4. 审核后将带批注的 Word 文档上传到腾讯文档指定位置

这个路径避开了“在线原生批注接口不明确”的阻塞，把交付对象改成“带批注的 Word 成品”。

## 3. 产品目标

打造一个面向腾讯文档内容审核场景的 AI 工具，完成以下闭环：

1. 通过官方 MCP 找到目标腾讯文档
2. 将腾讯文档下载为 Word 文档
3. 基于 Word 文档执行结构检查、质量评估、事实核查
4. 在 Word 文档中添加批注和审核意见
5. 将带批注的 Word 文档上传到腾讯文档指定位置
6. 输出结构化审核报告，供 agent 或人工继续处理

## 4. 产品定位

### 4.1 v3 核心定位

- 核心定位: 腾讯文档到 Word 的 AI 审核批注工作流
- 主交付物:
  - 带批注的 `.docx` 文件
  - 结构化审核报告
  - 上传回执信息

### 4.2 与 v2 的关键差异

- v2 重点是“在线文档读取 + 报告/区块写回”
- v3 重点是“文档下载为 Word + 本地批注 + 再上传”

### 4.3 为什么这样调整

- 官方 MCP 已验证可作为文档访问层
- 在线原生批注能力当前不可靠
- Word 批注是更成熟、更可控、跨平台更稳定的实现路径
- 对 OpenClaw / Claude Code 这类 agent 更友好，便于把“下载、处理、上传”拆成明确步骤

## 5. 目标用户

- 内容运营
- 编辑与审核
- 企业知识库维护者
- 通过 agent 工作流处理腾讯文档内容的人

## 6. 核心使用场景

### 场景 A: 单篇文档审核

用户在 agent 中指定一篇腾讯文档，系统：

1. 通过 MCP 获取文档
2. 下载为 Word
3. 添加审核批注
4. 上传到指定位置
5. 返回处理结果

### 场景 B: 模板对照审核

用户指定“目标文档 + 模板文档”，系统：

1. 下载两份 Word / 文本内容
2. 进行结构匹配与质量审核
3. 在目标文档生成批注
4. 输出一份差异说明和新文件

### 场景 C: Agent Skill 调用

OpenClaw / Claude Code 等 agent 调用 skill：

1. 读取腾讯文档
2. 下载 Word
3. 调用本地审核引擎
4. 输出新文档与报告
5. 上传并返回链接/位置

## 7. 范围定义

### 7.1 本期范围

- 腾讯文档官方 MCP 接入
- 文档下载为 Word
- 本地 Word 解析与批注
- 结构匹配
- 质量评估
- 事实核查框架
- 带批注文档导出
- 上传到腾讯文档指定位置
- 结构化报告输出
- CLI / Skill 双入口设计

### 7.2 暂不纳入本期

- 腾讯文档在线原生批注写回
- 自建 OpenAPI OAuth 全链路
- 复杂多人协同审批 UI
- 完整 SaaS 服务端

## 8. 功能需求

### 8.1 文档访问层

必须支持：

- 通过官方 MCP 定位目标文档
- 获取文档标题、所属文件夹、下载入口
- 下载为 Word 文档
- 上传处理后的 Word 文档到指定文件夹或指定空间位置

扩展支持：

- 同时拉取模板文档
- 保留原始文档版本信息

### 8.2 Word 处理层

必须支持：

- 读取 `.docx`
- 按段落、标题、表格建立可定位结构
- 在 Word 中插入批注
- 导出新的 `.docx`

扩展支持：

- 修订模式
- 高亮问题段落
- 生成封面页或审核摘要页

### 8.3 审核引擎

包含三个核心模块：

- 事实核查
- 结构匹配
- 质量评估

输出统一结果模型：

- 文档基本信息
- 问题列表
- 严重等级
- 命中原文
- 批注文本
- 修改建议
- 汇总摘要

### 8.4 上传回写策略

v3 采用三级交付设计：

1. Report Writer
   - 输出 Markdown / JSON / HTML 报告
2. Word Annotator
   - 在 `.docx` 中插入批注
3. Upload Writer
   - 将带批注的 `.docx` 上传到腾讯文档指定位置

### 8.5 Skill 接口层

必须支持：

- 接收文档标识或 MCP 返回的文档对象
- 触发下载、审核、批注、上传全流程
- 返回结果摘要、文件路径、上传结果

## 9. 非功能需求

### 9.1 稳定性

- 单篇失败不影响批量任务
- 下载、审核、上传三阶段都可重试
- 本地临时文件要可清理

### 9.2 跨平台

- 首要兼容 Windows
- 同时兼容 macOS
- 核心流程不得依赖 PowerShell 专属能力
- 路径处理统一使用 `pathlib`

### 9.3 可维护性

- MCP 接入层、Word 处理层、审核引擎、上传层解耦
- Skill 入口与 CLI 共用同一核心流程

### 9.4 合规与安全

- 下载的 Word 文档默认存放到受控临时目录
- 审核日志不得写入全文敏感正文
- 上传前保留本地结果可选

## 10. 产品方案结论

### 10.1 当前判断

当前最可行路线不是“在线文档内原生批注”，而是：

`官方 MCP 读取腾讯文档 -> 下载为 Word -> 本地批注 -> 上传到腾讯文档指定位置`

### 10.2 方案优势

- 避开在线批注能力不稳定问题
- 复用 Word 成熟批注模型
- 便于 agent 工作流编排
- 更适合 Windows / macOS 双平台

### 10.3 方案代价

- 需要引入 Word 处理库
- 上传结果将是新文件或新版本，不是原在线文档内即时批注
- 文档生命周期要增加“下载中间件”管理

## 11. 版本规划

### v3.0 MVP

- 接入官方 MCP 读取文档
- 下载 Word
- 跑通本地审核引擎
- 在 Word 中插入批注
- 上传到指定位置
- 输出审核报告

### v3.1

- 支持模板文档对照审核
- 支持批量处理
- 支持上传命名规则

### v3.2

- 支持更精细的批注定位
- 支持修订模式
- 支持 agent 返回更丰富的元数据

## 12. 技术方案

### 12.1 系统分层

- Access Layer
  - Tencent Docs MCP Adapter
  - Download Manager
  - Upload Manager
- Document Layer
  - Word Parser
  - Word Annotation Writer
- Domain Layer
  - FactChecker
  - StructureMatcher
  - QualityEvaluator
  - ReviewAggregator
- Interface Layer
  - CLI
  - OpenClaw Skill
  - Claude Code Skill

### 12.2 核心数据流

1. Agent/MCP 定位腾讯文档
2. 下载为 `.docx`
3. 解析 Word 结构
4. 执行审核分析
5. 将问题写成 Word 批注
6. 导出新 `.docx`
7. 上传到腾讯文档指定位置
8. 输出结构化报告

### 12.3 核心抽象

- `TencentDocReference`
- `DownloadedDocument`
- `WordAnnotation`
- `AnnotatedDocument`
- `UploadResult`
- `ReviewIssue`
- `ReviewReport`

## 13. 开发方案

### Phase A: 路径纠偏

目标：

- 从“在线文档写回”切换到“Word 下载/批注/上传到指定位置”

任务：

- 更新 PRD
- 冻结自建 OpenAPI 主链路
- 明确官方 MCP 为首选访问层
- 明确上传目标为指定位置

交付：

- PRD v3
- 新版开发计划

### Phase B: MCP 文档下载链路

目标：

- 跑通“找到文档并下载为 Word”

任务：

- 定义 MCP 输入输出协议
- 实现文档下载管理器
- 定义本地缓存/临时目录策略

交付：

- `mcp_adapter.py`
- `download_manager.py`

### Phase C: Word 解析与批注

目标：

- 跑通 Word 文档处理链路

任务：

- 引入 Word 处理库
- 解析段落/标题/表格
- 生成批注
- 导出新文档

交付：

- `word_parser.py`
- `word_annotator.py`

### Phase D: 上传到腾讯文档指定位置

目标：

- 将带批注的文档上传到用户指定位置

任务：

- 接入 MCP 上传能力
- 支持指定目标文件夹/目标空间
- 定义命名规则

交付：

- `upload_manager.py`

### Phase E: Skill 化与跨平台整理

目标：

- 面向 OpenClaw / Claude Code 暴露稳定 skill 能力

任务：

- 设计 skill 输入输出
- 保留 CLI 底层能力
- 完成 Windows/macOS 路径与临时目录兼容

交付：

- skill 适配层
- 跨平台说明

## 14. 风险与对策

### 风险 1: 官方 MCP 不支持 Word 下载或上传

对策：

- 保留手动下载/上传降级路径
- skill 先支持“半自动流程”

### 风险 2: Word 批注库能力有限

对策：

- 先支持基础批注
- 复杂修订后置

### 风险 3: 上传到指定位置失败或目标位置不可写

对策：

- 采用“生成新文件并上传到指定位置”的模式
- 上传前校验目标位置可访问
- 明确命名规范，例如 `原文件名-审核批注版.docx`

## 15. 验收标准

满足以下条件可视为 v3.0 MVP 完成：

- 能通过 MCP 找到并下载目标腾讯文档
- 能在本地生成带批注的 Word 文档
- 能上传到腾讯文档指定位置
- 能输出结构化审核报告
- 能在 OpenClaw 中完成端到端操作

## 16. 建议的代码目录

```text
src/tencent_doc_review/
  __init__.py
  config.py
  cli.py
  access/
    mcp_adapter.py
    download_manager.py
    upload_manager.py
  document/
    word_parser.py
    word_annotator.py
  domain/
    review_models.py
    review_aggregator.py
  analyzer/
    fact_checker.py
    structure_matcher.py
    quality_evaluator.py
    document_analyzer.py
  outputs/
    report_generator.py
```

## 17. 官方资料

- 腾讯文档开放平台首页: https://docs.qq.com/open/document/
- 腾讯文档 MCP 概述: https://docs.qq.com/open/document/mcp/
- 应用权限说明: https://docs.qq.com/open/document/app/scope.html

## 18. v3 开发计划

### Phase A: 路径纠偏

- [x] 将主路径调整为 `MCP -> Word 下载 -> 本地批注 -> 指定位置上传`
- [x] 将在线原生批注降级为非当前主目标
- [x] 将上传目标改为“腾讯文档指定位置”
- [x] 创建 v3 执行记录目录与首个详细文档
- 执行情况: [PhaseA-路径纠偏](执行情况-v3/PhaseA-路径纠偏.md)

### Phase B: MCP 文档下载链路

- [x] 定义 MCP 输入输出协议
- [x] 设计下载管理器与临时目录策略
- [x] 明确 Word 下载产物命名规范
- [x] 定义目标文档与模板文档下载路径
- 执行情况: [PhaseB-MCP文档下载链路](执行情况-v3/PhaseB-MCP文档下载链路.md)

### Phase C: Word 解析与批注

- [x] 选型并接入 Word 处理库
- [x] 建立段落/标题/表格定位模型
- [x] 支持将审核问题写入 Word 批注
- [x] 导出带批注的新 `.docx`
- 执行情况: [PhaseC-Word解析与批注](执行情况-v3/PhaseC-Word解析与批注.md)

### Phase D: 上传到腾讯文档指定位置

- [x] 接入 MCP 上传能力
- [x] 支持指定目标空间/目标文件夹
- [x] 增加上传命名规则和冲突处理
- [x] 返回上传结果与新文件位置信息
- 执行情况: [PhaseD-上传到腾讯文档指定位置](执行情况-v3/PhaseD-上传到腾讯文档指定位置.md)

### Phase E: Skill 化与跨平台整理

- [x] 抽象 OpenClaw / Claude Code 共同输入输出
- [x] 保留 CLI 作为底层执行器
- [x] 完成 Windows / macOS 路径与临时目录兼容
- [x] 输出 skill 接入说明
- 执行情况: [PhaseE-Skill化与跨平台整理](执行情况-v3/PhaseE-Skill化与跨平台整理.md)
