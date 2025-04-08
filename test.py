#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
数字孪生浏览器操作服务API测试脚本
(Digital Twin Browser Service API Test Script)

用于测试浏览器操作服务的各项功能
"""

import requests
import json
import time
import sys
import os
from pprint import pprint

# 服务地址配置
API_URL = "http://localhost:9000"  # 默认服务地址

def print_header(message):
    """打印带格式的标题"""
    print("\n" + "=" * 50)
    print(f"  {message}")
    print("=" * 50)

def check_health():
    """检查服务健康状态"""
    print_header("检查服务健康状态 (Health Check)")
    
    try:
        response = requests.get(f"{API_URL}/health")
        data = response.json()
        
        print(f"状态: {data.get('status')}")
        print(f"消息: {data.get('message')}")
        print(f"浏览器状态: {data.get('browser_status')}")
        print(f"页面状态: {data.get('page_status')}")
        print(f"当前页面URL: {data.get('page_url')}")
        
        return data.get('status') == "healthy"
    except Exception as e:
        print(f"错误: {e}")
        return False

def reinitialize_browser():
    """重新初始化浏览器"""
    print_header("重新初始化浏览器 (Reinitialize Browser)")
    
    try:
        response = requests.post(f"{API_URL}/reinitialize")
        data = response.json()
        
        print(f"成功: {data.get('success')}")
        print(f"消息: {data.get('message')}")
        
        return data.get('success', False)
    except Exception as e:
        print(f"错误: {e}")
        return False

def rotate_model(direction="left", angle=30, target=None):
    """旋转模型"""
    print_header(f"旋转模型 (Rotate Model): {direction}, {angle}度, 目标={target}")
    
    data = {
        "action": "rotate",
        "target": target,
        "parameters": {
            "direction": direction,
            "angle": angle
        }
    }
    
    try:
        response = requests.post(f"{API_URL}/api/execute", json=data)
        result = response.json()
        
        print(f"成功: {result.get('success')}")
        print(f"消息: {result.get('message')}")
        
        if 'debug_info' in result:
            print("\n调试信息:")
            print(f"API调用: {len(result['debug_info'].get('api_calls', []))}个")
            print(f"日志: {len(result['debug_info'].get('logs', []))}条")
            print(f"错误: {len(result['debug_info'].get('errors', []))}个")
            
            # 打印错误信息
            if result['debug_info'].get('errors'):
                print("\n错误详情:")
                for error in result['debug_info'].get('errors', []):
                    print(f"- {error.get('error')} (位置: {error.get('location')})")
        
        return result.get('success', False)
    except Exception as e:
        print(f"错误: {e}")
        return False

def zoom_model(scale=1.5, target=None):
    """缩放模型"""
    print_header(f"缩放模型 (Zoom Model): 比例={scale}, 目标={target}")
    
    data = {
        "action": "zoom",
        "target": target,
        "parameters": {
            "scale": scale
        }
    }
    
    try:
        response = requests.post(f"{API_URL}/api/execute", json=data)
        result = response.json()
        
        print(f"成功: {result.get('success')}")
        print(f"消息: {result.get('message')}")
        
        if 'debug_info' in result:
            print("\n调试信息:")
            print(f"API调用: {len(result['debug_info'].get('api_calls', []))}个")
            print(f"日志: {len(result['debug_info'].get('logs', []))}条")
            print(f"错误: {len(result['debug_info'].get('errors', []))}个")
            
            # 打印错误信息
            if result['debug_info'].get('errors'):
                print("\n错误详情:")
                for error in result['debug_info'].get('errors', []):
                    print(f"- {error.get('error')} (位置: {error.get('location')})")
        
        return result.get('success', False)
    except Exception as e:
        print(f"错误: {e}")
        return False

def focus_on_model(target):
    """聚焦到模型组件"""
    print_header(f"聚焦到组件 (Focus on Component): {target}")
    
    data = {
        "action": "focus",
        "target": target
    }
    
    try:
        response = requests.post(f"{API_URL}/api/execute", json=data)
        result = response.json()
        
        print(f"成功: {result.get('success')}")
        print(f"消息: {result.get('message')}")
        
        if 'debug_info' in result:
            print("\n调试信息:")
            print(f"API调用: {len(result['debug_info'].get('api_calls', []))}个")
            print(f"日志: {len(result['debug_info'].get('logs', []))}条")
            print(f"错误: {len(result['debug_info'].get('errors', []))}个")
            
            # 打印错误信息
            if result['debug_info'].get('errors'):
                print("\n错误详情:")
                for error in result['debug_info'].get('errors', []):
                    print(f"- {error.get('error')} (位置: {error.get('location')})")
        
        return result.get('success', False)
    except Exception as e:
        print(f"错误: {e}")
        return False

def reset_model():
    """重置模型"""
    print_header("重置模型 (Reset Model)")
    
    data = {
        "action": "reset"
    }
    
    try:
        response = requests.post(f"{API_URL}/api/execute", json=data)
        result = response.json()
        
        print(f"成功: {result.get('success')}")
        print(f"消息: {result.get('message')}")
        
        return result.get('success', False)
    except Exception as e:
        print(f"错误: {e}")
        return False

def run_all_tests():
    """运行所有测试"""
    print_header("开始全面测试 (Starting Full Test Suite)")
    
    # 检查健康状态
    if not check_health():
        print("服务状态不健康，尝试重新初始化...")
        if not reinitialize_browser():
            print("重新初始化失败，测试终止")
            return False
    
    # 执行各种操作
    tests = [
        lambda: rotate_model(direction="left", angle=45),
        lambda: time.sleep(1),
        lambda: rotate_model(direction="right", angle=90),
        lambda: time.sleep(1),
        lambda: zoom_model(scale=1.5),
        lambda: time.sleep(1),
        lambda: zoom_model(scale=0.5),
        lambda: time.sleep(1),
        lambda: focus_on_model("model"),  # 使用模型的名称
        lambda: time.sleep(1),
        lambda: reset_model()
    ]
    
    results = []
    for test in tests:
        result = test()
        if isinstance(result, bool):
            results.append(result)
    
    # 确保有测试结果
    if results:
        success_rate = sum(results) / len([r for r in results if isinstance(r, bool)]) * 100
        print_header(f"测试完成 (Test Completed)")
        print(f"成功率: {success_rate:.1f}%")
    else:
        print_header("测试完成但未获取到结果")
    
    return True

if __name__ == "__main__":
    # 检查命令行参数
    if len(sys.argv) > 1:
        # 自定义服务地址
        API_URL = sys.argv[1]
    
    print(f"使用服务地址: {API_URL}")
    
    # 根据命令行参数执行特定测试
    if len(sys.argv) > 2:
        command = sys.argv[2].lower()
        
        if command == "health":
            check_health()
        elif command == "reinit":
            reinitialize_browser()
        elif command == "rotate":
            angle = int(sys.argv[3]) if len(sys.argv) > 3 else 30
            direction = sys.argv[4] if len(sys.argv) > 4 else "left"
            rotate_model(direction=direction, angle=angle)
        elif command == "zoom":
            scale = float(sys.argv[3]) if len(sys.argv) > 3 else 1.5
            zoom_model(scale=scale)
        elif command == "focus":
            target = sys.argv[3] if len(sys.argv) > 3 else "model"
            focus_on_model(target)
        elif command == "reset":
            reset_model()
        else:
            print(f"未知命令: {command}")
            print("可用命令: health, reinit, rotate, zoom, focus, reset")
    else:
        # 默认运行所有测试
        try:
            run_all_tests()
        except Exception as e:
            print(f"测试过程中出错: {e}")
            import traceback
            traceback.print_exc() 