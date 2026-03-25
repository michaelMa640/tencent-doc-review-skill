@echo off
chcp 65001 >nul
echo ========================================
echo 文章审核批注工具 - 测试运行器
echo ========================================
echo.

:: 设置颜色
set "RESET="
set "GREEN="
set "YELLOW="
set "RED="
set "CYAN="

:: 检查 Python
where python >nul 2>&1
if %errorlevel% neq 0 (
    echo [错误] 未找到 Python，请确保 Python 已安装并添加到 PATH
    pause
    exit /b 1
)

:: 检查 pytest
python -c "import pytest" >nul 2>&1
if %errorlevel% neq 0 (
    echo [信息] 正在安装 pytest...
    python -m pip install pytest pytest-asyncio -q
    if %errorlevel% neq 0 (
        echo [错误] 安装 pytest 失败
        pause
        exit /b 1
    )
)

echo [信息] Python 版本:
python --version
echo.

:menu
cls
echo ========================================
echo 测试运行器菜单
echo ========================================
echo.
echo  [1] 运行所有测试
echo  [2] 运行单元测试
echo  [3] 运行集成测试
echo  [4] 运行性能测试
echo  [5] 生成覆盖率报告
echo  [6] 运行特定测试文件
echo  [7] 查看测试帮助
echo  [8] 退出
echo.
echo ========================================
set /p choice="请选择操作 [1-8]: "

if "%choice%"=="1" goto run_all
if "%choice%"=="2" goto run_unit
if "%choice%"=="3" goto run_integration
if "%choice%"=="4" goto run_performance
if "%choice%"=="5" goto run_coverage
if "%choice%"=="6" goto run_specific
if "%choice%"=="7" goto show_help
if "%choice%"=="8" goto end
goto menu

:run_all
echo.
echo ========================================
echo 运行所有测试
echo ========================================
echo.
python -m pytest tests/ -v --tb=short
echo.
pause
goto menu

:run_unit
echo.
echo ========================================
echo 运行单元测试
echo ========================================
echo.
python -m pytest tests/unit/ -v --tb=short
echo.
pause
goto menu

:run_integration
echo.
echo ========================================
echo 运行集成测试
echo ========================================
echo.
python -m pytest tests/integration/ -v --tb=short
echo.
pause
goto menu

:run_performance
echo.
echo ========================================
echo 运行性能测试
echo ========================================
echo 注意：性能测试可能需要较长时间
echo.
python -m pytest tests/performance/ -v --tb=short
echo.
pause
goto menu

:run_coverage
echo.
echo ========================================
echo 生成覆盖率报告
echo ========================================
echo.
echo [信息] 检查 pytest-cov...
python -c "import pytest_cov" >nul 2>&1
if %errorlevel% neq 0 (
    echo [信息] 正在安装 pytest-cov...
    python -m pip install pytest-cov -q
)
echo.
python -m pytest tests/ --cov=tencent_doc_review --cov-report=html --cov-report=term
echo.
echo [信息] HTML 覆盖率报告已生成: htmlcov/index.html
echo.
pause
goto menu

:run_specific
echo.
echo ========================================
echo 运行特定测试文件
echo ========================================
echo.
echo 可用的测试文件:
echo.
echo [1] tests/unit/test_fact_checker.py
echo [2] tests/unit/test_structure_matcher.py
echo [3] tests/unit/test_quality_evaluator.py
echo [4] tests/integration/test_document_analyzer.py
echo [5] tests/performance/test_performance.py
echo [6] 返回主菜单
echo.
set /p test_choice="请选择 [1-6]: "

if "%test_choice%"=="1" (
    python -m pytest tests/unit/test_fact_checker.py -v --tb=short
) else if "%test_choice%"=="2" (
    python -m pytest tests/unit/test_structure_matcher.py -v --tb=short
) else if "%test_choice%"=="3" (
    python -m pytest tests/unit/test_quality_evaluator.py -v --tb=short
) else if "%test_choice%"=="4" (
    python -m pytest tests/integration/test_document_analyzer.py -v --tb=short
) else if "%test_choice%"=="5" (
    python -m pytest tests/performance/test_performance.py -v --tb=short
) else (
    goto menu
)

echo.
pause
goto menu

:show_help
echo.
echo ========================================
echo 测试帮助
echo ========================================
echo.
echo 测试类型说明:
echo.
echo 单元测试 (Unit Tests):
echo   - 测试单个模块的功能
echo   - 隔离测试，不依赖外部服务
echo   - 运行速度快
echo.
echo 集成测试 (Integration Tests):
echo   - 测试模块间的协作
echo   - 验证完整业务流程
echo   - 可能依赖外部服务
echo.
echo 性能测试 (Performance Tests):
echo   - 测试系统性能指标
echo   - 包括响应时间、吞吐量等
echo   - 可能需要较长时间运行
echo.
echo 常用命令:
echo   python -m pytest tests/              # 运行所有测试
echo   python -m pytest tests/unit/       # 只运行单元测试
echo   python -m pytest -v                  # 显示详细输出
echo   python -m pytest -x                  # 遇到失败立即停止
echo   python -m pytest --tb=short          # 显示简短的错误信息
echo.
pause
goto menu

:end
echo.
echo 感谢使用测试运行器！
echo.
pause
exit /b 0
