# Phase 1 执行情况：MVP 定义与收口

- 阶段: Phase 1
- 日期: 2026-03-25
- 状态: 已完成

## 本阶段目标

把项目范围收口到最小可用闭环，避免继续在非关键能力上分散开发注意力。

MVP 定义为：

- 输入本地文档
- 调用可切换的 LLM provider
- 执行结构匹配、质量评估、事实核查
- 输出 Markdown / JSON 报告

## 本阶段任务

- [x] 明确 MVP 目标边界
- [x] 明确 MVP 非目标
- [x] 固定主链路为 `CLI -> 本地文件 -> LLM -> 报告`
- [x] 补充环境变量模板
- [x] 更新 README 为当前真实架构说明

## 实际产出

### 1. MVP 边界收口

已明确当前版本不是“腾讯文档原生批注系统”，而是“文章审核引擎 + 报告生成工具”。

### 2. 环境变量模板

新增文件：

- `.env.example`

覆盖：

- `LLM_PROVIDER`
- `LLM_API_KEY`
- `LLM_BASE_URL`
- `LLM_MODEL`
- 腾讯文档访问参数
- 搜索与运行参数

### 3. README 整理

README 已调整为当前真实状态：

- 说明 provider 化 LLM 架构
- 说明默认 provider 为 DeepSeek
- 提供 CLI 和 Python 最小使用示例
- 去除历史误导性表述

## 当前结论

Phase 1 已完成，项目下一步应进入 Phase 2，优先打通一条真正可运行的主链路：

`CLI -> 读取本地文件 -> 调用 LLM -> 生成 Markdown/JSON 报告`

## 风险与遗留

- 当前还有一批未提交代码改动，需要后续统一整理
- 腾讯文档真实读取链路尚未作为本阶段阻塞项处理
- 测试依赖与完整测试回归尚未作为本阶段目标

## 下一阶段建议

进入 Phase 2：

- 跑通 `tencent-doc-review analyze`
- 校正分析器输入输出
- 固化 Markdown / JSON 报告输出
