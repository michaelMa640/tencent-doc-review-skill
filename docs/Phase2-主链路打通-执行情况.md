# Phase 2 执行情况：主链路打通

- 阶段: Phase 2
- 日期: 2026-03-25
- 状态: 已完成

## 本阶段目标

打通一条可实际运行的主链路：

`CLI -> 读取本地文件 -> 调用 LLM -> 生成报告`

## 本阶段任务状态

- [x] 跑通 `tencent-doc-review analyze`
- [x] 确保本地文件读取稳定
- [x] 确保 Markdown / JSON 报告输出链路可用
- [x] 补主流程最小异常处理
- [x] 用真实 LLM provider 再验证一次主链路
- [x] 补主链路回归测试

## 本次完成内容

### 1. 重写主编排器

已将 `document_analyzer.py` 重写为更简单、可运行的版本，保留以下能力：

- 事实核查
- 结构匹配
- 质量评估
- 批量分析
- 报告保存

### 2. 补充本地验证 provider

新增 `mock` provider，用于不依赖真实 API Key 的端到端验证。

用途：

- 本地验证 CLI
- 快速检查主链路是否跑通
- 后续可用于主流程回归测试

### 3. 端到端验证结果

已使用以下链路完成实际验证：

`LLM_PROVIDER=mock -> CLI analyze -> 读取 sample-input.md -> 输出 sample-report.md`

验证结果：

- CLI 正常执行
- 本地文件读取正常
- Markdown 报告生成正常
- 结构、质量、事实三个模块都参与了结果聚合

### 4. 自动化回归测试

已新增 `tests/unit/test_phase2_cli_flow.py`，覆盖以下场景：

- `mock` provider 工厂创建
- CLI 生成 Markdown 报告
- CLI 生成 JSON 报告

执行结果：

- `python -m unittest tests.unit.test_phase2_cli_flow` 通过
- `python -m compileall src/tencent_doc_review` 通过

### 5. 真实 provider 联调

已使用 `.env` 中的真实 DeepSeek 配置完成联调验证。

联调前补充了两项必要修正：

- 在 fallback 配置路径中增加 `.env` 文件读取逻辑，避免缺少 `pydantic-settings` 时无法加载本地配置
- 安装 `httpx`，补齐真实 HTTP 调用依赖

联调方式：

- 使用 `deepseek` provider
- 读取本地测试文章与模板
- 输出临时 Markdown 报告 `tests/.tmp/real-provider-check/report.md`

联调结果：

- 真实 provider 请求已成功发出并返回
- 主链路可以在真实 DeepSeek 配置下完成执行
- 报告文件生成成功
- 当前事实核查与质量评估的提示词/解析质量仍需后续优化，但不影响 Phase 2 完成

## 当前结论

Phase 2 已完成当前代码范围内的收尾目标：

- 主链路可运行
- 本地输入稳定
- Markdown / JSON 输出稳定
- CLI 已支持 provider / api-key / base-url / model 覆盖参数
- 自动化回归测试已补齐

Phase 2 的计划项现已全部完成。

## 下一步建议

进入 Phase 3，继续做 LLM 抽象层稳定化：

1. 统一内部命名为 `llm_client`
2. 固化 provider 工厂与接口边界
3. 清理分析器中的历史命名和耦合
