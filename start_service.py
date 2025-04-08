#!/usr/bin/env python
"""
数字孪生浏览器服务启动脚本 (Digital Twin Browser Service Starter)

本脚本负责启动数字孪生项目的浏览器操作服务(MCP)。该服务通过Playwright
操作浏览器实例，使AI后端能够控制3D模型的显示和交互。

工作原理:
1. 启动一个FastAPI应用作为控制服务
2. 初始化一个Playwright浏览器实例（默认为headless模式）
3. 浏览器实例导航到前端页面（默认为http://localhost:3000）
4. 提供API接口接收来自后端的模型操作请求（旋转、缩放等）
5. 在浏览器实例中执行JavaScript代码来操作模型

重要提示:
* 服务启动后将自动打开一个浏览器实例，该实例是执行模型操作的关键环境
* 如果使用有头模式（--headless=false），请勿关闭打开的浏览器窗口
* 用户通过AI聊天发出的模型操作指令最终会在此浏览器实例中执行
* 该浏览器实例与用户自己打开的前端页面不是同一个实例

用法: python start_service.py [--headless] [--browser=firefox|webkit|chromium] [--port=9000] [--frontend-url=http://localhost:3000]
"""

import argparse
import logging
import os
import subprocess
import sys
import time
import socket
import requests
from datetime import datetime

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def parse_arguments():
    """解析命令行参数"""
    parser = argparse.ArgumentParser(description="启动数字孪生浏览器服务")
    
    parser.add_argument("--headless", action="store_true", help="使用无头模式运行浏览器")
    parser.add_argument("--browser", choices=["firefox", "webkit", "chromium"], default="chromium", 
                        help="选择浏览器类型 (默认: chromium)")
    parser.add_argument("--port", type=int, default=9000, help="服务端口 (默认: 9000)")
    parser.add_argument("--frontend-url", default="http://localhost:3000", 
                       help="前端URL (默认: http://localhost:3000)")
    parser.add_argument("--log-level", choices=["debug", "info", "warning", "error"], 
                       default="info", help="日志级别 (默认: info)")
    parser.add_argument("--dify-api-endpoint", help="Dify API端点")
    parser.add_argument("--dify-api-key", help="Dify API密钥")
    parser.add_argument("--timeout", type=int, default=120, help="连接保持超时时间（秒）(默认: 120)")
    parser.add_argument("--force-port", action="store_true", help="强制使用指定端口，若被占用则退出")
    
    return parser.parse_args()

def is_port_in_use(port):
    """检查端口是否被占用"""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        return s.connect_ex(('localhost', port)) == 0

def find_available_port(start_port, max_attempts=10):
    """查找可用端口"""
    for port in range(start_port, start_port + max_attempts):
        if not is_port_in_use(port):
            return port
    return None

def wait_for_service(port, max_attempts=30, interval=2):
    """等待服务启动"""
    logger.info(f"等待服务启动在端口 {port}...")
    url = f"http://localhost:{port}/health"
    
    for attempt in range(max_attempts):
        try:
            response = requests.get(url, timeout=5)
            if response.status_code == 200:
                data = response.json()
                logger.info(f"服务已启动，状态: {data.get('status', 'unknown')}")
                return True
        except Exception:
            pass
        
        time.sleep(interval)
        logger.info(f"等待服务启动... ({attempt + 1}/{max_attempts})")
    
    logger.error(f"服务启动超时，请检查日志")
    return False

def is_playwright_installed():
    """检查Playwright是否安装"""
    try:
        import playwright
        return True
    except ImportError:
        return False

def install_playwright(browser_type):
    """安装Playwright及浏览器"""
    logger.info("安装Playwright...")
    try:
        subprocess.run([sys.executable, "-m", "pip", "install", "playwright"], check=True)
        
        logger.info(f"安装Playwright {browser_type}浏览器...")
        subprocess.run([sys.executable, "-m", "playwright", "install", browser_type], check=True)
        
        return True
    except subprocess.CalledProcessError as e:
        logger.error(f"安装Playwright失败: {e}")
        return False

def kill_process_on_port(port):
    """终止占用指定端口的进程"""
    try:
        if sys.platform.startswith('win'):
            cmd = f'netstat -ano | findstr :{port}'
            output = subprocess.check_output(cmd, shell=True).decode()
            
            if output:
                lines = output.strip().split('\n')
                for line in lines:
                    if f':{port}' in line and 'LISTENING' in line:
                        parts = line.strip().split()
                        pid = parts[-1]
                        logger.info(f"正在终止进程 PID: {pid} 以释放端口 {port}")
                        subprocess.run(f'taskkill /F /PID {pid}', shell=True)
                        return True
        else:
            cmd = f"lsof -i :{port} -t"
            output = subprocess.check_output(cmd, shell=True).decode()
            
            if output:
                pids = output.strip().split('\n')
                for pid in pids:
                    logger.info(f"正在终止进程 PID: {pid} 以释放端口 {port}")
                    subprocess.run(f'kill -9 {pid}', shell=True)
                return True
    except Exception as e:
        logger.error(f"终止进程时出错: {e}")
    return False

def main():
    """
    主函数 - 设置并启动MCP服务
    
    MCP服务是模型操作控制平台(Model Control Platform)的简称，它是连接AI后端与3D模型的桥梁。
    服务启动后会打开一个托管的浏览器实例，该实例是执行模型操作的实际环境。
    
    当用户通过AI对话接口要求"旋转模型"、"放大模型"等操作时，请求流程如下：
    1. 用户请求 -> AI后端 -> LLM解析意图 -> AI后端调用MCP服务API
    2. MCP服务接收请求 -> 在托管的浏览器实例中执行相应的JavaScript代码
    3. 浏览器实例中的3D模型执行相应操作 -> 返回操作结果
    
    注意：MCP服务打开的浏览器实例与用户访问前端的浏览器是不同的！
    用户可以关闭自己的浏览器，但MCP服务的浏览器实例必须保持运行。
    """
    args = parse_arguments()
    original_port = args.port
    
    # 检查端口是否被占用
    if is_port_in_use(args.port):
        logger.warning(f"端口 {args.port} 已被占用")
        if args.force_port:
            if kill_process_on_port(args.port):
                logger.info(f"已释放端口 {args.port}")
                time.sleep(1)  # 等待端口释放
            else:
                logger.error(f"无法释放端口 {args.port}，请手动关闭占用端口的程序或使用其他端口")
                return 1
        else:
            available_port = find_available_port(args.port + 1)
            if available_port:
                logger.info(f"选择新端口: {available_port}")
                args.port = available_port
            else:
                logger.error(f"无法找到可用端口，请手动关闭占用端口的程序或指定其他端口")
                return 1
    
    # 设置环境变量
    os.environ["HEADLESS"] = "true" if args.headless else "false"
    os.environ["BROWSER_TYPE"] = args.browser
    os.environ["PORT"] = str(args.port)
    os.environ["FRONTEND_URL"] = args.frontend_url
    os.environ["LOG_LEVEL"] = args.log_level
    
    if args.dify_api_endpoint:
        os.environ["DIFY_API_ENDPOINT"] = args.dify_api_endpoint
    
    if args.dify_api_key:
        os.environ["DIFY_API_KEY"] = args.dify_api_key
    
    # 检查Playwright是否安装
    if not is_playwright_installed():
        logger.warning("Playwright未安装")
        if not install_playwright(args.browser):
            logger.error("无法安装Playwright，请手动安装")
            return 1
    
    # 打印启动信息
    print("="*80)
    print("数字孪生浏览器操作服务 (MCP - Model Control Platform)".center(80))
    print("="*80)
    print(f"启动时间: {datetime.now().isoformat()}")
    print(f"浏览器类型: {args.browser}")
    print(f"无头模式: {'是' if args.headless else '否'}")
    print(f"服务端口: {args.port}" + (" (自动选择)" if args.port != original_port else ""))
    print(f"前端URL: {args.frontend_url}")
    print(f"日志级别: {args.log_level}")
    print("="*80)
    print("重要提示：".center(80))
    print("- 服务将打开一个浏览器实例用于执行模型操作")
    print("- 此浏览器实例是AI控制模型的必要环境，请勿关闭")
    print("- 用户通过AI聊天下达的模型操作指令将在此浏览器执行")
    print("="*80)
    print("正在启动服务...")
    
    # 启动服务
    try:
        cmd = [
            sys.executable, 
            "mcp_server.py"
        ]
        
        process = subprocess.Popen(cmd)
        
        # 等待服务启动
        if wait_for_service(args.port):
            print("="*80)
            print(f"服务已成功启动")
            print(f"API文档: http://localhost:{args.port}/docs")
            print(f"健康检查: http://localhost:{args.port}/health")
            print(f"性能指标: http://localhost:{args.port}/metrics")
            print("="*80)
            print("按Ctrl+C终止服务")
            
            # 等待进程结束
            process.wait()
            return process.returncode
        else:
            process.terminate()
            return 1
    except KeyboardInterrupt:
        print("\n用户中断，正在停止服务...")
        process.terminate()
        return 0
    except Exception as e:
        logger.error(f"启动服务时出错: {e}")
        return 1

if __name__ == "__main__":
    sys.exit(main()) 