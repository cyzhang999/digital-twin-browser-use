#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
MCP协议简单测试脚本
"""

import json
import asyncio
from mcp_adapter import MCPCommand, MCPMessage, generate_mcp_command_from_nl

async def test_mcp_command():
    """测试MCP命令创建和序列化"""
    # 创建旋转命令
    rotate_cmd = MCPCommand.rotate("left", 45)
    print(f"旋转命令: {json.dumps(rotate_cmd.to_dict(), ensure_ascii=False)}")
    
    # 创建缩放命令
    zoom_cmd = MCPCommand.zoom(1.5)
    print(f"缩放命令: {json.dumps(zoom_cmd.to_dict(), ensure_ascii=False)}")
    
    # 创建聚焦命令
    focus_cmd = MCPCommand.focus("meeting_room")
    print(f"聚焦命令: {json.dumps(focus_cmd.to_dict(), ensure_ascii=False)}")
    
    # 创建重置命令
    reset_cmd = MCPCommand.reset()
    print(f"重置命令: {json.dumps(reset_cmd.to_dict(), ensure_ascii=False)}")

async def test_mcp_message():
    """测试MCP消息创建和序列化"""
    # 创建命令消息
    rotate_cmd = MCPCommand.rotate("left", 45)
    command_msg = MCPMessage.command(rotate_cmd)
    print(f"命令消息: {command_msg.to_json()}")
    
    # 创建响应消息
    response_msg = MCPMessage.response(rotate_cmd.id, True, {"rotated": True})
    print(f"响应消息: {response_msg.to_json()}")
    
    # 创建错误消息
    error_msg = MCPMessage.error("操作失败", 500)
    print(f"错误消息: {error_msg.to_json()}")

async def test_nl_command():
    """测试自然语言生成命令"""
    nl_messages = [
        "向左旋转模型45度",
        "放大模型1.5倍",
        "聚焦到会议室区域",
        "重置模型视图"
    ]
    
    for message in nl_messages:
        command = await generate_mcp_command_from_nl(message)
        if command:
            print(f"自然语言: {message}")
            print(f"生成命令: {json.dumps(command.to_dict(), ensure_ascii=False)}")
            print()

async def main():
    """主函数"""
    print("=== 测试MCP命令 ===")
    await test_mcp_command()
    print()
    
    print("=== 测试MCP消息 ===")
    await test_mcp_message()
    print()
    
    print("=== 测试自然语言生成命令 ===")
    await test_nl_command()
    print()

if __name__ == "__main__":
    asyncio.run(main()) 