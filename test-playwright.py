#!/usr/bin/env python
# -*- coding: utf-8 -*-

import asyncio
from playwright.async_api import async_playwright
import sys
import time
import traceback
from typing import Dict, Any, Optional

async def test_page_load(page) -> bool:
    """测试页面加载"""
    try:
        print("\n=== 测试页面加载 ===")
        await page.goto("http://localhost:3000")
        print("页面加载成功")
        return True
    except Exception as e:
        print(f"页面加载失败: {str(e)}")
        print(f"错误详情: {traceback.format_exc()}")
        return False

async def test_rotate(page) -> bool:
    """测试旋转操作"""
    try:
        print("\n=== 测试旋转操作 ===")
        result = await page.evaluate("""() => {
            try {
                window.rotateModel({direction: 'left', angle: 45});
                return true;
            } catch (e) {
                console.error('旋转操作失败:', e);
                return false;
            }
        }""")
        print(f"旋转操作结果: {result}")
        return bool(result)
    except Exception as e:
        print(f"旋转操作测试出错: {str(e)}")
        print(f"错误详情: {traceback.format_exc()}")
        return False

async def test_zoom(page) -> bool:
    """测试缩放操作"""
    try:
        print("\n=== 测试缩放操作 ===")
        result = await page.evaluate("""() => {
            try {
                window.zoomModel({scale: 1.5});
                return true;
            } catch (e) {
                console.error('缩放操作失败:', e);
                return false;
            }
        }""")
        print(f"缩放操作结果: {result}")
        return bool(result)
    except Exception as e:
        print(f"缩放操作测试出错: {str(e)}")
        print(f"错误详情: {traceback.format_exc()}")
        return False

async def test_focus(page) -> bool:
    """测试聚焦操作"""
    try:
        print("\n=== 测试聚焦操作 ===")
        result = await page.evaluate("""() => {
            try {
                window.focusModel({target: 'Area_1'});
                return true;
            } catch (e) {
                console.error('聚焦操作失败:', e);
                return false;
            }
        }""")
        print(f"聚焦操作结果: {result}")
        return bool(result)
    except Exception as e:
        print(f"聚焦操作测试出错: {str(e)}")
        print(f"错误详情: {traceback.format_exc()}")
        return False

async def test_reset(page) -> bool:
    """测试重置操作"""
    try:
        print("\n=== 测试重置操作 ===")
        result = await page.evaluate("""() => {
            try {
                window.resetModel();
                return true;
            } catch (e) {
                console.error('重置操作失败:', e);
                return false;
            }
        }""")
        print(f"重置操作结果: {result}")
        return bool(result)
    except Exception as e:
        print(f"重置操作测试出错: {str(e)}")
        print(f"错误详情: {traceback.format_exc()}")
        return False

async def test_all() -> None:
    """运行所有测试"""
    print("开始运行所有Playwright测试...")
    
    async with async_playwright() as p:
        try:
            # 启动浏览器
            browser = await p.chromium.launch(headless=False)
            context = await browser.new_context()
            page = await context.new_page()
            
            # 运行测试
            results = {
                "页面加载": await test_page_load(page),
                "旋转操作": await test_rotate(page),
                "缩放操作": await test_zoom(page),
                "聚焦操作": await test_focus(page),
                "重置操作": await test_reset(page)
            }
            
            # 输出结果
            print("\n=== 测试结果汇总 ===")
            success_count = sum(1 for result in results.values() if result)
            total_count = len(results)
            print(f"总测试数: {total_count}")
            print(f"通过数量: {success_count}")
            print(f"失败数量: {total_count - success_count}")
            print(f"通过率: {(success_count / total_count) * 100:.2f}%")
            
            print("\n详细结果:")
            for test_name, result in results.items():
                print(f"{test_name}: {'通过' if result else '失败'}")
            
            # 关闭浏览器
            await context.close()
            await browser.close()
            
        except Exception as e:
            print(f"测试执行出错: {str(e)}")
            print(f"错误详情: {traceback.format_exc()}")
            if 'browser' in locals():
                await browser.close()

async def main():
    """主函数"""
    try:
        if len(sys.argv) > 1:
            # 根据命令行参数运行特定测试
            test_name = sys.argv[1].lower()
            async with async_playwright() as p:
                browser = await p.chromium.launch(headless=False)
                context = await browser.new_context()
                page = await context.new_page()
                
                if test_name == "load":
                    await test_page_load(page)
                elif test_name == "rotate":
                    await test_rotate(page)
                elif test_name == "zoom":
                    await test_zoom(page)
                elif test_name == "focus":
                    await test_focus(page)
                elif test_name == "reset":
                    await test_reset(page)
                else:
                    print(f"未知的测试名称: {test_name}")
                    print("可用的测试: load, rotate, zoom, focus, reset")
                
                await context.close()
                await browser.close()
        else:
            # 运行所有测试
            await test_all()
    except KeyboardInterrupt:
        print("\n测试被用户中断")
    except Exception as e:
        print(f"测试执行出错: {str(e)}")
        print(f"错误详情: {traceback.format_exc()}")

if __name__ == "__main__":
    asyncio.run(main()) 