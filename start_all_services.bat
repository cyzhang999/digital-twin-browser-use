@echo off
echo 数字孪生系统服务启动工具
echo ================================
echo.

echo 选择要启动的服务:
echo 1. 启动MCP服务 (Playwright浏览器代理)
echo 2. 启动Spring Boot后端服务
echo 3. 同时启动所有服务
echo.
set /p choice=请输入选项 (1-3): 

if "%choice%"=="1" (
    call :start_mcp
) else if "%choice%"=="2" (
    call :start_backend
) else if "%choice%"=="3" (
    call :start_all
) else (
    echo 无效的选项，请重新运行脚本
    goto :end
)

goto :end

:start_mcp
echo.
echo 正在启动MCP服务...
echo.
start cmd /k "cd /d %~dp0 && start_mcp_server.bat"
goto :eof

:start_backend
echo.
echo 请手动启动Spring Boot后端服务
echo.
goto :eof

:start_all
echo.
echo 正在启动所有服务...
echo.
call :start_mcp
call :start_backend
goto :eof

:end
echo.
echo 操作完成
pause 