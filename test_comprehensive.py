#!/usr/bin/env python
"""
数字孪生浏览器服务综合测试脚本
用法: python test_comprehensive.py [health|websocket|api|all]
"""

import asyncio
import json
import logging
import sys
import time
import traceback
import websockets
import requests
from datetime import datetime

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# 配置
BASE_URL = "http://localhost:9000"
WS_URL = "ws://localhost:9000/ws"
REQUEST_TIMEOUT = 10  # 秒

# 测试结果统计
test_results = {
    "total": 0,
    "passed": 0,
    "failed": 0,
    "skipped": 0,
    "details": []
}

def log_test_result(test_name, success, message, elapsed_time=None):
    """记录测试结果"""
    result = "通过" if success else "失败"
    time_info = f" (耗时: {elapsed_time:.2f}秒)" if elapsed_time is not None else ""
    logger.info(f"测试 {test_name}: {result}{time_info} - {message}")
    
    test_results["total"] += 1
    if success:
        test_results["passed"] += 1
    else:
        test_results["failed"] += 1
    
    test_results["details"].append({
        "name": test_name,
        "result": result,
        "message": message,
        "elapsed_time": elapsed_time
    })

async def test_health_check():
    """测试健康检查端点"""
    start_time = time.time()
    try:
        response = requests.get(f"{BASE_URL}/health", timeout=REQUEST_TIMEOUT)
        response.raise_for_status()
        data = response.json()
        
        # 验证响应格式
        required_fields = ["status", "message", "version", "timestamp"]
        missing_fields = [field for field in required_fields if field not in data]
        
        if missing_fields:
            log_test_result("健康检查", False, f"响应缺少必需字段: {', '.join(missing_fields)}", time.time() - start_time)
            return
        
        if data["status"] not in ["healthy", "degraded", "unhealthy"]:
            log_test_result("健康检查", False, f"无效的状态值: {data['status']}", time.time() - start_time)
            return
        
        log_test_result("健康检查", True, f"状态: {data['status']}, 消息: {data['message']}", time.time() - start_time)
        return data
    except Exception as e:
        log_test_result("健康检查", False, f"异常: {str(e)}", time.time() - start_time)
        return None

async def test_metrics():
    """测试性能指标端点"""
    start_time = time.time()
    try:
        response = requests.get(f"{BASE_URL}/metrics", timeout=REQUEST_TIMEOUT)
        response.raise_for_status()
        data = response.json()
        
        # 验证响应格式
        required_fields = ["uptime", "cpu", "memory", "operations"]
        missing_fields = [field for field in required_fields if field not in data]
        
        if missing_fields:
            log_test_result("性能指标", False, f"响应缺少必需字段: {', '.join(missing_fields)}", time.time() - start_time)
            return
        
        log_test_result("性能指标", True, f"CPU: {data['cpu']['current']:.2f}%, 内存: {data['memory']['current']:.2f}%", time.time() - start_time)
        return data
    except Exception as e:
        log_test_result("性能指标", False, f"异常: {str(e)}", time.time() - start_time)
        return None

async def test_api_operations():
    """测试API操作端点"""
    operations = [
        {
            "name": "旋转操作",
            "payload": {
                "operation": "rotate",
                "parameters": {
                    "angle": 45,
                    "axis": "y"
                }
            }
        },
        {
            "name": "缩放操作",
            "payload": {
                "operation": "zoom",
                "parameters": {
                    "scale": 1.5
                }
            }
        },
        {
            "name": "聚焦操作",
            "payload": {
                "operation": "focus",
                "parameters": {
                    "target": "center"
                }
            }
        },
        {
            "name": "重置操作",
            "payload": {
                "operation": "reset"
            }
        },
        {
            "name": "材质更改",
            "payload": {
                "operation": "changeMaterial",
                "parameters": {
                    "material": "standard",
                    "color": "#ff0000"
                }
            }
        },
        {
            "name": "动画控制",
            "payload": {
                "operation": "toggleAnimation",
                "parameters": {
                    "name": "default",
                    "enabled": True
                }
            }
        }
    ]
    
    results = []
    
    for op in operations:
        start_time = time.time()
        try:
            response = requests.post(
                f"{BASE_URL}/api/execute",
                json=op["payload"],
                timeout=REQUEST_TIMEOUT
            )
            response.raise_for_status()
            data = response.json()
            
            if data.get("success"):
                log_test_result(op["name"], True, "操作成功执行", time.time() - start_time)
            else:
                log_test_result(op["name"], False, f"操作执行失败: {data.get('error', '未知错误')}", time.time() - start_time)
            
            results.append(data)
        except Exception as e:
            log_test_result(op["name"], False, f"异常: {str(e)}", time.time() - start_time)
            results.append(None)
    
    return results

async def test_reinitialize():
    """测试浏览器重新初始化"""
    start_time = time.time()
    try:
        response = requests.post(f"{BASE_URL}/api/reinitialize", timeout=30)  # 较长的超时
        response.raise_for_status()
        data = response.json()
        
        if data.get("status") == "success":
            log_test_result("浏览器重新初始化", True, data.get("message", "重新初始化成功"), time.time() - start_time)
        else:
            log_test_result("浏览器重新初始化", False, f"重新初始化失败: {data.get('message', '未知错误')}", time.time() - start_time)
        
        # 等待一段时间以确保重新初始化完成
        await asyncio.sleep(5)
        return data
    except Exception as e:
        log_test_result("浏览器重新初始化", False, f"异常: {str(e)}", time.time() - start_time)
        return None

async def test_websocket():
    """测试WebSocket连接和操作"""
    start_time = time.time()
    try:
        # 连接WebSocket
        async with websockets.connect(WS_URL, timeout=REQUEST_TIMEOUT) as ws:
            # 测试脚本执行
            script_test = {
                "type": "execute_script",
                "script": "return window.rotateModel ? window.rotateModel(45, 'y') : true;",
                "timestamp": datetime.now().isoformat()
            }
            
            await ws.send(json.dumps(script_test))
            response = await ws.recv()
            data = json.loads(response)
            
            script_success = data.get("type") == "script_result" and data.get("success")
            log_test_result("WebSocket脚本执行", script_success, 
                           "脚本成功执行" if script_success else f"脚本执行失败: {data.get('error', '未知错误')}", 
                           time.time() - start_time)
            
            # 测试健康检查
            health_test = {
                "type": "health_check",
                "timestamp": datetime.now().isoformat()
            }
            
            health_start = time.time()
            await ws.send(json.dumps(health_test))
            response = await ws.recv()
            data = json.loads(response)
            
            health_success = data.get("type") == "health_check" and data.get("status") == "healthy"
            log_test_result("WebSocket健康检查", health_success, 
                           "页面响应正常" if health_success else f"页面响应异常: {data.get('message', '未知错误')}", 
                           time.time() - health_start)
            
            return {"script": script_success, "health": health_success}
    except Exception as e:
        log_test_result("WebSocket连接", False, f"异常: {str(e)}", time.time() - start_time)
        return None

async def run_all_tests():
    """运行所有测试"""
    print("="*50)
    print("数字孪生浏览器服务综合测试")
    print("="*50)
    print(f"目标服务器: {BASE_URL}")
    print(f"开始时间: {datetime.now().isoformat()}")
    print("="*50)
    
    # 健康检查和指标测试
    await test_health_check()
    await test_metrics()
    
    # API操作测试
    await test_api_operations()
    
    # 重新初始化测试
    await test_reinitialize()
    
    # 等待重新初始化完成
    await asyncio.sleep(5)
    
    # WebSocket测试
    await test_websocket()
    
    # 打印测试结果汇总
    print("\n"+"="*50)
    print("测试结果汇总")
    print("="*50)
    print(f"总测试数: {test_results['total']}")
    print(f"通过: {test_results['passed']} ({test_results['passed']/test_results['total']*100:.2f}%)")
    print(f"失败: {test_results['failed']} ({test_results['failed']/test_results['total']*100:.2f}%)")
    print(f"跳过: {test_results['skipped']} ({test_results['skipped']/test_results['total']*100:.2f}%)")
    print("="*50)
    
    if test_results["failed"] > 0:
        print("\n失败的测试:")
        for detail in test_results["details"]:
            if detail["result"] == "失败":
                print(f"  - {detail['name']}: {detail['message']}")
    
    return test_results

async def main():
    """主函数"""
    if len(sys.argv) < 2:
        test_type = "all"
    else:
        test_type = sys.argv[1].lower()
    
    try:
        if test_type == "health":
            await test_health_check()
            await test_metrics()
        elif test_type == "api":
            await test_api_operations()
        elif test_type == "websocket":
            await test_websocket()
        elif test_type == "all":
            await run_all_tests()
        else:
            print(f"未知的测试类型: {test_type}")
            print("有效选项: health, api, websocket, all")
            return 1
    except KeyboardInterrupt:
        print("\n测试被用户中断")
        return 1
    except Exception as e:
        print(f"\n测试执行过程中出错: {str(e)}")
        traceback.print_exc()
        return 1
    
    return 0 if test_results["failed"] == 0 else 1

if __name__ == "__main__":
    try:
        exit_code = asyncio.run(main())
        sys.exit(exit_code)
    except KeyboardInterrupt:
        print("\n程序被用户中断")
        sys.exit(1) 