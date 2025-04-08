#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
服务启动脚本：自动安装依赖并启动服务
Service startup script: Automatically install dependencies and start the service
"""

import os
import sys
import subprocess
import time

def install_dependencies():
    """安装必要的依赖"""
    print("正在检查并安装依赖...")
    
    packages = [
        "fastapi==0.109.2",
        "uvicorn==0.27.1",
        "pydantic==2.6.1",
        "websockets==12.0",
        "python-dotenv==1.0.1",
        "loguru>=0.7.2",
        "requests>=2.31.0",
        "playwright==1.41.2"
    ]
    
    for package in packages:
        print(f"安装 {package}...")
        try:
            subprocess.check_call([sys.executable, "-m", "pip", "install", package])
            print(f"✓ {package} 安装成功")
        except subprocess.CalledProcessError:
            print(f"✗ 无法安装 {package}")
            return False
    
    print("所有基本依赖已安装")
    return True

def install_playwright_browsers():
    """安装Playwright浏览器"""
    print("正在安装Playwright浏览器...")
    try:
        subprocess.check_call([sys.executable, "-m", "playwright", "install", "chromium"])
        print("✓ Playwright浏览器安装成功")
        return True
    except subprocess.CalledProcessError:
        print("✗ 无法安装Playwright浏览器")
        return False

def create_env_file():
    """创建环境变量文件（如果不存在）"""
    env_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env")
    if not os.path.exists(env_path):
        print("创建.env文件...")
        with open(env_path, "w") as f:
            f.write("""# 日志设置
LOG_LEVEL=INFO
LOG_FILE_PATH=logs/service.log

# 浏览器配置
BROWSER_TYPE=chromium
HEADLESS=true
FRONTEND_URL=http://localhost:3000

# 视图设置
VIEWPORT_WIDTH=1280
VIEWPORT_HEIGHT=800
PAGE_LOAD_TIMEOUT=60000
MODEL_LOAD_WAIT=5000

# 服务配置
PORT=9000

# 安全设置
API_KEY=app-9v8uNvGpo576ojUarkP8kZNT
API_KEY_REQUIRED=false
MAX_CONCURRENT_SESSIONS=5
""")
        print("✓ .env文件已创建")
        return True
    else:
        print("✓ .env文件已存在")
        return True

def main():
    print("==== 数字孪生浏览器服务安装程序 ====")
    print(f"Python版本: {sys.version}")
    
    # 步骤1：创建环境变量文件
    if not create_env_file():
        print("创建环境变量文件失败，继续安装...")
    
    # 步骤2：安装依赖
    if not install_dependencies():
        print("依赖安装失败，无法继续")
        return
    
    # 步骤3：安装Playwright浏览器
    if not install_playwright_browsers():
        print("Playwright浏览器安装失败，但将继续启动服务（某些功能可能不可用）")
    
    # 步骤4：启动服务
    print("\n开始启动服务...")
    try:
        # 重新加载环境变量，确保我们有最新值
        from dotenv import load_dotenv
        load_dotenv()
        
        port = int(os.getenv("PORT", "9000"))
        print(f"服务将在http://localhost:{port}上启动")
        print("启动中，请稍候...")
        
        # 启动服务
        # 使用相对导入，避免路径问题
        import uvicorn
        uvicorn.run("main:app", host="0.0.0.0", port=port, log_level="info")
        
    except Exception as e:
        print(f"启动服务时出错: {e}")
        print("请手动运行: python main.py")

if __name__ == "__main__":
    main() 