# Release Guide

## Scope
This project is released as a Python CLI package with optional Docker packaging.

## Local installation

```bash
pip install -e .
```

Install development dependencies:

```bash
pip install -e ".[dev]"
```

## Environment

Create a local `.env` based on `.env.example` and fill in only the keys you need:

```env
LLM_PROVIDER=deepseek
LLM_API_KEY=your_api_key
LLM_BASE_URL=https://api.deepseek.com/v1
LLM_MODEL=deepseek-chat

TENCENT_DOCS_TOKEN=your_access_token
TENCENT_DOCS_CLIENT_ID=your_client_id
TENCENT_DOCS_OPEN_ID=your_open_id
```

`.env` is ignored by Git and must not be committed.

## Verification

Run the following before a release:

```bash
python -m compileall src/tencent_doc_review
pytest tests -q
python -m pip install --no-deps -e .
python -m pip wheel --no-deps . -w dist
tencent-doc-review doctor
```

Optional package build:

```bash
python -m build
```

## Example commands

Analyze a local file:

```bash
tencent-doc-review analyze --input-file article.md --output report.md
```

Analyze a local file and emit HTML:

```bash
tencent-doc-review analyze --input-file article.md --format html --output report.html
```

Analyze a Tencent Docs document and append review notes:

```bash
tencent-doc-review analyze --doc-id "300000000$abc123" --template-doc-id "300000000$tpl456" --writeback-mode append --output report.md
```

## Docker

Build:

```bash
docker build -t tencent-doc-review:latest .
```

Run:

```bash
docker run --rm --env-file .env tencent-doc-review:latest doctor
```

Analyze a mounted local file:

```bash
docker run --rm --env-file .env -v ${PWD}/examples:/workspace tencent-doc-review:latest analyze --input-file /workspace/article.md --output /workspace/report.md
```

## Current release boundary

Included:
- Python package installation
- CLI commands
- Local file analysis
- Tencent Docs read + append writeback path
- Markdown / JSON / HTML outputs

Not included:
- Native Tencent Docs comment writeback
- Batch workflow packaging
- Long-running service deployment
