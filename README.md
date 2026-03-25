# 📝 腾讯文档智能审核批注工具

[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Code style: black](https://img.shields.io/badge/code%20style-black-000000.svg)](https://github.com/psf/black)

> 基于 LLM 的智能文章审核系统，自动进行事实核查、结构匹配、质量评估，并直接在腾讯文档中添加批注。

## ✨ 核心功能

### 🔍 事实核查 (Fact Checking)
- 自动识别文章中的关键信息（数据、人名、地名、时间等）
- 通过联网搜索验证信息准确性
- 标记存疑内容并提供修改建议
- 支持批量处理和多轮验证

### 🏗️ 结构匹配 (Structure Matching)
- 对比文档结构与标准模板
- 识别缺失章节、位置错位、额外内容
- 生成结构完整性报告
- 支持自定义模板配置

### ⭐ 质量评估 (Quality Assessment)
- 从 6 个维度进行多维度评估：
  - 内容完整性
  - 逻辑清晰度
  - 论证质量
  - 数据准确性
  - 语言表达
  - 格式合规
- 生成质量评分和改进建议
- 支持自定义评估权重

### 📝 腾讯文档集成
- 直接读取腾讯文档内容
- 自动在对应位置添加批注
- 支持批量处理多个文档
- 生成详细审核报告

---

## 🚀 快速开始

### 安装

```bash
# 从 PyPI 安装（推荐）
pip install tencent-doc-review

# 或从源码安装
git clone https://github.com/yourusername/tencent-doc-review.git
cd tencent-doc-review
pip install -e .
```

### 配置

创建配置文件 `config.yaml`：

```yaml
# DeepSeek API 配置
deepseek:
  api_key: "your-deepseek-api-key"
  api_url: "https://api.deepseek.com"
  model: "deepseek-chat"
  temperature: 0.3
  max_tokens: 4096

# 腾讯文档 MCP 配置
tencent_doc:
  app_id: "your-tencent-doc-app-id"
  app_secret: "your-tencent-doc-app-secret"
  mcp_url: "http://localhost:3000"

# 联网搜索配置（可选）
search:
  provider: "serper"  # 或 "bing", "google"
  api_key: "your-search-api-key"

# 日志配置
logging:
  level: "INFO"
  format: "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
  file: "logs/tencent-doc-review.log"
```

### 使用示例

#### 命令行使用

```bash
# 分析单个文档
tencent-doc-review analyze --doc-id "doc_xxx" --template-id "template_xxx"

# 批量分析目录下的所有文档
tencent-doc-review batch --folder-id "folder_xxx" --template-id "template_xxx"

# 生成质量报告
tencent-doc-review report --doc-id "doc_xxx" --output report.md

# 查看帮助
tencent-doc-review --help
```

#### Python API 使用

```python
import asyncio
from tencent_doc_review import DocumentAnalyzer
from tencent_doc_review.config import get_settings

async def main():
    # 加载配置
    settings = get_settings()
    
    # 创建分析器
    analyzer = DocumentAnalyzer(
        deepseek_client=settings.deepseek,
        mcp_client=settings.tencent_doc
    )
    
    # 分析文档
    result = await analyzer.analyze(
        document_text="""
        # 示例文档
        
        ## 1. 背景
        2023年中国GDP增长5.2%。
        
        ## 2. 内容
        人工智能市场规模达到1500亿美元。
        """,
        template_text="""
        # 模板
        
        ## 1. 背景
        ## 2. 内容
        ## 3. 结论
        """,
        document_id="example-doc-001",
        document_title="示例文档"
    )
    
    # 输出结果
    print(f"总体评分: {result.quality_report.overall_score}")
    print(f"质量等级: {result.quality_report.overall_level}")
    print(f"\n改进建议:")
    for i, suggestion in enumerate(result.recommendations, 1):
        print(f"  {i}. {suggestion}")

if __name__ == "__main__":
    asyncio.run(main())
```

---

## 📚 文档

- [快速开始指南](docs/quickstart.md)
- [API 文档](docs/api.md)
- [配置说明](docs/configuration.md)
- [CLI 使用指南](docs/cli.md)
- [开发指南](docs/development.md)
- [架构设计](docs/architecture.md)

---

## 🤝 贡献

欢迎贡献代码、报告问题或提出新功能建议！

### 贡献步骤

1. Fork 项目
2. 创建特性分支 (`git checkout -b feature/amazing-feature`)
3. 提交更改 (`git commit -m 'Add amazing feature'`)
4. 推送到分支 (`git push origin feature/amazing-feature`)
5. 创建 Pull Request

### 开发环境设置

```bash
# 克隆仓库
git clone https://github.com/yourusername/tencent-doc-review.git
cd tencent-doc-review

# 创建虚拟环境
python -m venv venv
source venv/bin/activate  # Linux/Mac
# 或
venv\Scripts\activate  # Windows

# 安装开发依赖
pip install -e ".[dev]"

# 运行测试
pytest tests/

# 运行代码格式化
black src/ tests/
isort src/ tests/

# 运行类型检查
mypy src/
```

---

## 📄 许可证

本项目采用 [MIT 许可证](LICENSE) 开源。

---

## 🙏 致谢

- [DeepSeek](https://deepseek.com/) - 提供强大的大语言模型
- [腾讯文档](https://docs.qq.com/) - 提供文档协作平台
- [MCP](https://modelcontextprotocol.io/) - Model Context Protocol
- [OpenClaw](https://openclaw.ai/) - AI Agent 平台

---

## 📞 联系方式

- 项目主页: https://github.com/yourusername/tencent-doc-review
- 问题反馈: https://github.com/yourusername/tencent-doc-review/issues
- 邮箱: dev@example.com

---

<p align="center">
  Made with ❤️ by Dev Claw
</p>
