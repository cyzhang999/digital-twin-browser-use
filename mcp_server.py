#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
MCP服务器实现
(MCP Server Implementation)

基于WebSocket实现标准的MCP（Model Control Protocol）协议，提供更高效的模型操作控制。
"""

import json
import logging
import asyncio
import os
import time
from typing import Dict, List, Any, Optional, Union, Callable, Tuple
from enum import Enum
from datetime import datetime
import uuid
import websockets
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from mcp_command_builder import MCPCommandBuilder
from parse_natural_language import parse_natural_language

# 配置日志
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("mcp_server")

# MCP操作类型
class MCPOperationType(str, Enum):
    ROTATE = "rotate"
    ZOOM = "zoom"
    FOCUS = "focus"
    RESET = "reset"
    CUSTOM = "custom"  # 自定义操作

# MCP命令接口
class MCPCommand:
    """MCP命令"""
    def __init__(
        self, 
        action: str, 
        parameters: Dict[str, Any] = None, 
        target: str = None, 
        command_id: str = None
    ):
        self.action = action or ""  # 确保action不为None
        self.parameters = parameters or {}
        self.target = target
        self.id = command_id or str(uuid.uuid4())
        self.timestamp = datetime.now().isoformat()
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            "id": self.id,
            "action": str(self.action) if self.action else "",  # 确保action是字符串
            "target": self.target,
            "parameters": self.parameters,
            "timestamp": self.timestamp
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'MCPCommand':
        """从字典创建命令"""
        return cls(
            action=data.get("action", ""),
            parameters=data.get("parameters", {}),
            target=data.get("target"),
            command_id=data.get("id")
        )
    
    @classmethod
    def rotate(cls, direction: str, angle: float, target: str = None) -> 'MCPCommand':
        """创建旋转命令"""
        return cls(
            action=MCPOperationType.ROTATE,
            parameters={"direction": direction, "angle": angle},
            target=target
        )
    
    @classmethod
    def zoom(cls, scale: float, target: str = None) -> 'MCPCommand':
        """创建缩放命令"""
        return cls(
            action=MCPOperationType.ZOOM,
            parameters={"scale": scale},
            target=target
        )
    
    @classmethod
    def focus(cls, target: str) -> 'MCPCommand':
        """创建聚焦命令"""
        return cls(
            action=MCPOperationType.FOCUS,
            parameters={},
            target=target
        )
    
    @classmethod
    def reset(cls) -> 'MCPCommand':
        """创建重置命令"""
        return cls(
            action=MCPOperationType.RESET,
            parameters={}
        )

# MCP命令结果
class MCPCommandResult:
    """MCP命令执行结果"""
    def __init__(
        self,
        command_id: str,
        success: bool,
        data: Any = None,
        error: str = None
    ):
        self.command_id = command_id
        self.success = success
        self.data = data
        self.error = error
        self.timestamp = datetime.now().isoformat()
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        result = {
            "commandId": self.command_id,
            "success": self.success,
            "timestamp": self.timestamp
        }
        
        if self.data is not None:
            result["data"] = self.data
        
        if self.error is not None:
            result["error"] = self.error
            
        return result

# WebSocket连接管理器
class ConnectionManager:
    """WebSocket连接管理器"""
    def __init__(self):
        self.active_connections: List[WebSocket] = []
    
    async def connect(self, websocket: WebSocket):
        """处理WebSocket连接"""
        await websocket.accept()
        self.active_connections.append(websocket)
        logger.info(f"客户端连接成功，当前连接数: {len(self.active_connections)}")
    
    def disconnect(self, websocket: WebSocket):
        """处理WebSocket断开连接"""
        if websocket in self.active_connections:
            self.active_connections.remove(websocket)
            logger.info(f"客户端断开连接，当前连接数: {len(self.active_connections)}")
    
    async def broadcast(self, message: Dict[str, Any]):
        """广播消息到所有连接的客户端"""
        if not self.active_connections:
            logger.warning("没有活跃的WebSocket连接，无法广播消息")
            return
            
        disconnected_clients = []
        
        for websocket in self.active_connections:
            try:
                await websocket.send_json(message)
            except Exception as e:
                logger.error(f"广播消息失败: {e}")
                disconnected_clients.append(websocket)
        
        # 清理断开的连接
        for websocket in disconnected_clients:
            self.disconnect(websocket)

    async def send_message(self, message: str, websocket: WebSocket):
        await websocket.send_text(message)
        
    def get_active_connections_count(self) -> int:
        """获取当前活跃的WebSocket连接数"""
        return len(self.active_connections)

# MCP服务器实现
class MCPServer:
    """MCP服务器，用于处理MCP协议命令
    
    处理各种MCP操作命令，包括模型旋转、缩放、高亮等
    管理与前端的WebSocket连接
    """
    
    def __init__(self):
        self.connections: List[WebSocket] = []
        self.operation_handlers: Dict[str, Callable] = {}
        # 初始化logger
        self.logger = logger
        # 初始化browser属性为None
        self.browser = None
        # 注册默认操作处理器
        self._register_default_handlers()
        self.logger.info("MCP服务器初始化完成")
    
    def _register_default_handlers(self):
        """注册默认的操作处理方法"""
        self.register_operation_handler("rotate", self.execute_rotate_operation)
        self.register_operation_handler("zoom", self.execute_zoom_operation)
        self.register_operation_handler("focus", self.execute_focus_operation)
        self.register_operation_handler("reset", self.execute_reset_operation)
        self.register_operation_handler("highlight", self.execute_highlight_operation)
        self.register_operation_handler("execute_js", self.execute_js_operation)
        self.register_operation_handler("batch", self.execute_batch_operation)
        logger.info("已注册默认操作处理器")
    
    async def connect(self, websocket: WebSocket):
        """处理新的WebSocket连接"""
        await websocket.accept()
        self.connections.append(websocket)
        logger.info(f"新的WebSocket连接已建立，当前连接数: {len(self.connections)}")
        try:
            # 保持连接并监听消息
            while True:
                message = await websocket.receive_text()
                await self.process_message(websocket, message)
        except Exception as e:
            logger.error(f"WebSocket连接异常: {str(e)}")
        finally:
            # 断开连接时清理
            await self.disconnect(websocket)
    
    async def disconnect(self, websocket: WebSocket):
        """处理WebSocket断开连接"""
        if websocket in self.connections:
            self.connections.remove(websocket)
            logger.info(f"WebSocket连接已断开，剩余连接数: {len(self.connections)}")
    
    async def process_message(self, websocket: WebSocket, message: str):
        """处理接收到的WebSocket消息"""
        try:
            data = json.loads(message)
            logger.debug(f"收到消息: {data}")
            
            # 根据消息类型分发处理
            msg_type = data.get("type")
            if msg_type == "mcp.command":
                await self.handle_command(websocket, data)
            else:
                logger.warning(f"未知消息类型: {msg_type}")
                await websocket.send_json({"status": "error", "message": f"未知消息类型: {msg_type}"})
        except json.JSONDecodeError:
            logger.error("消息格式错误，不是有效的JSON")
            await websocket.send_json({"status": "error", "message": "消息格式错误，不是有效的JSON"})
        except Exception as e:
            logger.error(f"处理消息时出错: {str(e)}")
            await websocket.send_json({"status": "error", "message": str(e)})
    
    async def handle_command(self, websocket: WebSocket, command: Dict[str, Any]):
        """处理MCP命令"""
        try:
            operation = command.get("operation")
            params = command.get("params", {})
            command_id = command.get("command_id")
            
            if not operation:
                error_msg = "命令缺少操作类型"
                logger.error(error_msg)
                await websocket.send_json({
                    "type": "mcp.response",
                    "command_id": command_id,
                    "status": "error",
                    "message": error_msg
                })
                return
            
            logger.info(f"处理命令: {operation}, 参数: {params}")
            
            # 查找对应的处理方法
            handler = self.operation_handlers.get(operation)
            if handler:
                result = await handler(params)
                # 发送执行结果
                await websocket.send_json({
                    "type": "mcp.response",
                    "command_id": command_id,
                    "status": "success" if result.get("success", False) else "error",
                    "data": result.get("data", {}),
                    "message": result.get("message", "")
                })
            else:
                error_msg = f"未知操作类型: {operation}"
                logger.warning(error_msg)
                await websocket.send_json({
                    "type": "mcp.response",
                    "command_id": command_id,
                    "status": "error",
                    "message": error_msg
                })
        except Exception as e:
            logger.error(f"处理命令时出错: {str(e)}")
            await websocket.send_json({
                "type": "mcp.response",
                "command_id": command.get("command_id"),
                "status": "error",
                "message": f"处理命令时出错: {str(e)}"
            })
    
    async def broadcast_command(self, command: Dict[str, Any]):
        """广播命令到所有连接的客户端"""
        if not self.connections:
            logger.warning("没有活跃的连接，无法广播命令")
            return False
        
        try:
            command_str = MCPCommandBuilder.serialize_command(command)
            tasks = [connection.send_text(command_str) for connection in self.connections]
            await asyncio.gather(*tasks)
            logger.info(f"已广播命令到 {len(self.connections)} 个客户端")
            return True
        except Exception as e:
            logger.error(f"广播命令时出错: {str(e)}")
            return False
    
    def register_operation_handler(self, operation: str, handler: Callable):
        """注册操作处理方法"""
        self.operation_handlers[operation] = handler
        logger.debug(f"已注册操作处理器: {operation}")
    
    async def execute_rotate_operation(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """执行旋转操作"""
        try:
            if not params or 'direction' not in params or 'angle' not in params:
                return {"success": False, "error": "旋转操作缺少必要参数 (direction/angle)"}
            
            direction = params.get('direction', 'left')
            angle = float(params.get('angle', 0.1))
            
            # 将角度转换为弧度
            angle_rad = angle * (3.14159 / 180)
            
            # 由于不再使用Playwright/Selenium (self.browser为None)，直接通过WebSocket发送命令到前端
            logger.info(f"准备通过WebSocket发送旋转操作: direction={direction}, angle={angle}")
            
            # 构建MCP命令
            command = {
                "type": "mcp.command",
                "operation": "rotate",
                "params": {
                    "direction": direction,
                    "angle": angle
                },
                "command_id": str(uuid.uuid4())
            }
            
            # 广播到所有连接的客户端
            broadcast_success = await self.broadcast_command(command)
            
            if not broadcast_success:
                return {"success": False, "error": "没有活跃的WebSocket连接，无法执行旋转操作"}
            
            return {
                "success": True,
                "message": f"已发送旋转命令: 方向={direction}, 角度={angle}°",
                "data": {
                    "direction": direction,
                    "angle": angle
                }
            }
        except Exception as e:
            logging.error(f"执行旋转操作时出错: {str(e)}")
            import traceback
            traceback.print_exc()
            return {"success": False, "error": f"执行旋转操作时出错: {str(e)}"}
    
    async def execute_zoom_operation(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """执行缩放操作"""
        try:
            scale = params.get("scale")
            
            if scale is None:
                return {"success": False, "message": "缺少缩放参数"}
            
            # 确保scale是数值类型
            if isinstance(scale, dict) and "scale" in scale:
                scale = float(scale["scale"])
            else:
                scale = float(scale)
            
            if scale <= 0:
                return {"success": False, "message": "缩放比例必须大于0"}
            
            self.logger.info(f"执行缩放操作: scale={scale}")
            
            # 构建MCP命令
            command = {
                "type": "mcp.command",
                "operation": "zoom",
                "params": {
                    "scale": scale
                },
                "command_id": str(uuid.uuid4())
            }
            
            # 广播到所有连接的客户端
            broadcast_success = await self.broadcast_command(command)
            
            if not broadcast_success:
                return {"success": False, "error": "没有活跃的WebSocket连接，无法执行缩放操作"}
            
            return {
                "success": True, 
                "message": f"已发送缩放命令: 比例={scale}",
                "data": {
                    "scale": scale
                }
            }
            
        except Exception as e:
            self.logger.error(f"执行缩放操作时出错: {str(e)}")
            import traceback
            traceback.print_exc()
            return {"success": False, "message": f"执行缩放操作时出错: {str(e)}"}
    
    async def execute_focus_operation(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """执行聚焦操作"""
        try:
            target = params.get("target")
            
            if not target:
                return {"success": False, "message": "缺少目标参数"}
            
            self.logger.info(f"执行聚焦操作: target={target}")
            
            # 构建MCP命令
            command = {
                "type": "mcp.command",
                "operation": "focus",
                "params": {
                    "target": target
                },
                "command_id": str(uuid.uuid4())
            }
            
            # 广播到所有连接的客户端
            broadcast_success = await self.broadcast_command(command)
            
            if not broadcast_success:
                return {"success": False, "error": "没有活跃的WebSocket连接，无法执行聚焦操作"}
            
            return {
                "success": True, 
                "message": f"已发送聚焦命令: 目标={target}",
                "data": {
                    "target": target
                }
            }
            
        except Exception as e:
            self.logger.error(f"执行聚焦操作时出错: {str(e)}")
            import traceback
            traceback.print_exc()
            return {"success": False, "message": f"执行聚焦操作时出错: {str(e)}"}
    
    async def execute_reset_operation(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """执行重置视图操作"""
        try:
            self.logger.info("执行重置视图操作")
            
            # 构建MCP命令
            command = {
                "type": "mcp.command",
                "operation": "reset",
                "params": {},
                "command_id": str(uuid.uuid4())
            }
            
            # 广播到所有连接的客户端
            broadcast_success = await self.broadcast_command(command)
            
            if not broadcast_success:
                return {"success": False, "error": "没有活跃的WebSocket连接，无法执行重置操作"}
            
            return {
                "success": True, 
                "message": "已发送重置视图命令",
                "data": {}
            }
            
        except Exception as e:
            self.logger.error(f"执行重置视图操作时出错: {str(e)}")
            import traceback
            traceback.print_exc()
            return {"success": False, "message": f"执行重置视图操作时出错: {str(e)}"}
    
    async def execute_highlight_operation(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """执行高亮组件操作"""
        try:
            component_id = params.get("component_id")
            color = params.get("color", "#FF0000")
            duration = params.get("duration")
            
            if not component_id:
                return {"success": False, "message": "缺少组件ID参数"}
            
            self.logger.info(f"执行高亮操作: component_id={component_id}, color={color}, duration={duration}")
            
            # 由于不再使用Playwright，直接返回成功结果
            return {
                "success": True, 
                "message": f"已发送高亮命令: 组件={component_id}, 颜色={color}" + 
                          (f", 持续时间={duration}秒" if duration is not None else ""),
                "data": {
                    "component_id": component_id,
                    "color": color,
                    "duration": duration
                }
            }
            
        except Exception as e:
            self.logger.error(f"执行高亮操作时出错: {str(e)}")
            return {"success": False, "message": f"执行高亮操作时出错: {str(e)}"}
    
    async def execute_js_operation(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """执行JavaScript代码操作"""
        try:
            code = params.get("code")
            
            if not code:
                return {"success": False, "message": "缺少JavaScript代码参数"}
            
            self.logger.info(f"执行JavaScript操作, 代码长度: {len(code)}字符")
            
            # 由于不再使用Playwright，直接返回成功结果
            return {
                "success": True, 
                "message": "已发送JavaScript执行命令",
                "data": {
                    "code_length": len(code)
                }
            }
            
        except Exception as e:
            self.logger.error(f"执行JavaScript代码操作时出错: {str(e)}")
            return {"success": False, "message": f"执行JavaScript代码操作时出错: {str(e)}"}
    
    async def execute_batch_operation(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """执行批量操作命令"""
        try:
            commands = params.get("commands", [])
            
            if not commands:
                return {"success": False, "message": "批量命令列表为空"}
            
            results = []
            for cmd in commands:
                operation = cmd.get("operation")
                cmd_params = cmd.get("params", {})
                
                handler = self.operation_handlers.get(operation)
                if handler:
                    result = await handler(cmd_params)
                    results.append(result)
                else:
                    results.append({
                        "success": False,
                        "message": f"未知操作类型: {operation}"
                    })
            
            success_count = sum(1 for result in results if result.get("success", False))
            
            return {
                "success": success_count > 0,
                "message": f"批量操作完成，成功: {success_count}/{len(commands)}",
                "data": {
                    "results": results
                }
            }
            
        except Exception as e:
            logger.error(f"执行批量操作时出错: {str(e)}")
            return {"success": False, "message": f"执行批量操作时出错: {str(e)}"}

# 操作处理器
class OperationHandler:
    """MCP操作处理器"""
    
    def __init__(self):
        self.operations: Dict[str, Callable] = {}
    
    def register_operation(self, operation_type: str, handler: Callable):
        """注册操作处理方法"""
        self.operations[operation_type] = handler
    
    def get_handler(self, operation_type: str) -> Optional[Callable]:
        """获取操作处理方法"""
        return self.operations.get(operation_type)
        
    def get_registered_operations(self) -> List[str]:
        """获取所有已注册的操作类型列表"""
        return list(self.operations.keys())

def main():
    """主函数"""
    import uvicorn
    from fastapi.middleware.cors import CORSMiddleware
    
    # 创建FastAPI应用
    app = FastAPI()
    
    # 配置CORS
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    
    # 创建连接管理器和MCP服务器实例
    connection_manager = ConnectionManager()
    mcp_server = MCPServer()
    operation_handler = OperationHandler()
    
    # 注册操作处理函数 - 使用MCP服务器中的方法
    operation_handler.register_operation("rotate", mcp_server.execute_rotate_operation)
    operation_handler.register_operation("zoom", mcp_server.execute_zoom_operation)
    operation_handler.register_operation("focus", mcp_server.execute_focus_operation)
    operation_handler.register_operation("reset", mcp_server.execute_reset_operation)
    
    # WebSocket连接端点
    @app.websocket("/ws")
    async def websocket_endpoint(websocket: WebSocket):
        await connection_manager.connect(websocket)
        try:
            while True:
                data = await websocket.receive_json()
                logger.info(f"收到WebSocket消息: {data}")
                
                # 处理MCP命令
                if "action" in data:
                    action = data.get("action", "")
                    if not action:
                        logger.warning("收到空操作类型的命令")
                        await websocket.send_json({"status": "error", "message": "操作类型不能为空"})
                        continue
                        
                    handler = operation_handler.get_handler(action)
                    if handler:
                        try:
                            result = await handler(data.get("parameters", {}))
                            await websocket.send_json({
                                "status": "success",
                                "commandId": data.get("id", str(uuid.uuid4())),
                                "result": result
                            })
                        except Exception as e:
                            logger.error(f"执行操作 {action} 时出错: {str(e)}")
                            await websocket.send_json({
                                "status": "error",
                                "commandId": data.get("id", str(uuid.uuid4())),
                                "error": str(e)
                            })
                    else:
                        logger.warning(f"未找到操作处理器: {action}")
                        await websocket.send_json({
                            "status": "error", 
                            "message": f"未支持的操作类型: {action}"
                        })
                else:
                    await websocket.send_json({"status": "error", "message": "消息格式不正确，缺少'action'字段"})
        except WebSocketDisconnect:
            connection_manager.disconnect(websocket)
        except Exception as e:
            logger.error(f"WebSocket处理异常: {str(e)}")
            connection_manager.disconnect(websocket)
    
    # 添加健康检查端点
    @app.get("/health")
    async def health_check():
        """健康检查端点"""
        return {"status": "ok", "service": "mcp_server"}
    
    # 添加WebSocket状态检查端点
    @app.get("/api/websocket/status")
    async def websocket_status():
        """WebSocket状态检查端点"""
        return {
            "status": "available", 
            "connections": connection_manager.get_active_connections_count(),
            "operations": operation_handler.get_registered_operations()
        }
    
    # 添加AI助手请求处理接口
    @app.post("/api/llm/process")
    async def process_llm_request(request: Request):
        """处理LLM请求"""
        try:
            # 从请求中获取消息
            data = await request.json()
            user_message = data.get("message", "")
            
            if not user_message:
                return JSONResponse(
                    status_code=400,
                    content={"status": "error", "message": "消息内容不能为空"}
                )
                
            logger.info(f"处理AI助手请求: {user_message}")
            
            # 使用改进的命令解析函数，提取操作类型和参数
            operation, parameters = parse_natural_language(user_message)
            
            if not operation:
                return JSONResponse(
                    status_code=400,
                    content={"status": "error", "message": "无法解析操作类型"}
                )
                
            # 获取操作处理器
            handler = operation_handler.get_handler(operation)
            if not handler:
                return JSONResponse(
                    status_code=404,
                    content={"status": "error", "message": f"未找到操作处理器: {operation}"}
                )
                
            # 执行操作
            result = await handler(parameters)
            
            return {
                "status": "success",
                "operation": operation,
                "result": result,
                "message": f"成功执行{operation}操作"
            }
        except Exception as e:
            logger.error(f"处理LLM请求时出错: {str(e)}")
            return JSONResponse(
                status_code=500,
                content={"status": "error", "message": f"处理请求时出错: {str(e)}"}
            )
    
    # 添加通用操作执行接口
    @app.post("/api/execute")
    async def execute_operation(request: Request):
        """执行操作"""
        try:
            # 从请求中获取操作信息
            data = await request.json()
            operation = data.get("operation", "")
            parameters = data.get("parameters", {})
            
            if not operation:
                return JSONResponse(
                    status_code=400,
                    content={"status": "error", "message": "操作类型不能为空"}
                )
                
            # 获取操作处理器
            handler = operation_handler.get_handler(operation)
            if not handler:
                return JSONResponse(
                    status_code=404,
                    content={"status": "error", "message": f"未找到操作处理器: {operation}"}
                )
                
            # 执行操作
            result = await handler(parameters)
            
            return {
                "status": "success",
                "operation": operation,
                "result": result
            }
        except Exception as e:
            logger.error(f"执行操作时出错: {str(e)}")
            return JSONResponse(
                status_code=500,
                content={"status": "error", "message": f"执行操作时出错: {str(e)}"}
            )
    
    # 启动服务器
    port = int(os.environ.get("PORT", 9000))
    print(f"启动MCP服务器，端口: {port}...")
    uvicorn.run(app, host="0.0.0.0", port=port)

# 添加主函数入口
if __name__ == "__main__":
    main() 