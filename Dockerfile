# 腾讯文档智能审核批注工具 - Docker 镜像
# 
# 构建命令:
#   docker build -t tencent-doc-review:latest .
#
# 运行命令:
#   docker run -it --rm -v $(pwd)/config:/app/config tencent-doc-review:latest
#
# 使用 docker-compose:
#   docker-compose up -d

# ============================================
# 第一阶段：构建阶段
# ============================================
FROM python:3.11-slim as builder

# 设置工作目录
WORKDIR /build

# 安装构建依赖
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    g++ \
    libc6-dev \
    libffi-dev \
    && rm -rf /var/lib/apt/lists/*

# 复制依赖文件
COPY requirements.txt .

# 创建虚拟环境并安装依赖
RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"
RUN pip install --no-cache-dir --upgrade pip setuptools wheel && \
    pip install --no-cache-dir -r requirements.txt

# ============================================
# 第二阶段：生产阶段
# ============================================
FROM python:3.11-slim as production

# 设置元数据
LABEL maintainer="Dev Claw <dev@example.com>"
LABEL description="腾讯文档智能审核批注工具 - 基于LLM的文章审核系统"
LABEL version="0.1.0"

# 设置环境变量
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONIOENCODING=utf-8 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PATH="/opt/venv/bin:$PATH" \
    APP_HOME=/app \
    CONFIG_PATH=/app/config \
    LOG_PATH=/app/logs

# 设置工作目录
WORKDIR $APP_HOME

# 安装系统依赖
RUN apt-get update && apt-get install -y --no-install-recommends \
    ca-certificates \
    curl \
    && rm -rf /var/lib/apt/lists/* \
    && apt-get clean

# 从构建阶段复制虚拟环境
COPY --from=builder /opt/venv /opt/venv

# 复制应用程序代码
COPY src/ $APP_HOME/src/
COPY config/ $APP_HOME/config/

# 创建必要的目录
RUN mkdir -p $LOG_PATH $CONFIG_PATH && \
    chmod -R 755 $APP_HOME

# 创建非 root 用户
RUN groupadd -r appgroup && \
    useradd -r -g appgroup -d $APP_HOME -s /bin/false appuser && \
    chown -R appuser:appgroup $APP_HOME

# 切换到非 root 用户
USER appuser

# 暴露端口（如果需要 HTTP API）
# EXPOSE 8000

# 健康检查
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD python -c "import tencent_doc_review; print('OK')" || exit 1

# 默认命令
CMD ["tencent-doc-review", "--help"]

# 入口点
ENTRYPOINT ["tencent-doc-review"]

# ============================================
# 第三阶段：开发阶段（可选）
# ============================================
FROM production as development

USER root

# 安装开发依赖
COPY requirements-dev.txt .
RUN pip install --no-cache-dir -r requirements-dev.txt

# 安装调试工具
RUN apt-get update && apt-get install -y --no-install-recommends \
    vim \
    git \
    && rm -rf /var/lib/apt/lists/*

# 复制测试代码
COPY tests/ $APP_HOME/tests/

# 切换到非 root 用户
USER appuser

# 默认命令（保持容器运行）
CMD ["tail", "-f", "/dev/null"]

# ============================================
# 多阶段构建说明
# ============================================
#
# 构建生产镜像:
#   docker build --target production -t tencent-doc-review:latest .
#
# 构建开发镜像:
#   docker build --target development -t tencent-doc-review:dev .
#
# 运行生产容器:
#   docker run --rm -v $(pwd)/config:/app/config tencent-doc-review:latest analyze --doc-id "xxx"
#
# 运行开发容器（交互式）:
#   docker run -it --rm -v $(pwd):/app tencent-doc-review:dev bash
#
# 使用 docker-compose:
#   docker-compose up -d
#
# ============================================
