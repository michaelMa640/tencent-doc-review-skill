# Tests

This repository contains unit, integration, and performance tests for the review engine.

## Layout

```text
tests/
  conftest.py
  unit/
  integration/
  performance/
```

## Run

```bash
python -m pytest tests/ -v
```

Run a subset:

```bash
python -m pytest tests/unit/ -v
python -m pytest tests/integration/ -v
python -m pytest tests/performance/ -v
```

## Notes

- Most tests use mocked LLM responses.
- Real Tencent Docs writeback is not exercised in the current test suite.
- If you add external API tests, keep them isolated behind explicit markers.

Maintainer: Michael Ma
