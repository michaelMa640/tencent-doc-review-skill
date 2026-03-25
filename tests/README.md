# 测试文档

## 概述

本项目包含三个层次的测试：

1. **单元测试** - 测试各个独立模块的功能
2. **集成测试** - 测试模块间的协作
3. **性能测试** - 测试系统性能和稳定性

## 目录结构

```
tests/
├── __init__.py
├── README.md
├── conftest.py              # 共享fixture
├── unit/                    # 单元测试
│   ├── __init__.py
│   ├── test_fact_checker.py
│   ├── test_structure_matcher.py
│   └── test_quality_evaluator.py
├── integration/             # 集成测试
│   ├── __init__.py
│   └── test_document_analyzer.py
└── performance/             # 性能测试
    ├── __init__.py
    └── test_performance.py
```

## 运行测试

### 运行所有测试

```bash
# 在项目根目录执行
python -m pytest tests/ -v
```

### 运行特定类型的测试

```bash
# 只运行单元测试
python -m pytest tests/unit/ -v

# 只运行集成测试
python -m pytest tests/integration/ -v

# 只运行性能测试
python -m pytest tests/performance/ -v
```

### 运行特定测试文件

```bash
python -m pytest tests/unit/test_fact_checker.py -v
```

### 运行特定测试函数

```bash
python -m pytest tests/unit/test_fact_checker.py::TestClaimExtraction::test_extract_claims -v
```

## 测试覆盖率

### 生成覆盖率报告

```bash
# 安装 coverage 工具
pip install pytest-cov

# 运行测试并生成覆盖率报告
python -m pytest tests/ --cov=tencent_doc_review --cov-report=html

# 生成终端覆盖率报告
python -m pytest tests/ --cov=tencent_doc_review --cov-report=term
```

## 性能基准

### 性能测试说明

性能测试位于 `tests/performance/` 目录，主要测试：

1. **文档大小性能** - 测试不同大小文档（1KB、10KB、100KB）的处理时间
2. **并发性能** - 测试并发分析和批量处理能力
3. **内存使用** - 监控大文档处理时的内存占用

### 性能基准目标

| 测试项 | 目标值 | 说明 |
|-------|-------|------|
| 小文档处理 | < 5秒 | 1KB文档 |
| 中等文档处理 | < 30秒 | 10KB文档 |
| 大文档处理 | < 90秒 | 100KB文档 |
| 并发处理 | < 60秒 | 5个文档并发 |
| 内存增长 | < 500MB | 处理3个大文档 |

## 测试配置

### Pytest 配置

项目根目录下的 `pytest.ini`（如果不存在可以创建）：

```ini
[pytest]
testpaths = tests
python_files = test_*.py
python_classes = Test*
python_functions = test_*
addopts = -v --tb=short
markers =
    slow: marks tests as slow (deselect with '-m "not slow"')
    integration: marks tests as integration tests
    performance: marks tests as performance tests
```

### 环境变量

测试可能需要以下环境变量：

```bash
# DeepSeek API 配置（可选，mock测试不需要）
export DEEPSEEK_API_KEY="your-api-key"
export DEEPSEEK_API_URL="https://api.deepseek.com"

# 腾讯文档 MCP 配置（可选）
export TENCENT_DOC_MCP_URL="http://localhost:3000"
```

## 编写测试的最佳实践

### 1. 测试命名

- 测试函数名应该清晰地描述测试的内容
- 使用 `test_` 前缀
- 示例：`test_extract_claims_from_text`

### 2. 使用 Fixture

- 使用 `@pytest.fixture` 创建可重用的测试数据
- 将 fixtures 放在 `conftest.py` 中以便跨文件共享

### 3. 参数化测试

```python
@pytest.mark.parametrize("input_text,expected_count", [
    ("简单文本", 0),
    ("2023年GDP增长5.2%", 1),
    ("A公司营收100亿，B公司营收200亿", 2),
])
def test_claim_count(self, input_text, expected_count):
    claims = extract_claims(input_text)
    assert len(claims) == expected_count
```

### 4. Mock 外部依赖

- 使用 `unittest.mock` 或 `pytest-mock` 来 mock 外部服务
- 避免在单元测试中调用真实的 API

### 5. 测试隔离

- 每个测试应该是独立的
- 不要在测试之间共享状态
- 使用 `setup_method` 和 `teardown_method` 进行清理

## 常见问题

### 1. 测试运行很慢

- 使用 `@pytest.mark.slow` 标记慢测试
- 运行时用 `-m "not slow"` 跳过慢测试
- 使用并行测试工具如 `pytest-xdist`

### 2. 测试不稳定（Flaky）

- 检查是否有时间依赖
- 确保测试之间的隔离性
- 使用 `pytest-rerunfailures` 重新运行失败的测试

### 3. 覆盖率不够

- 使用 `--cov-fail-under=80` 设置最低覆盖率要求
- 添加更多边界情况的测试
- 使用 `pytest-cov` 的 HTML 报告找出未覆盖的代码

## 联系与反馈

如有测试相关的问题或建议，请：

1. 查看项目的 Issue 列表
2. 创建新的 Issue 描述问题
3. 提交 Pull Request 改进测试

---

**最后更新**: 2026-03-25  
**维护者**: Dev Claw
