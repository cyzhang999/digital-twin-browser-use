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
import traceback
import datetime

# 服务地址配置
API_URL = "http://localhost:9000"  # 默认服务地址

# 测试结果文件
OUTPUT_FILE = "test_results.txt"

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

def write_output(message):
    """写入消息到输出文件"""
    with open(OUTPUT_FILE, "a", encoding="utf-8") as f:
        timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        f.write(f"[{timestamp}] {message}\n")

def clear_output():
    """清除输出文件"""
    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        f.write(f"=== 测试开始于 {datetime.datetime.now()} ===\n\n")

def test_health():
    """测试服务健康状态"""
    write_output("测试健康检查...")
    try:
        response = requests.get("http://localhost:9000/health", timeout=5)
        write_output(f"状态码: {response.status_code}")
        
        if response.status_code == 200:
            data = response.json()
            write_output(f"服务状态: {data.get('status')}")
            write_output(f"浏览器状态: {data.get('browser_status')}")
            write_output(f"页面状态: {data.get('page_status')}")
            write_output(f"JSON响应: {json.dumps(data, ensure_ascii=False, indent=2)}")
            return True
        else:
            write_output(f"请求失败: {response.text}")
            return False
    except requests.exceptions.ConnectionError:
        write_output("连接错误: 服务可能未运行")
        return False
    except Exception as e:
        write_output(f"请求异常: {str(e)}")
        write_output(traceback.format_exc())
        return False

def test_zoom():
    """测试缩放操作"""
    write_output("\n测试缩放操作...")
    
    payload = {
        "operation": "zoom",
        "parameters": {
            "scale": 1.5
        }
    }
    
    write_output(f"请求数据: {json.dumps(payload, ensure_ascii=False)}")
    
    try:
        response = requests.post(
            "http://localhost:9000/api/execute",
            json=payload,
            timeout=5
        )
        
        write_output(f"状态码: {response.status_code}")
        
        if response.status_code == 200:
            data = response.json()
            write_output(f"JSON响应: {json.dumps(data, ensure_ascii=False, indent=2)}")
            success = data.get('success', False)
            write_output(f"操作结果: {'成功' if success else '失败'}")
            return success
        else:
            write_output(f"请求失败: {response.text}")
            return False
    except requests.exceptions.ConnectionError:
        write_output("连接错误: 服务可能未运行")
        return False
    except Exception as e:
        write_output(f"请求异常: {str(e)}")
        write_output(traceback.format_exc())
        return False

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
            test_health()
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
        # 清除输出文件
        clear_output()
        write_output("开始测试数字孪生浏览器操作服务...")
        
        # 测试健康状态
        if test_health():
            write_output("\n服务健康检查通过，继续测试操作...")
            # 测试缩放操作
            zoom_result = test_zoom()
            if zoom_result:
                write_output("\n缩放操作测试通过")
            else:
                write_output("\n缩放操作测试失败")
        else:
            write_output("\n服务未运行或不可访问，请确保服务已启动并运行在端口9000上。")
        
        write_output("\n测试完成，请查看test_results.txt获取详细结果。")
        print(f"测试完成，结果已写入 {OUTPUT_FILE}") 