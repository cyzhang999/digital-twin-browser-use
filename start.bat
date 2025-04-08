@echo off
setlocal enabledelayedexpansion

echo ===== 数字孪生浏览器操作服务启动脚本 =====
echo 正在检查环境...

:: 设置环境变量，确保使用UTF-8编码
set PYTHONIOENCODING=utf-8
chcp 65001 >nul

:: 检查Conda是否安装
where conda >nul 2>nul
if %errorlevel% neq 0 (
    echo [警告] 未检测到Conda，将使用当前Python环境
    goto :use_current_env
) else (
    echo 检测到Conda环境管理器
    goto :use_conda_env
)

:use_conda_env
echo.
echo 选择环境管理方式:
echo 1. 使用/创建Conda环境 (推荐)
echo 2. 使用当前Python环境
echo 3. 退出

choice /c 123 /n /m "请选择 [1-3]: "

if errorlevel 3 goto :exit
if errorlevel 2 goto :use_current_env
if errorlevel 1 goto :setup_conda

:setup_conda
echo.
echo 检查Conda环境...

:: 检查是否已存在digital-twin环境
conda env list | findstr "digital-twin" >nul
if %errorlevel% equ 0 (
    echo 已存在digital-twin环境，是否重建？
    echo 1. 使用现有环境
    echo 2. 重建环境 (将删除现有环境)
    echo 3. 返回主菜单
    
    choice /c 123 /n /m "请选择 [1-3]: "
    
    if errorlevel 3 goto :use_conda_env
    if errorlevel 2 (
        echo 正在删除现有环境...
        conda env remove -n digital-twin
        goto :create_conda_env
    )
    if errorlevel 1 (
        goto :activate_conda_env
    )
) else (
    goto :create_conda_env
)

:create_conda_env
echo 正在创建新的Conda环境 (digital-twin)...
echo 这可能需要几分钟时间，请耐心等待...
conda env create -f environment.yml
if %errorlevel% neq 0 (
    echo [错误] Conda环境创建失败
    echo 请检查environment.yml文件是否正确
    pause
    goto :exit
) else (
    echo Conda环境创建成功
    goto :activate_conda_env
)

:activate_conda_env
echo 正在激活Conda环境...
:: 使用call是为了确保脚本继续执行
call conda activate digital-twin
if %errorlevel% neq 0 (
    echo [警告] 通过conda activate命令激活环境失败，尝试使用conda run...
    :: 使用conda run作为备选方案
    set USE_CONDA_RUN=1
    echo 将使用conda run运行命令
) else (
    set USE_CONDA_RUN=0
)

echo 正在安装Playwright浏览器...
if %USE_CONDA_RUN% equ 1 (
    conda run -n digital-twin python -m playwright install chromium
) else (
    python -m playwright install chromium
)

if %errorlevel% neq 0 (
    echo [警告] Playwright浏览器安装失败，服务可能无法正常工作
)

goto :start_options

:use_current_env
echo.
echo 使用当前Python环境...
echo 正在安装必要依赖...

python -m pip install -r requirements.txt --no-warn-script-location
if %errorlevel% neq 0 (
    echo [警告] 部分依赖安装可能失败，继续尝试...
)

echo 安装Playwright浏览器...
python -m playwright install chromium
if %errorlevel% neq 0 (
    echo [警告] Playwright浏览器安装失败，服务可能无法正常工作
)

goto :start_options

:start_options
:: 设置环境变量
set PORT=9000
set FRONTEND_URL=http://localhost:3000
set HEADLESS=true
set BACKUP_FRONTEND_URL=

echo.
echo === 环境配置 ===
echo 端口: %PORT%
echo 前端URL: %FRONTEND_URL%
echo 无头模式: %HEADLESS%
echo.
echo 服务启动选项:
echo 1. 标准模式 (连接到前端)
echo 2. 备用页面模式 (使用本地测试页面)
echo 3. 显示浏览器窗口
echo 4. MCP服务 (多客户端协议服务)
echo 5. 返回主菜单
echo 6. 退出

choice /c 123456 /n /m "请选择操作 [1-6]: "

if errorlevel 6 goto :exit
if errorlevel 5 goto :use_conda_env
if errorlevel 4 goto :start_mcp
if errorlevel 3 goto :visible_browser
if errorlevel 2 goto :backup_page
if errorlevel 1 goto :start_service

:visible_browser
set HEADLESS=false
echo 已设置显示浏览器窗口模式
goto :start_service

:backup_page
echo 使用本地测试页面作为备用...
set BACKUP_FRONTEND_URL=file:///%~dp0test-page.html
echo 已设置备用页面: %BACKUP_FRONTEND_URL%
goto :start_service

:start_mcp
echo.
echo === 启动MCP服务 ===
echo 如需停止服务，请按Ctrl+C
echo.

if "%USE_CONDA_RUN%" equ "1" (
    conda run -n digital-twin python mcp_server.py
) else (
    python mcp_server.py
)

if %errorlevel% neq 0 (
    echo.
    echo [错误] MCP服务启动失败，错误代码: %errorlevel%
    pause
)
goto :exit

:start_service
echo.
echo === 启动服务 ===
echo 如需停止服务，请按Ctrl+C
echo.

:: 启动服务
if "%USE_CONDA_RUN%" equ "1" (
    conda run -n digital-twin python main.py
) else (
    python main.py
)

if %errorlevel% neq 0 (
    echo.
    echo [错误] 服务启动失败，错误代码: %errorlevel%
    pause
)

:exit
echo 退出脚本
exit /b 0 