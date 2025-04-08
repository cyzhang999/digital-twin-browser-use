#!/usr/bin/env python
# -*- coding: utf-8 -*-

import asyncio
from playwright.async_api import async_playwright
import sys
import time
import traceback
from typing import Dict, Any, Optional, List
from dataclasses import dataclass
from enum import Enum

class ActionType(Enum):
    """操作类型枚举"""
    ROTATE = "rotate"
    ZOOM = "zoom"
    FOCUS = "focus"
    RESET = "reset"

@dataclass
class Action:
    """操作数据类"""
    type: ActionType
    target: Optional[str] = None
    parameters: Dict[str, Any] = None

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典格式"""
        return {
            "action": self.type.value,
            "target": self.target,
            "parameters": self.parameters or {}
        }

class MCPTest:
    """MCP测试类"""
    def __init__(self):
        self.browser = None
        self.context = None
        self.page = None
        self.playwright = None
        self.test_results: List[Dict[str, Any]] = []

    async def setup(self):
        """初始化测试环境"""
        try:
            print("\n=== 初始化MCP测试环境 ===")
            self.playwright = await async_playwright().start()
            self.browser = await self.playwright.chromium.launch(headless=False)
            self.context = await self.browser.new_context()
            self.page = await self.context.new_page()
            print("测试环境初始化成功")
        except Exception as e:
            print(f"测试环境初始化失败: {str(e)}")
            print(f"错误详情: {traceback.format_exc()}")
            raise

    async def cleanup(self):
        """清理测试环境"""
        try:
            if self.page:
                await self.page.close()
            if self.context:
                await self.context.close()
            if self.browser:
                await self.browser.close()
            if self.playwright:
                await self.playwright.stop()
            print("测试环境清理完成")
        except Exception as e:
            print(f"测试环境清理失败: {str(e)}")
            print(f"错误详情: {traceback.format_exc()}")

    async def execute_action(self, action: Action) -> bool:
        """执行单个操作"""
        try:
            print(f"\n=== 执行操作: {action.type.value} ===")
            print(f"操作参数: {action.to_dict()}")
            
            # 构建JavaScript代码
            js_code = f"""() => {{
                try {{
                    switch("{action.type.value}") {{
                        case "rotate":
                            window.rotateModel({action.parameters});
                            break;
                        case "zoom":
                            window.zoomModel({action.parameters});
                            break;
                        case "focus":
                            window.focusModel({action.parameters});
                            break;
                        case "reset":
                            window.resetModel();
                            break;
                    }}
                    return true;
                }} catch (e) {{
                    console.error('操作执行失败:', e);
                    return false;
                }}
            }}"""
            
            # 执行操作
            result = await self.page.evaluate(js_code)
            print(f"操作结果: {result}")
            
            # 记录测试结果
            self.test_results.append({
                "action": action.type.value,
                "parameters": action.parameters,
                "success": bool(result),
                "timestamp": time.time()
            })
            
            return bool(result)
        except Exception as e:
            print(f"操作执行出错: {str(e)}")
            print(f"错误详情: {traceback.format_exc()}")
            return False

    async def test_sequence(self, actions: List[Action]) -> None:
        """测试操作序列"""
        try:
            print("\n=== 开始测试操作序列 ===")
            results = []
            
            for action in actions:
                success = await self.execute_action(action)
                results.append({
                    "action": action.type.value,
                    "success": success
                })
                await asyncio.sleep(1)  # 等待操作完成
            
            # 输出序列测试结果
            print("\n=== 序列测试结果 ===")
            success_count = sum(1 for r in results if r["success"])
            total_count = len(results)
            print(f"总操作数: {total_count}")
            print(f"成功数量: {success_count}")
            print(f"失败数量: {total_count - success_count}")
            print(f"成功率: {(success_count / total_count) * 100:.2f}%")
            
            print("\n详细结果:")
            for result in results:
                print(f"{result['action']}: {'成功' if result['success'] else '失败'}")
                
        except Exception as e:
            print(f"序列测试出错: {str(e)}")
            print(f"错误详情: {traceback.format_exc()}")

    async def test_concurrent(self, actions: List[Action]) -> None:
        """测试并发操作"""
        try:
            print("\n=== 开始测试并发操作 ===")
            tasks = [self.execute_action(action) for action in actions]
            results = await asyncio.gather(*tasks, return_exceptions=True)
            
            # 输出并发测试结果
            print("\n=== 并发测试结果 ===")
            success_count = sum(1 for r in results if r is True)
            total_count = len(results)
            print(f"总操作数: {total_count}")
            print(f"成功数量: {success_count}")
            print(f"失败数量: {total_count - success_count}")
            print(f"成功率: {(success_count / total_count) * 100:.2f}%")
            
            print("\n详细结果:")
            for action, result in zip(actions, results):
                if isinstance(result, Exception):
                    print(f"{action.type.value}: 异常 - {str(result)}")
                else:
                    print(f"{action.type.value}: {'成功' if result else '失败'}")
                    
        except Exception as e:
            print(f"并发测试出错: {str(e)}")
            print(f"错误详情: {traceback.format_exc()}")

async def main():
    """主函数"""
    try:
        # 创建测试实例
        mcp_test = MCPTest()
        
        # 初始化测试环境
        await mcp_test.setup()
        
        # 定义测试操作
        test_actions = [
            Action(ActionType.ROTATE, parameters={"direction": "left", "angle": 45}),
            Action(ActionType.ZOOM, parameters={"scale": 1.5}),
            Action(ActionType.FOCUS, target="Area_1", parameters={}),
            Action(ActionType.RESET),
            Action(ActionType.ROTATE, parameters={"direction": "right", "angle": 30}),
            Action(ActionType.ZOOM, parameters={"scale": 0.8}),
            Action(ActionType.FOCUS, target="Area_2", parameters={}),
            Action(ActionType.RESET)
        ]
        
        # 运行序列测试
        await mcp_test.test_sequence(test_actions)
        
        # 运行并发测试
        await mcp_test.test_concurrent(test_actions)
        
    except KeyboardInterrupt:
        print("\n测试被用户中断")
    except Exception as e:
        print(f"测试执行出错: {str(e)}")
        print(f"错误详情: {traceback.format_exc()}")
    finally:
        if 'mcp_test' in locals():
            await mcp_test.cleanup()

if __name__ == "__main__":
    asyncio.run(main()) 