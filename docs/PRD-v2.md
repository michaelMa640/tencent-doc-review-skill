# 基于 LLM 的腾讯文档文章审核工具 PRD v2

## 1. 文档信息

- 版本: v2
- 日期: 2026-03-25
- 状态: 待评审
- 目标读者: 产品、研发、测试、项目负责人

## 2. 背景与问题

当前项目的 v1 方案默认把“腾讯文档内原生批注写回”视为核心能力，但根据 2026-03-25 查阅的腾讯文档官方开放平台文档，现阶段可明确确认的能力主要包括:

- Open API: 文件管理、权限、搜索、通知、在线文档内容获取与更新
- MCP: 基于 Open API 的 MCP 兼容能力，适合 AI 工具调用
- SaaS 开放接口: 面向 SaaS 部署企业
- SDK/WebSDK: 文档预览等场景

当前官方文档中可以明确确认:

- 支持通过 Open API 获取 Doc 文档内容
- 支持通过 Open API 更新 Doc 文档内容
- 支持文件级新建、查询、移动、复制、删除、导入导出、权限管理

当前未在本轮查阅的官方文档中确认到“原生批注/comment API”作为稳定公开能力。因此，产品方案需要从“强依赖原生批注写回”调整为“以审核结果结构化输出为主，以文档内可定位写回为增强项”。

## 3. 产品目标

打造一个面向内容审核场景的腾讯文档 AI 审核工具，完成以下闭环:

1. 读取腾讯文档正文与模板
2. 基于 LLM 执行事实核查、结构匹配、质量评估
3. 生成结构化审核结果
4. 以可落地的方式回写审核结论
5. 输出标准化审核报告

## 4. 产品定位调整

### 4.1 v1 定位

- 目标: 直接向腾讯文档写入原生批注
- 风险: 过度依赖尚未确认的官方公开接口

### 4.2 v2 定位

- 核心定位: 腾讯文档 AI 审核与建议生成工具
- 主交付物: 审核报告 + 定位信息 + 可选文档写回
- 写回策略:
  - P0: 生成外部审核报告
  - P1: 在文档末尾或指定区域写入“审核建议区块”
  - P2: 若后续确认 MCP 或官方接口支持原生批注，再接入真实批注适配器

## 5. 目标用户

- 内容运营
- 编辑与审校
- 企业知识库管理员
- 需要批量审核腾讯文档的 AI 流程搭建者

## 6. 核心使用场景

### 场景 A: 单篇文章审核

用户输入文档 ID 与模板 ID，系统输出:

- 事实核查问题
- 结构缺失问题
- 质量评分
- 审核摘要
- 建议修改项

### 场景 B: 目录批量审核

用户输入文件夹 ID 与模板 ID，系统批量处理所有文档并输出汇总报告。

### 场景 C: 审核结果回写

系统将审核建议写入:

- Markdown 报告
- HTML 报告
- 腾讯文档末尾“审核建议”区块

### 场景 D: AI Agent / MCP 调用

在 Agent 工作流中，通过 MCP 或服务层接口直接触发腾讯文档读取、分析、报告生成。

## 7. 范围定义

### 7.1 本期范围

- 腾讯文档文件读取
- Doc 内容获取
- 模板结构比对
- LLM 质量评估
- 事实核查框架
- 审核报告生成
- 文档内建议区块写回
- CLI 与服务接口

### 7.2 暂不纳入本期

- 强依赖官方“原生批注 API”的实现
- 实时协同审阅 UI
- 复杂富文本逐字符级高精度批注锚定
- 完整工作流审批系统

## 8. 功能需求

### 8.1 文档接入层

必须支持:

- 通过 Open API 获取文档元数据
- 通过 Open API 获取 Doc 文档内容
- 通过文件接口遍历目录与文件
- 模板文档读取

扩展支持:

- 文件导入与导出
- 文档权限校验

### 8.2 审核引擎

包含三个核心模块:

- 事实核查
- 结构匹配
- 质量评估

输出统一结果模型:

- 文档基础信息
- 问题列表
- 风险等级
- 置信度
- 建议动作
- 汇总摘要

### 8.3 审核结果表达

每条问题至少包含:

- 问题类型
- 严重级别
- 命中的原文
- 原文定位信息
- 解释说明
- 修改建议
- 证据或依据

### 8.4 结果回写策略

v2 采用三级回写设计:

1. Report Writer
   - 输出 Markdown/JSON/HTML 报告
2. Doc Append Writer
   - 将审核结果写入文档末尾固定区块
3. Annotation Adapter
   - 抽象接口保留
   - 只有在确认官方/可用 MCP 工具支持原生批注时再启用

### 8.5 批量处理

支持:

- 文件夹遍历
- 并发处理
- 失败重试
- 进度回调
- 汇总报告

### 8.6 配置管理

必须支持:

- DeepSeek API Key
- 腾讯文档 Access Token / Client Id / Open Id 所需配置
- 搜索 API Key
- 并发与限流参数
- 审核模板配置

## 9. 非功能需求

### 9.1 稳定性

- 支持单篇失败不影响批量任务整体完成
- 外部接口异常可降级
- 输出必须可追踪

### 9.2 性能

- 遵守腾讯文档官方频率限制
- 文档读取、分析、写回分阶段限流
- 支持队列化批量处理

### 9.3 可维护性

- 接入层、分析层、输出层解耦
- MCP / Open API / 本地报告输出使用统一抽象
- 审核结果使用统一数据模型

### 9.4 合规性

- 权限按最小必要原则申请
- 文档内容默认不落盘或按配置控制脱敏存储
- 审核日志不记录敏感正文全文

## 10. 官方接口结论与产品影响

### 10.1 已确认能力

- 开放平台首页明确提供 Open API、MCP、SaaS、SDK 四类能力入口
- 文件管理接口提供文件新建、查询、移动、删除、复制、导入导出、权限、搜索、通知
- 在线文档接口明确支持“获取 Doc 文档内容”
- MCP 明确说明“基于 Open API 的能力兼容 MCP 协议”

### 10.2 关键产品影响

- 可以稳定做“读文档 + 分析 + 写报告 + 更新文档区块”
- 不应在 v2 把“原生批注写回”定义为上线阻塞项
- 批注能力应下沉为可替换适配层

### 10.3 当前判断

这是基于本轮查阅官方文档的结论。未发现明确公开的原生批注接口时，应将该能力视为“待验证能力”，而不是默认已可用能力。

## 11. 版本方案

### v2.0 MVP

- 打通 Open API 文档读取
- 打通文档分析引擎
- 输出 Markdown/JSON/HTML 报告
- 支持文档末尾审核建议区块写回
- 提供 CLI

### v2.1

- 支持文件夹批量审核
- 支持模板管理
- 支持结果聚合仪表盘数据输出

### v2.2

- 接入真实搜索 API 做事实交叉核验
- 优化定位与证据链
- 支持可配置的写回模板

### v2.3

- 若确认官方/可用 MCP 支持原生批注，再上线 Annotation Adapter

## 12. 技术方案

### 12.1 系统分层

- Connector Layer
  - Tencent Open API Client
  - MCP Adapter
  - Search Adapter
- Domain Layer
  - DocumentParser
  - FactChecker
  - StructureMatcher
  - QualityEvaluator
  - ReviewAggregator
- Delivery Layer
  - ReportGenerator
  - DocAppendWriter
  - AnnotationAdapter
- Interface Layer
  - CLI
  - Future Service API

### 12.2 核心数据流

1. 读取文件信息与正文
2. 解析文本与结构
3. 并行执行三类分析
4. 聚合为统一审核结果
5. 输出报告
6. 按策略写回腾讯文档

### 12.3 核心抽象

- `DocumentSource`
- `ReviewIssue`
- `ReviewResult`
- `ReviewWriter`
- `AnnotationWriter`

## 13. 开发方案

### 阶段 0: 纠偏与验证

目标:

- 修正文档与代码现状不一致问题
- 确认官方接口最小闭环

任务:

- 补齐腾讯文档客户端并统一到正式接入层
- 补齐 `cli.py`
- 清理不存在的导入和发布入口
- 安装依赖并跑通测试
- 新增接口能力验证脚本

交付:

- 可运行的最小工程
- 真实接口能力清单

### 阶段 1: 接入层落地

目标:

- 打通腾讯文档文件与在线文档读取

任务:

- 实现 OAuth / Token 处理
- 实现文件列表、元数据、文档内容获取
- 实现基础限流与重试
- 实现统一异常模型

交付:

- `tencent_openapi_client.py`
- 集成测试

### 阶段 2: 审核结果统一模型

目标:

- 把现有分析模块统一到稳定领域模型

任务:

- 统一 `FactCheckResult`、结构匹配结果、质量报告输出
- 增加问题严重级别与定位字段标准
- 增加结果序列化

交付:

- `review_models.py`
- `review_aggregator.py`

### 阶段 3: 输出与写回

目标:

- 实现真正可交付的审核输出

任务:

- Markdown/JSON/HTML 报告生成
- 文档末尾审核建议区块写回
- 预留 Annotation Adapter

交付:

- `report_generator.py`
- `doc_append_writer.py`

### 阶段 4: 批量处理与可运维

目标:

- 支持生产可用的批量审核流程

任务:

- 文件夹批处理
- 任务进度跟踪
- 失败重试
- 汇总报告
- 日志与观测指标

交付:

- `batch_processor.py`
- 批量任务测试

### 阶段 5: 发布

目标:

- 形成可安装、可运行、可维护交付物

任务:

- 完善 `pyproject.toml`
- 补齐 CLI 帮助与示例
- 补齐配置文档
- Docker 化

交付:

- 可安装包
- 使用文档
- Docker 镜像

## 14. 研发排期建议

### 2 周 MVP 排期

- 第 1-2 天: 阶段 0
- 第 3-5 天: 阶段 1
- 第 6-8 天: 阶段 2
- 第 9-10 天: 阶段 3
- 第 11-12 天: 联调与测试
- 第 13-14 天: 发布整理

## 15. 风险与对策

### 风险 1: 原生批注接口不可用

对策:

- 以报告输出和文档区块写回作为正式方案
- 批注写回只保留适配层

### 风险 2: 频控导致批量任务失败

对策:

- 设计 fileID/openID 双维度限流
- 对导入导出单独限频

### 风险 3: LLM 输出不稳定

对策:

- 使用结构化 JSON 提示词
- 增加解析兜底和错误恢复

### 风险 4: 文档定位精度不足

对策:

- 先支持段落级定位
- 后续再做字符级锚点优化

## 16. 验收标准

满足以下条件可视为 v2 MVP 完成:

- 能读取腾讯文档 Doc 内容
- 能执行三类审核
- 能输出结构化报告
- 能将审核摘要写回文档固定区块
- 能批量处理多个文档
- 能在频控下稳定运行

## 17. 建议的代码目录

```text
src/tencent_doc_review/
  __init__.py
  config.py
  cli.py
  connectors/
    tencent_openapi_client.py
    mcp_adapter.py
    search_adapter.py
  domain/
    review_models.py
    document_parser.py
    review_aggregator.py
  analyzer/
    fact_checker.py
    structure_matcher.py
    quality_evaluator.py
    document_analyzer.py
  writers/
    report_generator.py
    doc_append_writer.py
    annotation_adapter.py
  workflows/
    batch_processor.py
```

## 18. 官方资料

- 腾讯文档开放平台首页: https://docs.qq.com/open/document/
- 文件管理接口索引: https://docs.qq.com/open/document/app/openapi/v2/file/
- 获取 Doc 文档内容: https://docs.qq.com/open/document/app/openapi/v3/doc/get/get.html
- Open API 频率控制: https://docs.qq.com/open/document/app/openapi/v2/frequency_control.html
- 应用权限说明: https://docs.qq.com/open/document/app/scope.html
- MCP 概述: https://docs.qq.com/open/document/mcp/

## 19. Phase 任务清单

### Phase 1: MVP 定义与收口

- [x] 明确 MVP 目标边界
- [x] 明确 MVP 非目标
- [x] 固定主链路为 `CLI -> 本地文件 -> LLM -> 报告`
- [x] 补充 `.env.example`
- [x] 更新 README 的 MVP 使用说明
- 执行情况: [Phase1-MVP定义与收口](执行情况-v2/Phase1-MVP定义与收口.md)

### Phase 2: 主链路打通

- [x] 跑通 `tencent-doc-review analyze`
- [x] 确保本地文件读取稳定
- [x] 确保 Markdown / JSON 报告输出稳定
- [x] 补主流程异常处理
- [ ] 用真实 LLM provider 再验证一次主链路
- [ ] 补主链路回归测试
- 执行情况: [Phase2-主链路打通](执行情况-v2/Phase2-主链路打通.md)

### Phase 3: LLM 抽象层稳定化

- [ ] 统一内部命名为 `llm_client`
- [ ] 固化 provider 工厂
- [ ] 保持 `deepseek` 可用
- [ ] 保持 `openai` provider 骨架可切换
- 执行情况: 待开始

### Phase 4: 审核结果模型统一

- [ ] 统一 issue / result / report 数据结构
- [ ] 统一严重级别
- [ ] 统一建议格式
- [ ] 统一序列化逻辑
- 执行情况: 待开始

### Phase 5: 测试与稳定性

- [ ] 修正并更新核心测试
- [ ] 覆盖 CLI 主链路
- [ ] 覆盖 provider 工厂
- [ ] 覆盖报告输出
- 执行情况: 待开始

### Phase 6: 腾讯文档读取接入

- [ ] 验证腾讯文档读取接口
- [ ] 实现正文读取
- [ ] 统一本地输入与腾讯文档输入
- [ ] 补限流与错误处理
- 执行情况: 待开始

### Phase 7: 结果写回策略

- [ ] 实现固定区块写回
- [ ] 保留批注适配层
- [ ] 明确原生批注为后续增强项
- 执行情况: 待开始

### Phase 8: 发布与交付

- [ ] 清理打包配置
- [ ] 补安装文档
- [ ] 补示例命令
- [ ] 整理 Docker 路径
- 执行情况: 待开始
