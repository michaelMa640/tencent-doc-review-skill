# 更新日志

所有显著的变更都将记录在此文件中。

格式基于 [Keep a Changelog](https://keepachangelog.com/zh-CN/1.0.0/)，
并且本项目遵循 [语义化版本](https://semver.org/lang/zh-CN/)。

---

## [Unreleased]

### 计划中

- [ ] 支持更多文档平台（飞书文档、钉钉文档、Google Docs）
- [ ] 集成更多 LLM 提供商（OpenAI、Claude、文心一言等）
- [ ] 支持多语言文档审核
- [ ] Web UI 管理界面
- [ ] 审核规则自定义配置
- [ ] 审核历史记录和统计

---

## [0.1.0] - 2026-03-25

### 🎉 初始版本发布

这是项目的第一个稳定版本，包含完整的文章审核批注功能。

### ✨ 新增功能

#### 核心功能

- **事实核查 (Fact Checking)**
  - 自动识别文章中的关键信息（数据、人名、地名、时间等）
  - 通过联网搜索验证信息准确性
  - 标记存疑内容并提供修改建议
  - 支持批量处理和多轮验证

- **结构匹配 (Structure Matching)**
  - 对比文档结构与标准模板
  - 识别缺失章节、位置错位、额外内容
  - 生成结构完整性报告
  - 支持自定义模板配置

- **质量评估 (Quality Assessment)**
  - 从 6 个维度进行多维度评估：
    - 内容完整性
    - 逻辑清晰度
    - 论证质量
    - 数据准确性
    - 语言表达
    - 格式合规
  - 生成质量评分和改进建议
  - 支持自定义评估权重

#### 腾讯文档集成

- 直接读取腾讯文档内容
- 自动在对应位置添加批注
- 支持批量处理多个文档
- 生成详细审核报告

#### 命令行工具 (CLI)

- `tencent-doc-review` 或 `tdr` 命令
- 支持分析单个文档、批量处理、生成报告
- 交互式界面，美观的终端输出

### 📦 项目结构

```
tencent-doc-review/
├── src/
│   └── tencent_doc_review/       # 主包
│       ├── analyzer/             # 核心分析引擎
│       │   ├── fact_checker.py
│       │   ├── structure_matcher.py
│       │   ├── quality_evaluator.py
│       │   └── document_analyzer.py
│       ├── mcp_client.py         # 腾讯文档 MCP 客户端
│       ├── deepseek_client.py    # DeepSeek API 客户端
│       ├── config.py             # 配置管理
│       └── cli.py                # 命令行接口
│
├── tests/                        # 测试套件 (~59KB)
│   ├── unit/                     # 单元测试
│   ├── integration/              # 集成测试
│   └── performance/              # 性能测试
│
├── docs/                         # 文档 (待完善)
├── config/                       # 配置文件
├── pyproject.toml                # 打包配置
├── setup.cfg                     # 备选打包配置
├── README.md                     # 项目主页
├── CHANGELOG.md                  # 更新日志
└── LICENSE                       # MIT 许可证
```

### 🧪 测试覆盖

- **单元测试**: ~37KB，覆盖 3 个核心模块
- **集成测试**: ~15KB，覆盖完整分析流程
- **性能测试**: ~6.7KB，覆盖不同负载场景
- **总计**: ~59KB 测试代码

### 🔧 技术栈

- **Python**: 3.10+
- **HTTP 客户端**: httpx
- **数据验证**: Pydantic v2
- **配置管理**: Pydantic Settings
- **日志**: Loguru
- **CLI**: Click + Rich
- **测试**: Pytest
- **代码质量**: Black, isort, mypy, flake8

### 📊 项目统计

| 指标 | 数值 |
|-----|------|
| 源代码 | ~3,800 行 |
| 测试代码 | ~59 KB |
| 测试文件数 | 8 个 |
| 测试用例数 | 50+ |
| 开发时间 | ~15 小时 (3 天) |

### 📝 开发阶段

- **Phase 1**: 基础设施 ✅ (2026-03-24)
- **Phase 2**: 核心引擎 ✅ (2026-03-24)
- **Phase 3**: 集成测试 ✅ (2026-03-25)
- **Phase 4**: 打包发布 🚧 (进行中)

---

## [0.0.1] - 2026-03-24

### 🚧 初始开发

项目启动，完成基础架构搭建。

- 搭建项目结构
- 实现腾讯文档 MCP 客户端
- 实现 DeepSeek API 客户端
- 实现配置管理系统

---

## 版本说明

### 版本号规则

本项目遵循 [语义化版本](https://semver.org/lang/zh-CN/) 规范：

- **主版本号 (MAJOR)**:  incompatible API 更改
- **次版本号 (MINOR)**:  向后兼容的功能添加
- **修订号 (PATCH)**:  向后兼容的问题修复

### 版本标签

- **[Unreleased]**: 未发布的功能，正在开发中
- **[Yanked]**: 已撤回的版本，存在严重问题

---

## 如何更新此文件

### 添加新版本的步骤

1. 在 `[Unreleased]` 部分上方创建新的版本小节
2. 按照以下格式添加变更记录：

```markdown
## [X.Y.Z] - YYYY-MM-DD

### Added
- 新增功能描述

### Changed
- 变更描述

### Fixed
- 修复描述
```

3. 如果存在 `[Unreleased]` 部分，将对应的变更移动到新版本小节中

### 变更类型说明

- **Added**: 新添加的功能
- **Changed**: 现有功能的变更
- **Deprecated**: 即将移除的功能
- **Removed**: 已移除的功能
- **Fixed**: 问题修复
- **Security**: 安全相关的修复

---

**注意**: 本文档使用中文编写，但遵循 Keep a Changelog 的格式规范。
