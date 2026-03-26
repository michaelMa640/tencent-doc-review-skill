# 基于 LLM 的腾讯文档文章审核批注工具 PRD v3

## 1. 文档信息

- 版本：v3
- 日期：2026-03-26
- 状态：进行中
- 适用对象：产品、研发、测试、项目负责人

## 2. 背景与问题

经过多轮真实联调，腾讯文档官方 MCP 的能力边界已经更清楚了：

- 可以读取腾讯文档内容
- 可以直接把腾讯文档下载为 `.docx`
- 可以把 `.docx` 下载到指定本地目录
- 可以把本地 Word 文档上传到腾讯文档指定位置
- 可以在个人空间中创建文件夹并上传进去
- 当前仍不适合把“在线原生批注”当作主交付路径

因此 v3 的真实主路径更新为：

`MCP 直接下载原始 .docx 到指定本地目录 -> 本地添加审核批注 -> MCP 上传到腾讯文档指定位置`

降级路径为：

`MCP 直接下载失败 -> 读取正文 -> 本地生成 .docx -> 本地添加审核批注 -> 上传到指定位置`

## 3. 产品目标

打造一个面向腾讯文档审核场景的 AI 工具，完成以下闭环：

1. 通过官方 MCP 定位目标腾讯文档
2. 优先下载原始 `.docx` 到指定目录
3. 下载失败时，降级为读取正文并本地生成 `.docx`
4. 基于 Word 文档执行结构检查、质量评估、事实核查
5. 在 Word 中写入审核标记与批注附录
6. 将带批注的 Word 上传到腾讯文档指定位置
7. 输出结构化审核报告

## 4. 产品定位

### 4.1 v3 核心定位

- 核心定位：腾讯文档到 Word 的 AI 审核批注工作流
- 主交付物：
  - 带审核标记的 `.docx`
  - 结构化审核报告
  - 上传结果信息

### 4.2 相对 v2 的关键变化

- v2 重点是“在线文档读取 + 报告/区块写回”
- v3 重点是“下载 Word + 本地批注 + 上传到指定位置”

### 4.3 当前方案判断

- 直接下载 `.docx` 已被真实验证可行，应作为优先路径
- 读取正文并本地生成 `.docx` 仍然保留，但只作为 fallback
- 在线原生批注继续降级为非当前主目标

## 5. 目标用户

- 内容运营
- 编辑与审核
- 企业知识库维护者
- 使用 OpenClaw / Claude Code 处理腾讯文档的个人用户

## 6. 核心使用场景

### 场景 A：单篇文档审核

1. 用户在 agent 中指定一篇腾讯文档
2. 系统优先下载原始 `.docx`
3. 本地添加审核批注
4. 上传到指定位置
5. 返回结果

### 场景 B：模板对照审核

1. 用户指定目标文档和模板文档
2. 两篇文档分别下载为 `.docx`，失败时降级为正文物化
3. 进行结构匹配与质量审核
4. 生成批注版 Word
5. 上传并返回结果

### 场景 C：Agent Skill 调用

1. OpenClaw / Claude Code 调用 skill
2. skill 下载或物化本地 Word
3. 调用审核引擎
4. 输出新文档与报告
5. 上传并返回链接和位置

## 7. 范围定义

### 7.1 本期范围

- 腾讯文档官方 MCP 接入
- Word 下载优先路径
- 正文物化 fallback 路径
- 本地 Word 解析与批注
- 结构匹配
- 质量评估
- 事实核查框架
- 上传到腾讯文档指定位置
- 报告输出
- CLI / Skill 双入口

### 7.2 暂不纳入本期

- 腾讯文档在线原生批注写回
- 自建 OpenAPI OAuth 全链路
- 复杂多人协同审核 UI
- 完整 SaaS 服务端

## 8. 功能需求

### 8.1 文档访问层

必须支持：

- 通过 MCP 定位目标文档
- 优先下载原始 `.docx`
- 支持指定本地下载目录
- 下载失败时读取正文并生成本地 `.docx`
- 上传处理后的 `.docx` 到腾讯文档指定位置

### 8.2 Word 处理层

必须支持：

- 读取 `.docx`
- 建立段落/标题/表格定位结构
- 写入审核标记和附录
- 导出新的 `.docx`

### 8.3 审核引擎

包含：

- 事实核查
- 结构匹配
- 质量评估

输出统一结果模型：

- 文档基本信息
- 问题列表
- 严重等级
- 原文命中
- 批注文本
- 修改建议
- 摘要

### 8.4 上传策略

1. Report Writer
   - 输出 Markdown / JSON / HTML 报告
2. Word Annotator
   - 在 `.docx` 中插入审核标记和附录
3. Upload Writer
   - 将带批注的 `.docx` 上传到腾讯文档指定位置

### 8.5 Skill 接口层

必须支持：

- 输入文档标识
- 输入目标空间/文件夹
- 输入本地下载目录
- 返回本地文件路径、上传结果、fallback 使用情况

## 9. 非功能需求

### 9.1 稳定性

- 下载、物化、审核、上传都可重试
- 本地临时文件可清理
- 单篇失败不影响批量任务

### 9.2 跨平台

- 优先兼容 Windows
- 同时兼容 macOS
- 路径统一使用 `pathlib`
- 不依赖 PowerShell 专属能力

### 9.3 可维护性

- 下载桥接、Word 处理、审核引擎、上传层解耦
- Skill 与 CLI 共用同一 workflow

## 10. 产品方案结论

### 10.1 当前主路径

`官方 MCP 下载原始 .docx -> 本地批注 -> 上传到腾讯文档指定位置`

### 10.2 Fallback 路径

`官方 MCP 直接下载失败 -> 读取正文 -> 本地生成 .docx -> 本地批注 -> 上传`

### 10.3 方案优势

- 保留原始排版和结构
- 与你的真实联调结果一致
- 仍保留无法下载时的兜底路径
- 适合 OpenClaw / Claude Code skill 化

## 11. 版本规划

### v3.0 MVP

- 接入 MCP 下载原始 `.docx`
- 支持指定本地下载目录
- 跑通本地审核引擎
- 生成批注版 `.docx`
- 上传到腾讯文档指定位置
- 输出审核报告

### v3.1

- 支持模板文档对照审核
- 支持批量处理
- 支持上传命名规则

### v3.2

- 支持更细粒度批注定位
- 支持修订模式
- 支持更丰富的 agent 元数据

## 12. 技术方案

### 12.1 系统分层

- Access Layer
  - Tencent Docs MCP Adapter
  - Download Manager
  - Upload Manager
  - OpenClaw / Claude Code Bridge
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
2. 优先下载 `.docx` 到本地目录
3. 下载失败时读取正文并物化 `.docx`
4. 解析 Word 结构
5. 执行审核分析
6. 写入审核标记
7. 导出新 `.docx`
8. 上传到腾讯文档指定位置
9. 输出结构化报告

### 12.3 核心抽象

- `TencentDocReference`
- `DownloadedDocument`
- `WordAnnotation`
- `AnnotatedDocument`
- `UploadTarget`
- `UploadResult`
- `ReviewIssue`
- `ReviewReport`

## 13. 开发方案

### Phase A：路径纠偏

- 从“在线写回优先”切到“下载 Word -> 批注 -> 上传”

### Phase B：MCP 下载与 fallback 物化链路

- 优先下载原始 `.docx`
- 下载失败时正文物化为 `.docx`
- 支持指定下载目录

### Phase C：Word 解析与批注

- 接入 Word 处理库
- 解析结构
- 生成审核标记

### Phase D：上传到腾讯文档指定位置

- 接入上传能力
- 支持目标空间/目标文件夹

### Phase E：Skill 化与跨平台整理

- 暴露 OpenClaw / Claude Code 共用输入输出
- 保留 CLI 底层入口

## 14. 风险与对策

### 风险 1：MCP 下载成功率受提示词影响

对策：

- Bridge prompt 显式要求优先下载
- 禁止 web search 路径干扰
- 保留正文 fallback

### 风险 2：Word comment 原生 API 仍有限

对策：

- 先用审核标记 + 附录交付 MVP

### 风险 3：上传目标空间语义不一致

对策：

- 显式区分 `space_type`、`space_id`、`folder_id`

## 15. 验收标准

- 能通过 MCP 直接下载目标腾讯文档为 `.docx`
- 能指定本地下载目录
- 能在下载失败时自动走正文物化 fallback
- 能生成带审核标记的 Word 文档
- 能上传到腾讯文档指定位置
- 能在 OpenClaw 中完成端到端操作

## 16. 资料与记录

- 腾讯文档开放平台：[https://docs.qq.com/open/document/](https://docs.qq.com/open/document/)
- 腾讯文档 MCP 概述：[https://docs.qq.com/open/document/mcp/](https://docs.qq.com/open/document/mcp/)
- 真实 MCP 能力验证记录：[真实MCP能力验证记录](执行情况-v3/真实MCP能力验证记录.md)
- 下载优先更新记录：[真实MCP能力验证记录-下载优先更新](执行情况-v3/真实MCP能力验证记录-下载优先更新.md)
- 真实联调结果：[真实联调结果](执行情况-v3/真实联调结果.md)

## 17. v3 开发计划

### Phase A：路径纠偏

- [x] 将主路径调整为 `MCP -> 下载原始 .docx -> 本地批注 -> 指定位置上传`
- [x] 将正文物化降级为 fallback
- [x] 将在线原生批注降级为非当前主目标
- 执行情况：[PhaseA-路径纠偏](执行情况-v3/PhaseA-路径纠偏.md)

### Phase B：MCP 下载与 fallback 物化链路

- [x] 定义下载与 fallback 协议
- [x] 支持指定下载目录
- [x] 保留正文物化 fallback
- 执行情况：[PhaseB-MCP文档下载链路](执行情况-v3/PhaseB-MCP文档下载链路.md)

### Phase C：Word 解析与批注

- [x] 接入 Word 处理库
- [x] 导出带审核标记的 `.docx`
- 执行情况：[PhaseC-Word解析与批注](执行情况-v3/PhaseC-Word解析与批注.md)

### Phase D：上传到腾讯文档指定位置

- [x] 接入 MCP 上传能力
- [x] 支持目标空间/目标文件夹
- 执行情况：[PhaseD-上传到腾讯文档指定位置](执行情况-v3/PhaseD-上传到腾讯文档指定位置.md)

### Phase E：Skill 化与跨平台整理

- [x] 抽象 OpenClaw / Claude Code 共用输入输出
- [x] 保留 CLI 作为底层执行器
- [x] 完成基础 bridge 适配层
- 执行情况：[PhaseE-Skill化与跨平台整理](执行情况-v3/PhaseE-Skill化与跨平台整理.md)
