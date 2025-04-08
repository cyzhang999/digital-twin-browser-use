@echo off
setlocal enabledelayedexpansion

echo ======================================================
echo 数字孪生浏览器操作服务 (MCP) 启动脚本
echo ======================================================
echo.

:: 检查Python环境
where python >nul 2>nul
if %ERRORLEVEL% neq 0 (
    echo [错误] 未找到Python。请安装Python并确保其在PATH中。
    echo 您可以从 https://www.python.org/downloads/ 下载Python。
    goto :error
)

:: 检查Python版本
python --version | findstr /i "Python 3" >nul
if %ERRORLEVEL% neq 0 (
    echo [错误] 需要Python 3。请安装Python 3或更高版本。
    goto :error
)

:: 检查虚拟环境
set VENV_DIR=.venv
set PYTHON_CMD=python

if exist %VENV_DIR%\Scripts\activate.bat (
    echo [信息] 使用虚拟环境...
    call %VENV_DIR%\Scripts\activate.bat
    set PYTHON_CMD=%VENV_DIR%\Scripts\python
) else (
    echo [警告] 未找到虚拟环境 (%VENV_DIR%)。使用系统Python。
)

:: 检查是否安装了必需的依赖
echo [信息] 检查依赖...
%PYTHON_CMD% -c "import playwright" 2>nul
if %ERRORLEVEL% neq 0 (
    echo [警告] 未找到Playwright。尝试安装...
    %PYTHON_CMD% -m pip install -r requirements-mcp.txt
    if %ERRORLEVEL% neq 0 (
        echo [错误] 安装依赖失败。请手动运行: pip install -r requirements-mcp.txt
        goto :error
    )
)

:: 检查是否安装了Playwright浏览器
echo [信息] 检查Playwright浏览器...
%PYTHON_CMD% -c "from playwright.sync_api import sync_playwright; print(sync_playwright().__enter__().chromium.executable_path)" 2>nul
if %ERRORLEVEL% neq 0 (
    echo [警告] 未找到Playwright浏览器。尝试安装...
    %PYTHON_CMD% -m playwright install
    if %ERRORLEVEL% neq 0 (
        echo [错误] 安装Playwright浏览器失败。请手动运行: playwright install
        goto :error
    )
)

:: 获取端口号
set PORT=9000
if exist .env (
    for /f "tokens=*" %%a in ('type .env ^| findstr PORT') do (
        set %%a
    )
)

:: 启动服务
echo.
echo [信息] 启动MCP服务，端口: %PORT%...
echo [信息] 服务启动后，可以访问: http://localhost:%PORT%
echo [信息] 按Ctrl+C结束服务
echo.

%PYTHON_CMD% main.py
if %ERRORLEVEL% neq 0 (
    echo [错误] 服务启动失败。请检查错误信息。
    goto :error
)

goto :end

:error
echo.
echo ======================================================
echo 启动失败。请查看上面的错误信息。
echo ======================================================
pause
exit /b 1

:end
endlocal 