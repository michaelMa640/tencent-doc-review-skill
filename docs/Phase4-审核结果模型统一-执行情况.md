# Phase 4 执行情况：审核结果模型统一

- 阶段: Phase 4
- 日期: 2026-03-25
- 状态: 已完成

## 本阶段目标

将事实核查、结构匹配、质量评估三类输出统一收敛到一套可序列化、可扩展、可直接用于报告和写回的审核结果模型。

## 本阶段任务状态

- [x] 统一 issue / result / report 数据结构
- [x] 统一严重级别
- [x] 统一建议格式
- [x] 统一序列化逻辑

## 本次完成内容

### 1. 新增统一领域模型

已新增 `src/tencent_doc_review/domain/review_models.py`，定义：

- `ReviewSeverity`
- `ReviewIssueType`
- `ReviewIssue`
- `ReviewReport`

统一模型具备以下特征：

- 所有问题都收敛为统一 `ReviewIssue`
- 严重级别统一为 `low / medium / high`
- 建议字段统一为 `suggestion`
- 所有结果都提供 `to_dict()`

### 2. 新增结果聚合层

已新增 `src/tencent_doc_review/domain/review_aggregator.py`，用于把现有三类分析结果聚合成统一视图：

- 事实核查结果转为 `ReviewIssue`
- 结构缺失/错位结果转为 `ReviewIssue`
- 质量低分维度转为 `ReviewIssue`
- 最终生成统一 `ReviewReport`

### 3. 主分析结果接入统一模型

已将 `DocumentAnalyzer` 的输出扩展为同时包含：

- 原始字段
  - `fact_check_results`
  - `structure_match_result`
  - `quality_report`
- 新统一字段
  - `review_issues`
  - `review_report`

这意味着现有调用方不需要立即改动，但后续 CLI、报告生成、腾讯文档写回都可以优先依赖统一模型。

### 4. 序列化与报告输出同步更新

已更新 `AnalysisResult`：

- `to_dict()` 现在会输出 `review_issues` 和 `review_report`
- `to_markdown()` 现在增加统一问题列表区块

## 验证结果

已新增 `tests/unit/test_phase4_review_models.py`，覆盖：

- 统一 `review_report` 已接入主分析结果
- `review_issues` / `review_report` 序列化稳定
- 统一 issue 的字段结构稳定

执行结果：

- `python -m unittest tests.unit.test_phase2_cli_flow tests.unit.test_phase3_llm_interface tests.unit.test_phase4_review_models` 通过
- `python -m compileall src/tencent_doc_review` 通过

## 当前结论

Phase 4 已完成。当前项目已经具备“兼容旧结果结构 + 提供统一审核结果模型”的双层输出能力，后续继续推进报告生成和腾讯文档写回时，不需要再直接依赖三个分析器各自不同的输出格式。

## 下一步建议

进入 Phase 5，继续做测试与稳定性：

1. 清理历史测试中的失配和乱码样本
2. 扩展对统一结果模型的覆盖
3. 收敛 CLI 和报告输出的回归测试
