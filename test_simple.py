#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
数字孪生浏览器操作服务测试脚本
用于测试健康状态和各项操作功能
"""

import requests
import sys
import time
import traceback

# 请求超时设置（秒）
REQUEST_TIMEOUT = 10
# 服务基础URL
BASE_URL = "http://localhost:9000"
# 详细日志
VERBOSE = True

def test_health():
    """测试健康状态端点"""
    print("\n===== 测试健康状态 =====")
    try:
        # 发送GET请求到健康状态端点
        response = requests.get(f"{BASE_URL}/health", timeout=REQUEST_TIMEOUT)
        
        # 记录HTTP状态码
        print(f"HTTP状态码: {response.status_code}")
        
        # 解析JSON响应
        if response.status_code == 200:
            data = response.json()
            print(f"健康状态: {data.get('status', '未知')}")
            print(f"消息: {data.get('message', '无消息')}")
            print(f"版本: {data.get('version', '未知')}")
            
            # 如果有其他详细信息，展示它们
            if 'api_key_status' in data:
                print(f"API密钥状态: {data.get('api_key_status')}")
            if 'browser_status' in data:
                print(f"浏览器状态: {data.get('browser_status')}")
            if 'page_status' in data:
                print(f"页面状态: {data.get('page_status')}")
            if 'timestamp' in data:
                timestamp = data.get('timestamp')
                print(f"时间戳: {timestamp}")
                
            # 如果有当前URL，显示它
            if 'current_url' in data:
                print(f"当前URL: {data.get('current_url')}")
            
            return data.get('status') == 'ok'
        else:
            print(f"请求失败: {response.text}")
            return False
    except Exception as e:
        print(f"测试健康状态时出错: {e}")
        if VERBOSE:
            traceback.print_exc()
        return False

def test_rotate():
    """测试旋转操作"""
    print("\n===== 测试旋转操作 =====")
    try:
        # 创建请求负载
        payload = {
            "operation": "rotate",
            "parameters": {
                "direction": "left",
                "angle": 45
            }
        }
        
        # 记录请求内容
        print(f"请求内容: {payload}")
        
        # 发送POST请求
        response = requests.post(
            f"{BASE_URL}/api/execute", 
            json=payload,
            timeout=REQUEST_TIMEOUT
        )
        
        # 记录HTTP状态码
        print(f"HTTP状态码: {response.status_code}")
        
        # 解析JSON响应
        if response.status_code == 200:
            data = response.json()
            print(f"成功: {data.get('success', False)}")
            
            # 显示详细信息
            if 'original_return' in data:
                print(f"原始返回值: {data.get('original_return')}")
            if 'executed' in data:
                print(f"已执行: {data.get('executed', False)}")
            
            # 如果有错误信息，显示它
            if 'error' in data:
                print(f"错误: {data.get('error')}")
            
            return data.get('success', False)
        else:
            print(f"请求失败: {response.text}")
            return False
    except Exception as e:
        print(f"测试旋转操作时出错: {e}")
        if VERBOSE:
            traceback.print_exc()
        return False

def test_zoom():
    """测试缩放操作"""
    print("\n===== 测试缩放操作 =====")
    try:
        # 创建请求负载
        payload = {
            "operation": "zoom",
            "parameters": {
                "scale": 1.5
            }
        }
        
        # 记录请求内容
        print(f"请求内容: {payload}")
        
        # 发送POST请求
        response = requests.post(
            f"{BASE_URL}/api/execute", 
            json=payload,
            timeout=REQUEST_TIMEOUT
        )
        
        # 记录HTTP状态码
        print(f"HTTP状态码: {response.status_code}")
        
        # 解析JSON响应
        if response.status_code == 200:
            data = response.json()
            print(f"成功: {data.get('success', False)}")
            
            # 显示详细信息
            if 'original_return' in data:
                print(f"原始返回值: {data.get('original_return')}")
            if 'executed' in data:
                print(f"已执行: {data.get('executed', False)}")
            
            # 如果有错误信息，显示它
            if 'error' in data:
                print(f"错误: {data.get('error')}")
            
            return data.get('success', False)
        else:
            print(f"请求失败: {response.text}")
            return False
    except Exception as e:
        print(f"测试缩放操作时出错: {e}")
        if VERBOSE:
            traceback.print_exc()
        return False

def test_reset():
    """测试重置操作"""
    print("\n===== 测试重置操作 =====")
    try:
        # 创建请求负载
        payload = {
            "operation": "reset"
        }
        
        # 记录请求内容
        print(f"请求内容: {payload}")
        
        # 发送POST请求
        response = requests.post(
            f"{BASE_URL}/api/execute", 
            json=payload,
            timeout=REQUEST_TIMEOUT
        )
        
        # 记录HTTP状态码
        print(f"HTTP状态码: {response.status_code}")
        
        # 解析JSON响应
        if response.status_code == 200:
            data = response.json()
            print(f"成功: {data.get('success', False)}")
            
            # 显示详细信息
            if 'original_return' in data:
                print(f"原始返回值: {data.get('original_return')}")
            if 'method' in data:
                print(f"使用的方法: {data.get('method')}")
            if 'executed' in data:
                print(f"已执行: {data.get('executed', False)}")
            
            # 如果有错误信息，显示它
            if 'error' in data:
                print(f"错误: {data.get('error')}")
            
            return data.get('success', False)
        else:
            print(f"请求失败: {response.text}")
            return False
    except Exception as e:
        print(f"测试重置操作时出错: {e}")
        if VERBOSE:
            traceback.print_exc()
        return False

def test_all():
    """执行所有测试"""
    print("\n=========== 开始执行所有测试 ===========")
    
    start_time = time.time()
    results = {
        "健康状态": test_health(),
        "旋转操作": test_rotate(),
        "缩放操作": test_zoom(),
        "重置操作": test_reset()
    }
    end_time = time.time()
    
    # 输出总结果
    print("\n=========== 测试结果摘要 ===========")
    success_count = sum(1 for result in results.values() if result)
    total_count = len(results)
    success_rate = (success_count / total_count) * 100
    
    print(f"总测试数: {total_count}")
    print(f"成功数: {success_count}")
    print(f"失败数: {total_count - success_count}")
    print(f"成功率: {success_rate:.2f}%")
    print(f"总耗时: {end_time - start_time:.2f}秒")
    
    # 输出详细结果
    print("\n详细结果:")
    for test_name, result in results.items():
        status = "✅ 成功" if result else "❌ 失败"
        print(f"{test_name}: {status}")
    
    # 返回是否全部测试都成功
    return all(results.values())

if __name__ == "__main__":
    try:
        # 检查是否有特定的测试要运行
        if len(sys.argv) > 1:
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
                print(f"未知的测试: {test_name}")
                print("可用的测试: health, rotate, zoom, reset")
        else:
            # 如果没有指定测试，则运行所有测试
            test_all()
    except KeyboardInterrupt:
        print("\n测试被用户中断")
    except Exception as e:
        print(f"执行测试时出现未处理的异常: {e}")
        if VERBOSE:
            traceback.print_exc() 