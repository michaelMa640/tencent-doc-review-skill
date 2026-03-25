# Tencent Doc Review Skill

基于 LLM 的腾讯文档文章审核工具，当前默认接入 DeepSeek，但架构已支持按 provider 切换模型接入层。

## 当前能力

- 事实核查框架
- 结构匹配
- 质量评估
- 统一分析结果模型
- 本地 CLI
- 腾讯文档读取客户端占位实现
- Markdown / JSON 报告输出

## LLM 架构

- 分析器依赖统一 LLM 接口
- 当前内置 provider: `deepseek`
- 后续可以继续增加 `openai`、`qwen`、`claude` 等 provider
- `deepseek_client.py` 现在是兼容导出层，不再是唯一的架构入口

## 安装

```bash
pip install -e .
```

开发依赖:

```bash
pip install -e ".[dev]"
```

## 环境变量

```bash
LLM_PROVIDER=deepseek
LLM_API_KEY=your_llm_key
LLM_BASE_URL=https://api.deepseek.com/v1
LLM_MODEL=deepseek-chat

# 兼容旧配置，仍可继续使用
DEEPSEEK_API_KEY=your_deepseek_key
DEEPSEEK_BASE_URL=https://api.deepseek.com/v1
DEEPSEEK_MODEL=deepseek-chat

TENCENT_DOCS_TOKEN=your_access_token
TENCENT_DOCS_CLIENT_ID=your_client_id
TENCENT_DOCS_OPEN_ID=your_open_id
TENCENT_DOCS_BASE_URL=https://docs.qq.com/openapi
```

## CLI

检查配置:

```bash
tencent-doc-review doctor
```

分析本地文档:

```bash
tencent-doc-review analyze --input-file article.md --template-file template.md --output report.md
```

输出 JSON:

```bash
tencent-doc-review analyze --input-file article.md --format json --output report.json
```

## Python 用法

```python
import asyncio

from tencent_doc_review import create_llm_client
from tencent_doc_review.analyzer.document_analyzer import DocumentAnalyzer


async def main() -> None:
    client = create_llm_client(
        provider="deepseek",
        api_key="your-api-key",
        base_url="https://api.deepseek.com/v1",
        model="deepseek-chat",
    )
    analyzer = DocumentAnalyzer(deepseek_client=client)

    result = await analyzer.analyze(
        document_text="# 示例文档\n\n这里是待审核内容。",
        template_text="# 模板\n\n## 背景\n## 结论",
        document_title="示例文档",
    )

    print(result.to_markdown())
    await client.close()


asyncio.run(main())
```

## 代码结构

```text
src/tencent_doc_review/
  __init__.py
  cli.py
  config.py
  deepseek_client.py
  tencent_doc_client.py
  mcp_client.py
  llm/
    base.py
    factory.py
    providers/
      deepseek.py
  analyzer/
    document_analyzer.py
    fact_checker.py
    quality_evaluator.py
    structure_matcher.py
```

## 仓库

- Repository: [michaelMa640/tencent-doc-review-skill](https://github.com/michaelMa640/tencent-doc-review-skill)
- Email: michaelma640@163.com

## 许可

MIT License
