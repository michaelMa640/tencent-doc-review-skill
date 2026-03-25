# Phase 8 执行情况：发布与交付
- 阶段: Phase 8
- 日期: 2026-03-25
- 状态: 已完成

## 本阶段目标
把项目从“开发中可运行”推进到“具备安装、验证、交付说明和 Docker 路径”的发布状态。

## 本阶段任务状态
- [x] 清理打包配置
- [x] 补安装文档
- [x] 补示例命令
- [x] 整理 Docker 路径

## 本次完成内容

### 1. 清理打包配置
- `pyproject.toml` 增加 `build` 到开发依赖，便于标准化构建
- `setup.cfg` 删除重复的 `pytest` 配置，消除 `pytest` 启动时的配置冲突警告
- CLI 正式支持 `--format html`，与现有 `ReportGenerator` 能力对齐

### 2. 完善安装与发布文档
已新增 `docs/Release-Guide.md`，补齐：
- 本地安装命令
- 开发依赖安装
- `.env` 配置方式
- 发布前验证命令
- 本地文件 / 腾讯文档 / HTML 输出的示例命令
- Docker 构建与运行示例

### 3. 重整 Docker 路径
已重写 `Dockerfile`：
- 不再依赖历史不稳定的多余构建逻辑
- 直接基于 `pyproject.toml` 安装项目
- 提供基础镜像和开发镜像两个 target
- 默认入口就是 `tencent-doc-review`

已新增 `.dockerignore`，避免把以下内容打进镜像上下文：
- `.git`
- `.env`
- `dist`
- `build`
- `htmlcov`
- `tests/.tmp`

### 4. README 补齐交付用法
README 已补充：
- 标准构建命令
- HTML 报告输出示例
- 发布说明入口

## 验证结果
- `python -m compileall src/tencent_doc_review` 通过
- `pytest tests -q` 通过，`91 passed`
- `python -m pip install --no-deps -e .` 通过
- `python -m pip wheel --no-deps . -w dist` 通过
- `tencent-doc-review doctor` 可执行

## 当前结论
Phase 8 已完成。当前仓库已经具备：
- 可安装的 Python CLI 包
- 清晰的环境变量与使用说明
- 可执行的发布前验证命令
- 可复用的 Docker 构建路径

## 版本判断
按当前范围，可以把项目视作 `v2.0 MVP 完成`，后续迭代应进入：

1. 批量处理与任务编排
2. 更真实的事实核查外部数据源
3. 原生批注能力的后续验证与适配
