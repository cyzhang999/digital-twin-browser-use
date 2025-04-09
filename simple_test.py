import requests
import sys
import time
import traceback

# 测试健康检查
def test_health():
    print("==== 测试健康检查 ====")
    try:
        response = requests.get("http://localhost:9000/health", timeout=5)
        print(f"状态码: {response.status_code}")
        if response.status_code == 200:
            data = response.json()
            print(f"服务状态: {data.get('status')}")
            return True
        else:
            print(f"请求失败: {response.text}")
            return False
    except requests.exceptions.ConnectionError:
        print("连接错误: 服务可能未运行")
        return False
    except Exception as e:
        print(f"请求异常: {str(e)}")
        traceback.print_exc()
        return False

# 测试缩放操作
def test_zoom():
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
            timeout=5
        )
        print(f"状态码: {response.status_code}")
        
        if response.status_code == 200:
            data = response.json()
            print(f"响应: {data}")
            return data.get('success', False)
        else:
            print(f"请求失败: {response.text}")
            return False
    except requests.exceptions.ConnectionError:
        print("连接错误: 服务可能未运行")
        return False
    except Exception as e:
        print(f"请求异常: {str(e)}")
        traceback.print_exc()
        return False

if __name__ == "__main__":
    print("正在测试数字孪生浏览器操作服务...")
    
    # 首先检查服务健康状态
    if test_health():
        # 测试缩放操作
        test_zoom()
    else:
        print("\n服务未运行或不可访问，请确保服务已启动并运行在端口9000上。") 