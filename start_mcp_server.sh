#!/bin/bash

echo "正在启动数字孪生MCP服务..."
echo

# 检查Python是否安装
if ! command -v python3 &> /dev/null; then
    echo "[错误] 未检测到Python环境，请安装Python 3.7+"
    exit 1
fi

# 检查是否已安装依赖
echo "检查依赖库..."
if ! python3 -c "import fastapi" &> /dev/null; then
    echo "正在安装依赖库，这可能需要一些时间..."
    pip3 install -r requirements-mcp.txt
    if [ $? -ne 0 ]; then
        echo "[错误] 依赖库安装失败"
        exit 1
    fi
    echo "依赖库安装完成"
fi

# 检查Playwright是否已安装
if ! python3 -c "from playwright.async_api import async_playwright" &> /dev/null; then
    echo "正在安装Playwright..."
    pip3 install playwright
    python3 -m playwright install
    if [ $? -ne 0 ]; then
        echo "[错误] Playwright安装失败"
        exit 1
    fi
    echo "Playwright安装完成"
fi

echo
echo "启动MCP服务器 (端口: 9000)..."
python3 mcp_server.py 