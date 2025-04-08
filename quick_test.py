#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
MCP服务快速测试脚本 (Quick Test for MCP Service)

此脚本用于快速测试数字孪生浏览器操作服务(MCP)的状态和基本功能。
它会检查服务的健康状态，并尝试执行基本的模型操作（如旋转、缩放等）。

用法:
1. 先确保MCP服务已启动 (python start_service.py)
2. 运行此测试脚本: python quick_test.py
"""

import json
import sys
import time
import traceback
import requests

# 配置
MCP_URL = "http://localhost:9000"
REQUEST_TIMEOUT = 10  # 请求超时时间（秒）
TEST_DELAY = 1  # 测试间隔时间（秒）

def print_separator(title=None):
    """打印分隔线"""
    print("\n" + "="*80)
    if title:
        print(f"{title.center(80)}")
        print("="*80)

def test_health():
    """测试服务健康状态"""
    print_separator("测试健康状态")
    
    try:
        response = requests.get(f"{MCP_URL}/health", timeout=REQUEST_TIMEOUT)
        print(f"状态码: {response.status_code}")
        
        if response.status_code == 200:
            data = response.json()
            print(f"服务状态: {data.get('status', 'unknown')}")
            print(f"消息: {data.get('message', '')}")
            print(f"版本: {data.get('version', '')}")
            print(f"浏览器状态: {data.get('browser_status', '')}")
            print(f"页面状态: {data.get('page_status', '')}")
            print(f"当前URL: {data.get('current_url', '')}")
            print(f"时间戳: {data.get('timestamp', '')}")
            
            if data.get('status') == 'healthy':
                print("\n✓ 健康检查通过 - 服务状态良好")
                return True
            else:
                print(f"\n! 警告: 服务报告状态非健康: {data.get('status')}")
                return False
        else:
            print(f"! 错误: 健康检查请求失败，状态码 {response.status_code}")
            return False
            
    except Exception as e:
        print(f"! 错误: 无法连接到MCP服务: {str(e)}")
        print("请确保MCP服务已启动并运行在 " + MCP_URL)
        return False

def test_rotate():
    """测试旋转操作"""
    print_separator("测试旋转操作")
    
    payload = {
        "operation": "rotate",
        "parameters": {
            "angle": 45,
            "axis": "y"
        }
    }
    
    try:
        print(f"请求数据: {json.dumps(payload, indent=2)}")
        response = requests.post(
            f"{MCP_URL}/api/execute", 
            json=payload,
            timeout=REQUEST_TIMEOUT
        )
        
        print(f"状态码: {response.status_code}")
        
        if response.status_code == 200:
            data = response.json()
            print(f"响应数据: {json.dumps(data, indent=2)}")
            
            if data.get('success') == True:
                print("\n✓ 旋转操作成功执行")
                return True
            else:
                print(f"\n! 警告: 旋转操作执行失败: {data.get('message', '')}")
                return False
        else:
            print(f"! 错误: 请求失败，状态码 {response.status_code}")
            if response.text:
                print(f"响应内容: {response.text}")
            return False
            
    except Exception as e:
        print(f"! 错误: 请求异常: {str(e)}")
        return False

def test_zoom():
    """测试缩放操作"""
    print_separator("测试缩放操作")
    
    payload = {
        "operation": "zoom",
        "parameters": {
            "scale": 1.5
        }
    }
    
    try:
        print(f"请求数据: {json.dumps(payload, indent=2)}")
        response = requests.post(
            f"{MCP_URL}/api/execute", 
            json=payload,
            timeout=REQUEST_TIMEOUT
        )
        
        print(f"状态码: {response.status_code}")
        
        if response.status_code == 200:
            data = response.json()
            print(f"响应数据: {json.dumps(data, indent=2)}")
            
            if data.get('success') == True:
                print("\n✓ 缩放操作成功执行")
                return True
            else:
                print(f"\n! 警告: 缩放操作执行失败: {data.get('message', '')}")
                return False
        else:
            print(f"! 错误: 请求失败，状态码 {response.status_code}")
            if response.text:
                print(f"响应内容: {response.text}")
            return False
            
    except Exception as e:
        print(f"! 错误: 请求异常: {str(e)}")
        return False

def test_reset():
    """测试重置操作"""
    print_separator("测试重置操作")
    
    payload = {
        "operation": "reset"
    }
    
    try:
        print(f"请求数据: {json.dumps(payload, indent=2)}")
        response = requests.post(
            f"{MCP_URL}/api/execute", 
            json=payload,
            timeout=REQUEST_TIMEOUT
        )
        
        print(f"状态码: {response.status_code}")
        
        if response.status_code == 200:
            data = response.json()
            print(f"响应数据: {json.dumps(data, indent=2)}")
            
            if data.get('success') == True:
                print("\n✓ 重置操作成功执行")
                return True
            else:
                print(f"\n! 警告: 重置操作执行失败: {data.get('message', '')}")
                return False
        else:
            print(f"! 错误: 请求失败，状态码 {response.status_code}")
            if response.text:
                print(f"响应内容: {response.text}")
            return False
            
    except Exception as e:
        print(f"! 错误: 请求异常: {str(e)}")
        return False

def test_reinitialize():
    """测试浏览器重初始化"""
    print_separator("测试浏览器重初始化")
    
    try:
        print("正在请求浏览器重初始化...")
        response = requests.post(f"{MCP_URL}/api/reinitialize", timeout=REQUEST_TIMEOUT)
        
        print(f"状态码: {response.status_code}")
        
        if response.status_code == 200:
            data = response.json()
            print(f"响应数据: {json.dumps(data, indent=2)}")
            
            if data.get('success') == True:
                print("\n✓ 浏览器重初始化成功")
                return True
            else:
                print(f"\n! 警告: 浏览器重初始化失败: {data.get('message', '')}")
                return False
        else:
            print(f"! 错误: 请求失败，状态码 {response.status_code}")
            if response.text:
                print(f"响应内容: {response.text}")
            return False
            
    except Exception as e:
        print(f"! 错误: 请求异常: {str(e)}")
        return False

def run_all_tests():
    """运行所有测试"""
    print_separator("MCP服务功能测试")
    print(f"目标服务: {MCP_URL}")
    print(f"测试时间: {time.strftime('%Y-%m-%d %H:%M:%S')}")
    
    results = {}
    total_tests = 0
    successful_tests = 0
    
    # 健康检查
    results["健康状态"] = test_health()
    if not results["健康状态"]:
        print("\n! 健康检查失败，中止测试")
        return results
    
    time.sleep(TEST_DELAY)
    
    # 测试操作
    results["旋转操作"] = test_rotate()
    time.sleep(TEST_DELAY)
    
    results["缩放操作"] = test_zoom()
    time.sleep(TEST_DELAY)
    
    results["重置操作"] = test_reset()
    time.sleep(TEST_DELAY)
    
    # 测试重初始化
    results["浏览器重初始化"] = test_reinitialize()
    
    # 统计结果
    for test_name, success in results.items():
        total_tests += 1
        if success:
            successful_tests += 1
    
    success_rate = (successful_tests / total_tests) * 100 if total_tests > 0 else 0
    
    # 打印汇总
    print_separator("测试结果汇总")
    for test_name, success in results.items():
        status = "✓ 通过" if success else "× 失败"
        print(f"{test_name}: {status}")
    
    print("\n总体结果:")
    print(f"成功率: {success_rate:.1f}% ({successful_tests}/{total_tests})")
    
    if success_rate == 100:
        print("\n✓ 全部测试通过!")
    else:
        print(f"\n! 存在 {total_tests - successful_tests} 个失败的测试")
    
    return results

if __name__ == "__main__":
    try:
        run_all_tests()
    except KeyboardInterrupt:
        print("\n用户中断，测试终止")
    except Exception as e:
        print(f"\n! 测试过程中出现意外错误:")
        print(traceback.format_exc())
    
    sys.exit(0) 