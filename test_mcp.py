#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
MCP协议测试脚本
(MCP Protocol Test Script)

测试MCP协议功能和WebSocket连接。
"""

import json
import asyncio
import websockets
import requests
import uuid
import time
import logging
from datetime import datetime
from typing import Dict, Any, Optional

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("mcp_test")

# MCP服务器配置
SERVER_URL = "http://localhost:9000"
WS_URL = "ws://localhost:9000/ws/mcp"

# HTTP请求超时（秒）
TIMEOUT = 10

# 测试MCP WebSocket连接
async def test_websocket_connection():
    """测试MCP WebSocket连接"""
    logger.info("测试MCP WebSocket连接...")
    
    try:
        # 连接到WebSocket
        async with websockets.connect(WS_URL) as websocket:
            # 等待欢迎消息
            welcome_msg = await websocket.recv()
            welcome_data = json.loads(welcome_msg)
            
            logger.info(f"收到欢迎消息: {welcome_data.get('message', '')}")
            logger.info(f"客户端ID: {welcome_data.get('clientId', '')}")
            
            # 发送初始化消息
            init_msg = {
                "type": "init",
                "clientType": "test_client",
                "timestamp": datetime.now().isoformat(),
                "id": f"msg_{uuid.uuid4().hex[:8]}"
            }
            
            await websocket.send(json.dumps(init_msg))
            
            # 等待响应
            response = await websocket.recv()
            response_data = json.loads(response)
            
            logger.info(f"收到初始化响应: {json.dumps(response_data, ensure_ascii=False)}")
            
            # 发送Ping消息
            ping_msg = {
                "type": "ping",
                "timestamp": datetime.now().isoformat(),
                "id": f"msg_{uuid.uuid4().hex[:8]}"
            }
            
            await websocket.send(json.dumps(ping_msg))
            
            # 等待Pong响应
            pong = await websocket.recv()
            pong_data = json.loads(pong)
            
            logger.info(f"收到Pong响应: {json.dumps(pong_data, ensure_ascii=False)}")
            
            # 发送旋转命令
            rotate_command = {
                "type": "command",
                "command": {
                    "id": f"cmd_{uuid.uuid4().hex[:8]}",
                    "action": "rotate",
                    "parameters": {
                        "direction": "left",
                        "angle": 30
                    }
                },
                "timestamp": datetime.now().isoformat(),
                "id": f"msg_{uuid.uuid4().hex[:8]}"
            }
            
            logger.info(f"发送旋转命令: {json.dumps(rotate_command, ensure_ascii=False)}")
            await websocket.send(json.dumps(rotate_command))
            
            # 等待一段时间确保命令执行
            await asyncio.sleep(1)
            
            # 发送缩放命令
            zoom_command = {
                "type": "command",
                "command": {
                    "id": f"cmd_{uuid.uuid4().hex[:8]}",
                    "action": "zoom",
                    "parameters": {
                        "scale": 1.5
                    }
                },
                "timestamp": datetime.now().isoformat(),
                "id": f"msg_{uuid.uuid4().hex[:8]}"
            }
            
            logger.info(f"发送缩放命令: {json.dumps(zoom_command, ensure_ascii=False)}")
            await websocket.send(json.dumps(zoom_command))
            
            # 等待一段时间确保命令执行
            await asyncio.sleep(1)
            
            # 发送重置命令
            reset_command = {
                "type": "command",
                "command": {
                    "id": f"cmd_{uuid.uuid4().hex[:8]}",
                    "action": "reset",
                    "parameters": {}
                },
                "timestamp": datetime.now().isoformat(),
                "id": f"msg_{uuid.uuid4().hex[:8]}"
            }
            
            logger.info(f"发送重置命令: {json.dumps(reset_command, ensure_ascii=False)}")
            await websocket.send(json.dumps(reset_command))
            
            # 等待一段时间确保命令执行
            await asyncio.sleep(1)
            
            logger.info("WebSocket测试完成")
            
            return True
    except Exception as e:
        logger.error(f"WebSocket测试失败: {e}")
        import traceback
        logger.debug(traceback.format_exc())
        return False

# 测试健康检查
def test_health_check():
    """测试健康检查API"""
    logger.info("测试健康检查API...")
    
    try:
        response = requests.get(f"{SERVER_URL}/health", timeout=TIMEOUT)
        response.raise_for_status()
        
        data = response.json()
        logger.info(f"健康状态: {data.get('status', '')}")
        logger.info(f"健康信息: {data.get('message', '')}")
        logger.info(f"版本: {data.get('version', '')}")
        
        if "browser" in data:
            logger.info(f"浏览器状态: {data['browser'].get('status', '')}")
        
        if "page" in data:
            logger.info(f"页面状态: {data['page'].get('status', '')}")
            
        if data.get("status") == "healthy":
            logger.info("健康检查通过")
            return True
        else:
            logger.warning("健康检查失败")
            return False
    except Exception as e:
        logger.error(f"健康检查请求失败: {e}")
        return False

# 测试REST API命令
def test_rest_command():
    """测试REST API命令"""
    logger.info("测试REST API命令...")
    
    try:
        # 发送旋转命令
        rotate_command = {
            "action": "rotate",
            "parameters": {
                "direction": "right",
                "angle": 45
            }
        }
        
        logger.info(f"发送REST旋转命令: {json.dumps(rotate_command, ensure_ascii=False)}")
        
        response = requests.post(
            f"{SERVER_URL}/api/mcp/command",
            json=rotate_command,
            timeout=TIMEOUT
        )
        
        response.raise_for_status()
        result = response.json()
        
        logger.info(f"旋转命令响应: {json.dumps(result, ensure_ascii=False)}")
        
        # 等待一段时间确保命令执行
        time.sleep(1)
        
        # 发送自然语言命令
        nl_command = {
            "message": "放大模型1.2倍"
        }
        
        logger.info(f"发送自然语言命令: {json.dumps(nl_command, ensure_ascii=False)}")
        
        response = requests.post(
            f"{SERVER_URL}/api/mcp/nl-command",
            json=nl_command,
            timeout=TIMEOUT
        )
        
        response.raise_for_status()
        result = response.json()
        
        logger.info(f"自然语言命令响应: {json.dumps(result, ensure_ascii=False)}")
        
        # 等待一段时间确保命令执行
        time.sleep(1)
        
        logger.info("REST API测试完成")
        return True
    except Exception as e:
        logger.error(f"REST API测试失败: {e}")
        import traceback
        logger.debug(traceback.format_exc())
        return False

# 主测试函数
async def run_tests():
    """运行所有测试"""
    logger.info("=== 开始MCP协议测试 ===")
    
    results = {}
    
    # 测试健康检查
    results["health_check"] = test_health_check()
    
    # 如果健康检查通过，继续其他测试
    if results["health_check"]:
        # 测试REST API命令
        results["rest_command"] = test_rest_command()
        
        # 测试WebSocket连接
        results["websocket"] = await test_websocket_connection()
    
    # 计算成功率
    success_count = sum(1 for result in results.values() if result)
    total_count = len(results)
    success_rate = (success_count / total_count) * 100 if total_count > 0 else 0
    
    # 输出结果摘要
    logger.info("=== 测试结果摘要 ===")
    for test_name, result in results.items():
        logger.info(f"{test_name}: {'成功' if result else '失败'}")
    
    logger.info(f"总计: {success_count}/{total_count} 测试通过 ({success_rate:.1f}%)")
    logger.info("=== 测试完成 ===")
    
    return results

# 主函数
if __name__ == "__main__":
    try:
        # 运行测试
        asyncio.run(run_tests())
    except KeyboardInterrupt:
        logger.info("测试被用户中断")
    except Exception as e:
        logger.error(f"测试过程中发生错误: {e}")
        import traceback
        logger.error(traceback.format_exc()) 