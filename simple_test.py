import os
import sys
import traceback

print("=== 简单测试脚本 ===")
print(f"Python版本: {sys.version}")
print(f"当前目录: {os.getcwd()}")

try:
    # 尝试导入所需的库
    print("测试导入库...")
    import fastapi
    print(f"FastAPI版本: {fastapi.__version__}")
    
    import pydantic
    print(f"Pydantic版本: {pydantic.__version__}")
    
    from playwright.async_api import async_playwright
    print("Playwright导入成功")
    
    print("所有库导入成功")
except Exception as e:
    print(f"导入时出错: {e}")
    print(traceback.format_exc())

print("测试完成") 