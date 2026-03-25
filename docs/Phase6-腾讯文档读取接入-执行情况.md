# Phase 6 执行情况：腾讯文档读取接入

- 阶段: Phase 6
- 日期: 2026-03-25
- 状态: 已完成

## 本阶段目标

把腾讯文档读取能力从占位实现推进到可接入主链路的工程状态，包括正文读取、元数据读取、CLI 输入源统一、重试与错误处理。

## 本阶段任务状态

- [x] 验证腾讯文档读取接口
- [x] 实现正文读取
- [x] 统一本地输入与腾讯文档输入
- [x] 补限流与错误处理

## 本次完成内容

### 1. 增强腾讯文档客户端

已扩展 `src/tencent_doc_review/tencent_doc_client.py`：

- 增加 `get_document_info()`
- 增加 `get_document_content()`
- 增加 `get_document_bundle()`
- 增加统一请求入口 `_request_json()`
- 增加基础重试逻辑
- 增加统一异常模型：
  - `TencentDocError`
  - `TencentDocAuthError`
  - `TencentDocRateLimitError`
  - `TencentDocRequestError`

### 2. 实现正文与元数据统一读取

客户端现在可以同时获取：

- 文档标题、类型、时间等元数据
- Doc 正文文本

并将读取结果收敛到：

- `DocumentInfo`
- 提取后的纯文本正文

### 3. 统一本地输入与腾讯文档输入

已更新 CLI：

- 支持 `--input-file`
- 支持 `--doc-id`
- 支持 `--template-file`
- 支持 `--template-doc-id`

当前规则：

- `--input-file` 和 `--doc-id` 二选一
- `--template-file` 和 `--template-doc-id` 最多选一个

这意味着本地文件和腾讯文档已经能共用同一条分析主链路。

### 4. 主分析器接入腾讯文档 bundle

已更新 `DocumentAnalyzer.analyze_from_tencent_doc()`：

- 通过 `get_document_bundle()` 同时拿到标题与正文
- 分析结果中的 `document_title` 不再退化为 `file_id`

### 5. 配置与文档补齐

已新增腾讯文档读取重试配置：

- `TENCENT_DOCS_MAX_RETRIES`
- `TENCENT_DOCS_RETRY_DELAY`

并更新：

- `.env.example`
- `README.md`

## 验证结果

已新增 `tests/unit/test_phase6_tencent_doc_input.py`，覆盖：

- 腾讯文档客户端读取元数据与正文
- 429 场景下的重试行为
- 重试耗尽后的异常行为
- CLI `--doc-id` 输入路径

执行结果：

- `python -m unittest tests.unit.test_phase2_cli_flow tests.unit.test_phase3_llm_interface tests.unit.test_phase4_review_models tests.unit.test_phase6_tencent_doc_input` 通过
- `pytest tests -q` 通过
- 结果：`85 passed`
- `python -m compileall src/tencent_doc_review` 通过

## 当前结论

Phase 6 已完成。当前项目已经具备“本地文件输入 + 腾讯文档输入”双输入源能力，并且腾讯文档读取已经有可用的工程化接入层、基础重试与错误处理。

## 下一步建议

进入 Phase 7，开始结果写回策略：

1. 优先实现固定区块写回
2. 保留批注适配层接口
3. 避免把原生批注作为当前交付阻塞项
