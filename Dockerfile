# Tencent Doc Review Skill - Docker image
#
# Build:
#   docker build -t tencent-doc-review:latest .
#
# Run:
#   docker run --rm --env-file .env tencent-doc-review:latest doctor
#   docker run --rm --env-file .env -v ${PWD}/examples:/workspace tencent-doc-review:latest analyze --input-file /workspace/article.md --output /workspace/report.md

FROM python:3.11-slim AS base

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    ca-certificates \
    && rm -rf /var/lib/apt/lists/*

COPY pyproject.toml setup.cfg README.md LICENSE ./
COPY src ./src

RUN pip install --upgrade pip setuptools wheel && \
    pip install .

ENTRYPOINT ["tencent-doc-review"]
CMD ["--help"]

FROM base AS development

RUN pip install .[dev]
COPY tests ./tests

CMD ["doctor"]
