#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
数字孪生浏览器操作服务测试脚本
(Digital Twin Browser Operation Service Test Script)

简单测试脚本，用于测试服务的基本功能
"""

import requests
import sys
import time
import traceback
from typing import Dict, Any, List, Tuple

# 设置请求超时时间
TIMEOUT = 10  # 秒

def test_health() -> bool:
    """测试健康检查接口"""
    print("\n==== 测试健康检查接口 ====")
    try:
        response = requests.get("http://localhost:9000/health", timeout=TIMEOUT)
        print(f"HTTP状态码: {response.status_code}")
        
        if response.status_code == 200:
            data = response.json()
            print(f"状态: {data.get('status')}")
            print(f"消息: {data.get('message')}")
            print(f"版本: {data.get('version')}")
            print(f"浏览器状态: {data.get('browser_status')}")
            print(f"页面状态: {data.get('page_status')}")
            print(f"时间戳: {data.get('timestamp')}")
            return True
        else:
            print(f"请求失败: {response.text}")
            return False
    except Exception as e:
        print(f"请求异常: {str(e)}")
        traceback.print_exc()
        return False

def test_rotate() -> bool:
    """测试旋转操作"""
    print("\n==== 测试旋转操作 ====")
    payload = {
        "operation": "rotate",
        "parameters": {
            "direction": "left",
            "degrees": 45
        }
    }
    
    try:
        print(f"发送请求: {payload}")
        response = requests.post(
            "http://localhost:9000/api/execute", 
            json=payload,
            timeout=TIMEOUT
        )
        print(f"HTTP状态码: {response.status_code}")
        
        if response.status_code == 200:
            data = response.json()
            print(f"操作结果: {data}")
            print(f"成功状态: {data.get('success')}")
            print(f"执行详情: {data.get('data', {}).get('executed')}")
            print(f"原始返回值: {data.get('data', {}).get('original_return')}")
            return data.get('success', False)
        else:
            print(f"请求失败: {response.text}")
            return False
    except Exception as e:
        print(f"请求异常: {str(e)}")
        traceback.print_exc()
        return False

def test_zoom() -> bool:
    """测试缩放操作"""
    print("\n==== 测试缩放操作 ====")
    payload = {
        "operation": "zoom",
        "parameters": {
            "scale": 1.5
        }
    }
    
    try:
        print(f"发送请求: {payload}")
        response = requests.post(
            "http://localhost:9000/api/execute", 
            json=payload,
            timeout=TIMEOUT
        )
        print(f"HTTP状态码: {response.status_code}")
        
        if response.status_code == 200:
            data = response.json()
            print(f"操作结果: {data}")
            print(f"成功状态: {data.get('success')}")
            print(f"执行详情: {data.get('data', {}).get('executed')}")
            print(f"原始返回值: {data.get('data', {}).get('original_return')}")
            return data.get('success', False)
        else:
            print(f"请求失败: {response.text}")
            return False
    except Exception as e:
        print(f"请求异常: {str(e)}")
        traceback.print_exc()
        return False

def test_reset() -> bool:
    """测试重置操作"""
    print("\n==== 测试重置操作 ====")
    payload = {
        "operation": "reset",
        "parameters": {}
    }
    
    try:
        print(f"发送请求: {payload}")
        response = requests.post(
            "http://localhost:9000/api/execute", 
            json=payload,
            timeout=TIMEOUT
        )
        print(f"HTTP状态码: {response.status_code}")
        
        if response.status_code == 200:
            data = response.json()
            print(f"操作结果: {data}")
            print(f"成功状态: {data.get('success')}")
            print(f"执行详情: {data.get('data', {}).get('executed')}")
            print(f"原始返回值: {data.get('data', {}).get('original_return')}")
            return data.get('success', False)
        else:
            print(f"请求失败: {response.text}")
            return False
    except Exception as e:
        print(f"请求异常: {str(e)}")
        traceback.print_exc()
        return False

def test_all() -> Tuple[int, int]:
    """执行所有测试"""
    print("\n===== 开始全部测试 =====")
    start_time = time.time()
    
    tests = [
        ("健康检查", test_health),
        ("旋转操作", test_rotate),
        ("缩放操作", test_zoom),
        ("重置操作", test_reset)
    ]
    
    success_count = 0
    total_tests = len(tests)
    
    for name, test_func in tests:
        print(f"\n>> 执行测试: {name}")
        try:
            result = test_func()
            if result:
                success_count += 1
                print(f"✅ 测试通过: {name}")
            else:
                print(f"❌ 测试失败: {name}")
        except Exception as e:
            print(f"❌ 测试异常: {name} - {str(e)}")
            traceback.print_exc()
    
    elapsed = time.time() - start_time
    print(f"\n===== 测试完成 =====")
    print(f"总测试数: {total_tests}")
    print(f"通过测试: {success_count}")
    print(f"失败测试: {total_tests - success_count}")
    print(f"成功率: {(success_count / total_tests) * 100:.1f}%")
    print(f"总耗时: {elapsed:.2f}秒")
    
    return (success_count, total_tests)

if __name__ == "__main__":
    try:
        if len(sys.argv) > 1:
            # 执行指定的测试
            test_name = sys.argv[1].lower()
            if test_name == "health":
                test_health()
            elif test_name == "rotate":
                test_rotate()
            elif test_name == "zoom":
                test_zoom()
            elif test_name == "reset":
                test_reset()
            else:
                print(f"未知测试: {test_name}")
                print("可用测试: health, rotate, zoom, reset")
        else:
            # 执行所有测试
            test_all()
    except KeyboardInterrupt:
        print("\n测试被用户中断")
    except Exception as e:
        print(f"测试执行过程中出错: {str(e)}")
        traceback.print_exc() 