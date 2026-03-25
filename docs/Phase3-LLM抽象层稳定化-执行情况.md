# Phase 3 执行情况：LLM 抽象层稳定化

- 阶段: Phase 3
- 日期: 2026-03-25
- 状态: 已完成

## 本阶段目标

将项目中的 LLM 接入从“默认绑定 DeepSeek 命名”整理为“统一依赖 LLM 抽象接口”，同时保留对旧调用方式的兼容。

## 本阶段任务状态

- [x] 统一内部命名为 `llm_client`
- [x] 固化 provider 工厂
- [x] 保持 `deepseek` 可用
- [x] 保持 `openai` provider 骨架可切换

## 本次完成内容

### 1. 统一主流程接口命名

已将活跃代码中的主入口改为优先使用 `llm_client`：

- `DocumentAnalyzer`
- `FactChecker`
- `QualityEvaluator`
- `StructureMatcher`
- CLI 主链路

同时保留 `deepseek_client` 兼容参数，避免现有调用和历史测试立即失效。

### 2. 固化 provider 工厂边界

已在 `llm.factory` 中显式定义受支持 provider：

- `deepseek`
- `mock`
- `openai`

同时将 `SUPPORTED_PROVIDERS` 导出到包级接口，便于 CLI、文档和后续扩展共用。

### 3. 保持现有 provider 可用

- `deepseek` 仍为默认真实 provider
- `openai` provider 骨架仍可创建
- `mock` provider 继续作为本地回归与无密钥调试路径
- `deepseek_client.py` 继续保留为兼容导出层

### 4. 补充 Phase 3 回归测试

已新增 `tests/unit/test_phase3_llm_interface.py`，覆盖：

- `SUPPORTED_PROVIDERS` 显式导出
- `DocumentAnalyzer(llm_client=...)` 可用
- `DocumentAnalyzer(deepseek_client=...)` 兼容可用
- 子分析器接受 `llm_client` 参数

## 验证结果

- `python -m unittest tests.unit.test_phase2_cli_flow tests.unit.test_phase3_llm_interface` 通过
- `python -m compileall src/tencent_doc_review` 通过

## 当前结论

Phase 3 已完成。当前代码架构中，LLM provider 已从业务主流程里抽象出来，后续继续接入新 provider 时，不需要再把具体厂商名称带入分析器接口。

## 下一步建议

进入 Phase 4，统一审核结果模型：

1. 收敛 `fact_check / structure / quality` 三类输出结构
2. 定义统一的 issue / result / report 数据模型
3. 减少报告生成和结果聚合中的临时拼接逻辑
