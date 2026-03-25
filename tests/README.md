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

Run the lightweight regression subset:

```bash
python -m unittest tests.unit.test_phase2_cli_flow tests.unit.test_phase3_llm_interface tests.unit.test_phase4_review_models
```

## Notes

- Most tests use mocked LLM responses.
- Real Tencent Docs writeback is not exercised in the current test suite.
- If you add external API tests, keep them isolated behind explicit markers.
- Current supported local baseline:
  - `pytest tests -q`
  - `python -m unittest tests.unit.test_phase2_cli_flow tests.unit.test_phase3_llm_interface tests.unit.test_phase4_review_models`

Maintainer: Michael Ma
