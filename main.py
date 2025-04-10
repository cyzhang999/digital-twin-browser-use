#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
数字孪生浏览器使用服务 (Digital Twin Browser Use Service)
支持MCP协议和Dify集成，提供WebSocket实时通信
"""

import os
import json
import logging
import asyncio
from typing import Dict, Any, List, Optional

from fastapi import FastAPI, WebSocket, WebSocketDisconnect, Request, Depends, HTTPException
from fastapi.responses import JSONResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
import uvicorn

from mcp_server import MCPServer
from dify_processor import DifyProcessor
from websocket_manager import ConnectionManager

# 配置日志
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# 创建FastAPI应用
app = FastAPI(
    title="数字孪生浏览器使用服务",
    description="提供数字孪生模型浏览器的交互功能",
    version="1.0.0"
)

# 创建MCP服务器实例
mcp_server = MCPServer()

# 创建Dify处理器实例
dify_processor = DifyProcessor()

# 创建WebSocket连接管理器
connection_manager = ConnectionManager()

# 设置静态文件目录
app.mount("/static", StaticFiles(directory="static"), name="static")

# 设置模板引擎
templates = Jinja2Templates(directory="templates")

@app.get("/", response_class=HTMLResponse)
async def root():
    """服务根路径，返回服务启动信息"""
    return HTMLResponse(content="<h1>数字孪生浏览器使用服务已启动</h1>")

@app.get("/test", response_class=HTMLResponse)
async def test_page(request: Request):
    """测试页面"""
    return templates.TemplateResponse("test.html", {"request": request})

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    """WebSocket连接入口点"""
    await connection_manager.connect(websocket)
    try:
        while True:
            # 接收客户端消息
            data = await websocket.receive_text()
            
            # 解析消息
            try:
                message = json.loads(data)
                logger.info(f"收到WebSocket消息: {message}")
                
                # 处理不同类型的消息
                if "type" in message:
                    if message["type"] == "command":
                        # 处理命令消息
                        result = await process_command(message)
                        await websocket.send_json(result)
                    elif message["type"] == "health_check":
                        # 处理健康检查消息
                        result = await get_health_status()
                        await websocket.send_json(result)
                    else:
                        # 处理未知类型消息
                        await websocket.send_json({
                            "type": "error",
                            "message": f"未知消息类型: {message['type']}"
                        })
                else:
                    # 缺少类型信息的消息
                    await websocket.send_json({
                        "type": "error",
                        "message": "消息缺少类型信息"
                    })
            except json.JSONDecodeError:
                # 非JSON消息
                await websocket.send_json({
                    "type": "error",
                    "message": "消息格式错误，需要JSON格式"
                })
            except Exception as e:
                # 其他异常
                logger.error(f"处理WebSocket消息时出错: {e}")
                await websocket.send_json({
                    "type": "error",
                    "message": f"处理消息时出错: {str(e)}"
                })
    except WebSocketDisconnect:
        # 客户端断开连接
        connection_manager.disconnect(websocket)
        logger.info("客户端断开WebSocket连接")

@app.post("/api/mcp/execute")
async def execute_mcp_command(request: Request):
    """
    处理MCP命令执行请求
    
    用于从Dify接收并执行MCP命令
    """
    try:
        # 解析请求体
        body = await request.json()
        logger.info(f"收到MCP命令执行请求: {body}")
        
        # 验证请求参数
        if "operation" not in body:
            raise HTTPException(status_code=400, detail="缺少operation参数")
        
        # 提取操作信息
        operation = body.get("operation")
        parameters = body.get("parameters", {})
        
        # 执行MCP命令
        result = await mcp_server.execute_operation(operation, parameters)
        
        # 返回执行结果
        return JSONResponse(content=result)
    except json.JSONDecodeError:
        raise HTTPException(status_code=400, detail="请求体必须是有效的JSON")
    except Exception as e:
        logger.error(f"执行MCP命令时出错: {e}")
        raise HTTPException(status_code=500, detail=f"执行命令时出错: {str(e)}")

@app.post("/api/mcp/tool/{tool_name}")
async def execute_tool(tool_name: str, request: Request):
    """
    执行指定的工具
    
    用于Dify工具调用
    """
    try:
        # 解析请求体
        body = await request.json()
        logger.info(f"收到工具调用请求: {tool_name}, 参数: {body}")
        
        # 执行工具调用
        result = await dify_processor.call_tool(tool_name, body)
        
        # 返回执行结果
        return JSONResponse(content=result)
    except json.JSONDecodeError:
        raise HTTPException(status_code=400, detail="请求体必须是有效的JSON")
    except Exception as e:
        logger.error(f"执行工具时出错: {e}")
        raise HTTPException(status_code=500, detail=f"执行工具时出错: {str(e)}")

async def process_command(message: Dict[str, Any]) -> Dict[str, Any]:
    """
    处理命令消息
    
    Args:
        message: 命令消息
        
    Returns:
        处理结果
    """
    try:
        # 验证命令消息格式
        if "command" not in message:
            return {
                "type": "error",
                "message": "消息缺少command字段"
            }
        
        command = message["command"]
        params = message.get("params", {})
        
        # 执行MCP命令
        result = await mcp_server.execute_operation(command, params)
        
        # 广播命令执行结果
        await connection_manager.broadcast({
            "type": "command_result",
            "command": command,
            "result": result
        })
        
        return {
            "type": "command_result",
            "command": command,
            "result": result
        }
    except Exception as e:
        logger.error(f"处理命令时出错: {e}")
        return {
            "type": "error",
            "message": f"处理命令时出错: {str(e)}"
        }

async def get_health_status() -> Dict[str, Any]:
    """
    获取服务健康状态
    
    Returns:
        健康状态信息
    """
    try:
        # 获取MCP服务器状态
        mcp_status = mcp_server.get_status()
        
        # 返回健康状态
        return {
            "type": "health_status",
            "status": "ok",
            "services": {
                "mcp_server": mcp_status
            },
            "connections": connection_manager.get_active_connections_count()
        }
    except Exception as e:
        logger.error(f"获取健康状态时出错: {e}")
        return {
            "type": "health_status",
            "status": "error",
            "message": f"获取健康状态时出错: {str(e)}"
        }

async def register_mcp_tools():
    """注册MCP工具到Dify"""
    try:
        # 获取MCP工具定义
        tools = dify_processor.get_mcp_tool_definitions()
        
        # 注册旋转工具
        dify_processor.register_tool("rotate_model", mcp_server.execute_rotate_operation)
        
        # 注册缩放工具
        dify_processor.register_tool("zoom_model", mcp_server.execute_zoom_operation)
        
        # 注册聚焦工具
        dify_processor.register_tool("focus_model", mcp_server.execute_focus_operation)
        
        # 注册重置工具
        dify_processor.register_tool("reset_model", mcp_server.execute_reset_operation)
        
        # 向Dify注册工具
        result = await dify_processor.register_to_dify(tools)
        
        if result["success"]:
            logger.info("已成功注册MCP工具到Dify")
        else:
            logger.error(f"注册MCP工具到Dify失败: {result}")
    except Exception as e:
        logger.error(f"注册MCP工具时出错: {e}")

@app.on_event("startup")
async def startup_event():
    """应用启动时执行"""
    # 注册MCP工具
    asyncio.create_task(register_mcp_tools())
    logger.info("数字孪生浏览器使用服务已启动")

@app.on_event("shutdown")
async def shutdown_event():
    """应用关闭时执行"""
    # 清理资源
    connection_manager.close_all()
    logger.info("数字孪生浏览器使用服务已关闭")

if __name__ == "__main__":
    # 获取配置
    host = os.environ.get("HOST", "0.0.0.0")
    port = int(os.environ.get("PORT", "8000"))
    
    # 启动服务
    uvicorn.run("main:app", host=host, port=port, reload=True) 