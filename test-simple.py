import requests
import sys
import time
import traceback
from typing import Dict, Any, Optional

# 设置请求超时时间
TIMEOUT = 10

def test_health() -> Dict[str, Any]:
    """测试健康检查接口"""
    print("\n=== 测试健康检查接口 ===")
    try:
        response = requests.get("http://localhost:9000/health", timeout=TIMEOUT)
        print(f"HTTP状态码: {response.status_code}")
        data = response.json()
        print(f"响应数据: {data}")
        return data
    except Exception as e:
        print(f"健康检查失败: {str(e)}")
        print(f"错误详情: {traceback.format_exc()}")
        return {"status": "error", "message": str(e)}

def test_rotate() -> Dict[str, Any]:
    """测试旋转操作"""
    print("\n=== 测试旋转操作 ===")
    try:
        data = {
            "action": "rotate",
            "target": None,
            "parameters": {
                "direction": "left",
                "angle": 45
            }
        }
        print(f"发送请求数据: {data}")
        response = requests.post(
            "http://localhost:9000/api/execute",
            json=data,
            timeout=TIMEOUT
        )
        print(f"HTTP状态码: {response.status_code}")
        result = response.json()
        print(f"响应数据: {result}")
        return result
    except Exception as e:
        print(f"旋转操作失败: {str(e)}")
        print(f"错误详情: {traceback.format_exc()}")
        return {"success": False, "message": str(e)}

def test_zoom() -> Dict[str, Any]:
    """测试缩放操作"""
    print("\n=== 测试缩放操作 ===")
    try:
        data = {
            "action": "zoom",
            "target": None,
            "parameters": {
                "scale": 1.5
            }
        }
        print(f"发送请求数据: {data}")
        response = requests.post(
            "http://localhost:9000/api/execute",
            json=data,
            timeout=TIMEOUT
        )
        print(f"HTTP状态码: {response.status_code}")
        result = response.json()
        print(f"响应数据: {result}")
        return result
    except Exception as e:
        print(f"缩放操作失败: {str(e)}")
        print(f"错误详情: {traceback.format_exc()}")
        return {"success": False, "message": str(e)}

def test_reset() -> Dict[str, Any]:
    """测试重置操作"""
    print("\n=== 测试重置操作 ===")
    try:
        data = {
            "action": "reset",
            "target": None,
            "parameters": {}
        }
        print(f"发送请求数据: {data}")
        response = requests.post(
            "http://localhost:9000/api/execute",
            json=data,
            timeout=TIMEOUT
        )
        print(f"HTTP状态码: {response.status_code}")
        result = response.json()
        print(f"响应数据: {result}")
        return result
    except Exception as e:
        print(f"重置操作失败: {str(e)}")
        print(f"错误详情: {traceback.format_exc()}")
        return {"success": False, "message": str(e)}

def test_all() -> None:
    """执行所有测试"""
    print("开始执行所有测试...")
    results = []
    
    # 测试健康检查
    health_result = test_health()
    results.append(("健康检查", health_result.get("status") == "healthy"))
    
    # 测试旋转
    rotate_result = test_rotate()
    results.append(("旋转操作", rotate_result.get("success", False)))
    
    # 等待1秒
    time.sleep(1)
    
    # 测试缩放
    zoom_result = test_zoom()
    results.append(("缩放操作", zoom_result.get("success", False)))
    
    # 等待1秒
    time.sleep(1)
    
    # 测试重置
    reset_result = test_reset()
    results.append(("重置操作", reset_result.get("success", False)))
    
    # 打印测试结果统计
    print("\n=== 测试结果统计 ===")
    success_count = sum(1 for _, success in results if success)
    total_count = len(results)
    print(f"总测试数: {total_count}")
    print(f"成功数: {success_count}")
    print(f"失败数: {total_count - success_count}")
    print(f"成功率: {(success_count/total_count)*100:.1f}%")
    
    # 打印详细结果
    print("\n详细结果:")
    for test_name, success in results:
        status = "成功" if success else "失败"
        print(f"{test_name}: {status}")

def main():
    """主函数"""
    try:
        if len(sys.argv) > 1:
            # 根据命令行参数执行特定测试
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
                print(f"未知的测试名称: {test_name}")
                print("可用的测试名称: health, rotate, zoom, reset")
        else:
            # 执行所有测试
            test_all()
    except KeyboardInterrupt:
        print("\n测试被用户中断")
    except Exception as e:
        print(f"测试过程中发生错误: {str(e)}")
        print(f"错误详情: {traceback.format_exc()}")

if __name__ == "__main__":
    main()
