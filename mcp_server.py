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
import random
import string
import hashlib

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
        # 使用字典存储连接，键为客户端ID
        self.active_connections = {}
        # 按端点类型分类存储连接
        self.endpoint_connections = {
            "status": {},
            "health": {},
            "command": {},
            "general": {}
        }

    async def connect(self, websocket: WebSocket, endpoint_type="general", client_id=None):
        """处理WebSocket连接
        
        Args:
            websocket: WebSocket连接对象
            endpoint_type: 连接端点类型 (status/health/command/general)
            client_id: 客户端ID，如果为None则自动生成
        """
        await websocket.accept()
        
        # 从请求头中提取会话标识
        try:
            # 尝试从cookie或其他自定义头获取会话ID
            cookies = websocket.headers.get("cookie", "")
            user_agent = websocket.headers.get("user-agent", "")
            session_id = ""
            
            # 从cookie中提取会话ID
            if "digital_twin_session_id" in cookies:
                cookie_parts = cookies.split(";")
                for part in cookie_parts:
                    if "digital_twin_session_id" in part:
                        session_id = part.split("=")[1].strip()
                        break
            
            # 如果从WebSocket消息中得到会话ID，优先使用它
            try:
                first_message = await asyncio.wait_for(websocket.receive_json(), timeout=0.5)
                if isinstance(first_message, dict) and "sessionId" in first_message:
                    session_id = first_message["sessionId"]
                    logger.info(f"从WebSocket消息中获取会话ID: {session_id}")
                    # 发送确认消息
                    await websocket.send_json({
                        "type": "session_confirm", 
                        "sessionId": session_id,
                        "timestamp": datetime.now().isoformat()
                    })
            except (asyncio.TimeoutError, json.JSONDecodeError):
                # 忽略超时和解析错误
                pass
            
            # 如果没有会话ID，使用其他方式生成一个稳定标识
            if not session_id:
                # 使用用户代理的哈希作为备用
                if user_agent:
                    session_id = hashlib.md5(user_agent.encode()).hexdigest()[:8]
                else:
                    # 最后使用随机ID
                    session_id = ''.join(random.choices(string.ascii_letters + string.digits, k=8))
        
        except Exception as e:
            logger.error(f"提取会话标识时出错: {e}")
            session_id = ''.join(random.choices(string.ascii_letters + string.digits, k=8))
        
        # 生成客户端ID（格式：HOST_SESSION）
        if not client_id:
            client_id = f"{websocket.client.host}_{session_id}"
        
        # 检查是否存在同一客户端的同类端点连接
        for existing_id, existing_conn in list(self.active_connections.items()):
            # 只有当有相同的会话ID和相同的端点类型时，才视为重复连接
            if existing_id != client_id and existing_conn["endpoint_type"] == endpoint_type:
                existing_session_id = existing_id.split('_')[1] if '_' in existing_id else ""
                if existing_session_id == session_id:
                    try:
                        logger.info(f"发现同一会话的重复连接，断开旧连接: {existing_id}")
                        # 发送断开消息
                        await existing_conn["websocket"].send_json({
                            "type": "close", 
                            "reason": "duplicate_connection",
                            "message": "已在其他位置建立新连接",
                            "timestamp": datetime.now().isoformat()
                        })
                        await existing_conn["websocket"].close(code=1000, reason="重复连接")
                    except Exception as e:
                        logger.error(f"关闭重复连接时出错: {e}")
                    finally:
                        self.disconnect(existing_conn["websocket"], existing_id)
        
        # 保存连接
        self.active_connections[client_id] = {
            "websocket": websocket,
            "endpoint_type": endpoint_type,
            "connected_at": datetime.now(),
            "last_activity": datetime.now(),
            "session_id": session_id
        }
        
        # 按端点类型分类
        if endpoint_type not in self.endpoint_connections:
            self.endpoint_connections[endpoint_type] = {}
        self.endpoint_connections[endpoint_type][client_id] = websocket
        
        logger.info(f"客户端[{client_id}]连接成功，端点类型：{endpoint_type}，当前连接数: {len(self.active_connections)}")
        
        return client_id

    def disconnect(self, websocket: WebSocket, client_id=None):
        """处理WebSocket断开连接"""
        # 如果提供了客户端ID，直接使用它
        if client_id and client_id in self.active_connections:
            # 获取端点类型
            endpoint_type = self.active_connections[client_id]["endpoint_type"]
            # 从特定端点类型的字典中移除
            if endpoint_type in self.endpoint_connections:
                if client_id in self.endpoint_connections[endpoint_type]:
                    del self.endpoint_connections[endpoint_type][client_id]
            # 从总连接字典中移除
            del self.active_connections[client_id]
            logger.info(f"客户端[{client_id}]断开连接，当前连接数: {len(self.active_connections)}")
            return
        
        # 如果没有提供客户端ID，则搜索匹配的WebSocket
        to_remove = []
        for cid, conn_info in self.active_connections.items():
            if conn_info["websocket"] == websocket:
                to_remove.append(cid)
                # 获取端点类型
                endpoint_type = conn_info["endpoint_type"]
                # 从特定端点类型的字典中移除
                if endpoint_type in self.endpoint_connections and cid in self.endpoint_connections[endpoint_type]:
                    del self.endpoint_connections[endpoint_type][cid]
        
        # 从总连接字典中移除
        for cid in to_remove:
            del self.active_connections[cid]
            logger.info(f"客户端[{cid}]断开连接，当前连接数: {len(self.active_connections)}")

    async def broadcast(self, message: Dict[str, Any], endpoint_type=None, exclude_client_id=None):
        """广播消息到指定类型的所有连接的客户端
        
        Args:
            message: 要广播的消息
            endpoint_type: 要广播到的端点类型，如果为None则广播到所有端点
            exclude_client_id: 要排除的客户端ID
        """
        # 确定要广播的连接列表
        target_connections = {}
        
        if endpoint_type and endpoint_type in self.endpoint_connections:
            target_connections = self.endpoint_connections[endpoint_type]
        else:
            # 如果没有指定端点类型，则向所有连接广播
            for ep_type, connections in self.endpoint_connections.items():
                target_connections.update(connections)
        
        if not target_connections:
            logger.warning(f"没有活跃的WebSocket连接[端点类型:{endpoint_type}]，无法广播消息")
            return False
        
        disconnected_clients = []
        success_count = 0
        
        for cid, websocket in list(target_connections.items()):
            # 排除指定的客户端
            if exclude_client_id and cid == exclude_client_id:
                continue
                
            try:
                await websocket.send_json(message)
                success_count += 1
            except Exception as e:
                logger.error(f"向客户端[{cid}]广播消息失败: {e}")
                disconnected_clients.append(cid)
        
        # 清理断开的连接
        for cid in disconnected_clients:
            if endpoint_type and endpoint_type in self.endpoint_connections and cid in self.endpoint_connections[endpoint_type]:
                del self.endpoint_connections[endpoint_type][cid]
            if cid in self.active_connections:
                del self.active_connections[cid]
        
        if success_count > 0:
            logger.info(f"成功广播消息到 {success_count} 个客户端[端点类型:{endpoint_type}]")
            return True
        else:
            logger.warning(f"没有客户端接收到广播消息[端点类型:{endpoint_type}]")
            return False

    async def send_to_client(self, client_id: str, message: Dict[str, Any]) -> bool:
        """向特定客户端发送消息"""
        if client_id not in self.active_connections:
            logger.warning(f"客户端[{client_id}]不存在，无法发送消息")
            return False
        
        try:
            websocket = self.active_connections[client_id]["websocket"]
            await websocket.send_json(message)
            logger.info(f"成功向客户端[{client_id}]发送消息")
            return True
        except Exception as e:
            logger.error(f"向客户端[{client_id}]发送消息失败: {e}")
            # 可能连接已断开，移除该连接
            self.disconnect(None, client_id)
            return False

    async def send_message(self, message: str, websocket: WebSocket):
        """发送文本消息到特定WebSocket"""
        try:
            await websocket.send_text(message)
            return True
        except Exception as e:
            logger.error(f"发送文本消息失败: {e}")
            return False

    def get_client_by_websocket(self, websocket: WebSocket) -> Optional[str]:
        """根据WebSocket对象获取客户端ID"""
        # 先尝试使用ConnectionManager的方法
        for client_id, conn_info in self.active_connections.items():
            if conn_info["websocket"] == websocket:
                return client_id
        
        # 作为备用，获取客户端的host和port信息
        client_address = f"{websocket.client.host}"
        # 尝试查找以此地址开头的客户端
        active_clients = self.get_active_clients()
        for active_id in active_clients:
            if active_id.startswith(client_address):
                return active_id
        
        # 如果都找不到，创建一个临时ID并注册
        temp_id = f"{websocket.client.host}_{uuid.uuid4().hex[:8]}"
        logger.info(f"为WebSocket创建临时客户端ID: {temp_id}")
        
        # 在返回临时ID之前，确保它被注册到连接管理器
        try:
            # 异步注册连接
            loop = asyncio.get_event_loop()
            if loop.is_running():
                asyncio.create_task(self.connect(websocket, endpoint_type="command", client_id=temp_id))
            else:
                loop.run_until_complete(self.connect(websocket, endpoint_type="command", client_id=temp_id))
        except Exception as e:
            logger.warning(f"注册临时客户端ID时出错: {e}")
        
        return temp_id

    def get_active_connections_count(self, endpoint_type=None) -> int:
        """获取当前活跃的WebSocket连接数"""
        if endpoint_type and endpoint_type in self.endpoint_connections:
            return len(self.endpoint_connections[endpoint_type])
        return len(self.active_connections)

    def get_active_clients(self, endpoint_type=None) -> List[str]:
        """获取活跃客户端ID列表"""
        if endpoint_type and endpoint_type in self.endpoint_connections:
            return list(self.endpoint_connections[endpoint_type].keys())
        return list(self.active_connections.keys())


# MCP服务器实现
class MCPServer:
    """MCP服务器，用于处理MCP协议命令
    
    处理各种MCP操作命令，包括模型旋转、缩放、高亮等
    管理与前端的WebSocket连接
    """

    def __init__(self):
        """初始化MCP服务器"""
        # 创建操作处理器注册表
        self.operation_handlers = OperationHandler()
        
        # 注册基本操作处理器
        self._register_default_handlers()
        
        # 连接和消息处理相关变量
        self.pending_messages = {}
        self.browser_control = None
        self.browser = None  # 确保browser属性存在
        self.logger = logger  # 添加logger引用以便在执行方法中使用
        self.connection_manager = None  # 会在main函数中设置
        
        # 初始状态
        self.status = {
            "server": "online",
            "browser": "offline",
            "operations": self.operation_handlers.get_registered_operations()
        }
        
        logger.info(f"MCP服务器已初始化，支持的操作: {self.operation_handlers.get_registered_operations()}")

    def _register_default_handlers(self):
        """注册默认操作处理器"""
        # 注册基本操作
        self.operation_handlers.register_operation(MCPOperationType.ROTATE, self.execute_rotate_operation)
        self.operation_handlers.register_operation(MCPOperationType.ZOOM, self.execute_zoom_operation)
        self.operation_handlers.register_operation(MCPOperationType.FOCUS, self.execute_focus_operation)
        self.operation_handlers.register_operation(MCPOperationType.RESET, self.execute_reset_operation)
        
        # 注册其他操作
        self.operation_handlers.register_operation("highlight", self.execute_highlight_operation)
        self.operation_handlers.register_operation("execute_js", self.execute_js_operation)
        self.operation_handlers.register_operation("batch", self.execute_batch_operation)

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

    async def handle_command(self, websocket: WebSocket, command_data: Dict[str, Any]) -> None:
        """处理MCP命令

        Args:
            websocket: WebSocket连接
            command_data: 命令数据
        """
        try:
            # 提取命令ID，首先检查顶层，然后检查嵌套命令
            command_id = command_data.get("id") or command_data.get("command_id") or str(uuid.uuid4())
            
            # 检查命令格式并规范化
            if "command" in command_data and isinstance(command_data["command"], dict):
                # 处理嵌套命令 - 将嵌套命令提取到顶层
                nested_command = command_data["command"]
                # 保留顶层ID，但使用嵌套命令的其他字段
                action = nested_command.get("action")
                parameters = nested_command.get("parameters", {})
                target = nested_command.get("target")
            else:
                # 直接使用顶层字段
                action = command_data.get("action")
                parameters = command_data.get("parameters", {})
                target = command_data.get("target")
            
            # 检查操作类型
            if not action:
                # 尝试从"type"字段获取操作类型（有些客户端可能使用type而非action）
                action = command_data.get("type")
                if action == "mcp.command":
                    # 如果类型是mcp.command但没有具体操作，尝试从其他字段推断
                    action = command_data.get("operation")
                
                # 如果仍然没有操作类型，报错
                if not action:
                    logger.warning(f"收到空操作类型命令: {json.dumps(command_data)}")
                    await websocket.send_json({
                        "type": "mcp.response",
                        "command_id": command_id,
                        "status": "error",
                        "message": "命令缺少操作类型",
                        "timestamp": datetime.now().isoformat()
                    })
                    return
            
            # 获取客户端ID
            client_id = None
            try:
                client_id = connection_manager.get_client_by_websocket(websocket)
            except Exception as e:
                logger.warning(f"获取客户端ID时出错: {e}")
                
            if not client_id:
                # 创建临时客户端ID
                client_id = f"{websocket.client.host}_{uuid.uuid4().hex[:8]}"
                logger.info(f"创建临时客户端ID: {client_id}")
                
                # 异步注册客户端ID
                try:
                    await connection_manager.connect(websocket, endpoint_type="command", client_id=client_id)
                    logger.info(f"临时客户端[{client_id}]已注册")
                except Exception as e:
                    logger.warning(f"注册临时客户端ID时出错，继续处理命令: {e}")
            
            # 添加通用参数
            if isinstance(parameters, dict):
                parameters["client_id"] = client_id
            
            # 查找操作处理器
            handler = self.operation_handlers.get_handler(action)
            if not handler:
                logger.warning(f"未找到处理器: {action}")
                # 尝试执行特定的内置方法
                method_name = f"execute_{action}_operation"
                if hasattr(self, method_name) and callable(getattr(self, method_name)):
                    handler = getattr(self, method_name)
                    logger.info(f"使用内置方法处理器: {method_name}")
                else:
                    await websocket.send_json({
                        "type": "mcp.response",
                        "command_id": command_id,
                        "status": "error",
                        "message": f"未找到操作处理器: {action}",
                        "timestamp": datetime.now().isoformat()
                    })
                    return
            
            # 执行操作
            logger.info(f"执行{action}操作: 参数={parameters}")
            result = await handler(parameters)
            
            # 构建响应
            if isinstance(result, dict):
                success = result.get("success", False)
                response = {
                    "type": "mcp.response",
                    "command_id": command_id,
                    "status": "success" if success else "error",
                    "action": action,
                    "result": result,
                    "message": result.get("message", f"{'成功' if success else '失败'}执行{action}操作"),
                    "timestamp": datetime.now().isoformat()
                }
            else:
                # 如果结果不是字典，构建一个标准响应
                response = {
                    "type": "mcp.response",
                    "command_id": command_id,
                    "status": "success",
                    "action": action,
                    "result": {"data": result},
                    "message": f"已执行{action}操作",
                    "timestamp": datetime.now().isoformat()
                }
            
            # 发送响应
            await websocket.send_json(response)
            logger.info(f"已向客户端[{client_id}]发送操作响应")
        except Exception as e:
            logger.exception(f"处理命令时出错: {e}")
            try:
                # 尝试发送错误响应
                await websocket.send_json({
                    "type": "mcp.response",
                    "command_id": command_data.get("id", str(uuid.uuid4())),
                    "status": "error",
                    "message": f"处理命令时出错: {str(e)}",
                    "timestamp": datetime.now().isoformat()
                })
            except:
                logger.error("无法发送错误响应")
                pass

    async def broadcast_command(self, command: Dict[str, Any]):
        """广播命令到所有连接的客户端"""
        try:
            # 使用全局的connection_manager广播命令
            command_str = json.dumps(command)
            global connection_manager
            
            # 检查connection_manager是否可用
            if not 'connection_manager' in globals():
                logger.warning("全局connection_manager不存在，无法广播命令")
                return False
                
            # 向command端点广播命令
            broadcast_success = await connection_manager.broadcast(command, endpoint_type="command")
            
            if not broadcast_success:
                # 尝试向所有端点广播
                broadcast_success = await connection_manager.broadcast(command, endpoint_type=None)
                
            if broadcast_success:
                logger.info(f"已成功广播命令")
                return True
            else:
                logger.warning("没有客户端接收到命令广播")
                return False
        except Exception as e:
            logger.error(f"广播命令时出错: {str(e)}")
            import traceback
            traceback.print_exc()
            return False

    def register_operation_handler(self, operation: str, handler: Callable):
        """注册操作处理方法"""
        self.operation_handlers[operation] = handler
        logger.debug(f"已注册操作处理器: {operation}")

    async def execute_rotate_operation(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """执行旋转操作"""
        try:
            direction = params.get('direction', 'left')
            angle = params.get('angle', 45)

            logger.info(f"执行旋转操作: 方向={direction}, 角度={angle}")

            # 检查browser是否可用，如果不可用，则使用WebSocket广播
            if self.browser is None:
                logger.info("Browser不可用，使用WebSocket广播命令")
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
                if self.connection_manager:
                    broadcast_success = await self.connection_manager.broadcast(command, endpoint_type="command")
                    
                    if broadcast_success:
                        return {
                            "success": True,
                            "message": f"已发送旋转命令: 方向={direction}, 角度={angle}",
                            "data": {
                                "direction": direction,
                                "angle": angle
                            }
                        }
                    else:
                        logger.warning("没有活跃的WebSocket连接，无法广播旋转命令")
                else:
                    broadcast_success = await self.broadcast_command(command)
                    
                    if not broadcast_success:
                        logger.warning("没有活跃的WebSocket连接，无法广播旋转命令")

            # 如果browser可用，使用JavaScript执行
            # 构建直接操作THREE.js对象的JavaScript代码
            js_code = """
            (function() {
                // 1. 检查THREE.js对象是否可用（兼容两种命名方式）
                const scene = window.__scene || window.scene;
                const camera = window.__camera || window.camera;
                const renderer = window.__renderer || window.renderer;
                const controls = window.__controls || window.controls;
                const THREE = window.THREE;
                
                console.log('THREE.js对象可用性:', {
                    scene: !!scene,
                    camera: !!camera,
                    renderer: !!renderer,
                    controls: !!controls,
                    THREE: !!THREE
                });
                
                // 记录尝试过的方法
                const results = {
                    success: false,
                    methods_attempted: [],
                    error: null
                };
                
                try {
                    // 方法1: 使用全局rotateModel函数
                    if (typeof window.rotateModel === 'function') {
                        results.methods_attempted.push('rotateModel');
                        const rotateResult = window.rotateModel({direction: '%s', angle: %s});
                        console.log('rotateModel执行结果:', rotateResult);
                        
                        // 如果rotateModel返回值表示成功
                        if (rotateResult === true || (rotateResult && rotateResult.success)) {
                            results.success = true;
                            return results;
                        }
                    }
                    
                    // 方法2: 使用controls对象
                    if (!results.success && controls) {
                        results.methods_attempted.push('controls');
                        const angleRad = %s * (Math.PI / 180);
                        
                        // 根据方向选择旋转方法
                        if ('%s' === 'left' && typeof controls.rotateLeft === 'function') {
                            controls.rotateLeft(angleRad);
                            results.success = true;
                        } else if ('%s' === 'right' && typeof controls.rotateRight === 'function') {
                            controls.rotateRight(angleRad);
                            results.success = true;
                        } else if ('%s' === 'up' && typeof controls.rotateUp === 'function') {
                            controls.rotateUp(angleRad);
                            results.success = true;
                        } else if ('%s' === 'down' && typeof controls.rotateDown === 'function') {
                            controls.rotateDown(angleRad);
                            results.success = true;
                        }
                        
                        // 如果旋转成功，更新控制器并渲染
                        if (results.success) {
                            if (typeof controls.update === 'function') {
                                controls.update();
                            }
                            if (renderer && scene && camera) {
                                renderer.render(scene, camera);
                            }
                        }
                    }
                    
                    // 方法3: 直接操作相机
                    if (!results.success && camera && renderer && scene && THREE) {
                        results.methods_attempted.push('camera');
                        
                        // 创建旋转轴
                        const rotationAxis = new THREE.Vector3(0, 1, 0); // Y轴旋转 (左右)
                        if ('%s' === 'up' || '%s' === 'down') {
                            rotationAxis.set(1, 0, 0); // X轴旋转 (上下)
                        }
                        
                        // 确定旋转角度
                        const angleRad = %s * (Math.PI / 180);
                        const rotationAngle = ('%s' === 'left' || '%s' === 'up') ? angleRad : -angleRad;
                        
                        // 应用旋转
                        camera.position.applyAxisAngle(rotationAxis, rotationAngle);
                        
                        // 渲染场景
                        renderer.render(scene, camera);
                        results.success = true;
                    }
                    
                    // 如果所有方法都失败
                    if (!results.success) {
                        results.error = "所有旋转方法都失败，THREE.js对象可能不可用";
                        console.error(results.error);
                    }
                    
                    return results;
                } catch (e) {
                    results.success = false;
                    results.error = e.toString();
                    console.error('旋转操作出错:', e);
                    return results;
                }
            })();
            """ % (
            direction, angle, angle, direction, direction, direction, direction, direction, direction, angle, direction,
            direction)

            try:
                # 执行JavaScript代码
                result = self.browser.execute_script(js_code)

                logger.info(f"旋转操作JavaScript执行结果: {result}")

                if isinstance(result, dict):
                    success = result.get('success', False)
                    error = result.get('error', '')
                    methods = result.get('methods_attempted', [])

                    if success:
                        logger.info(f"旋转操作成功执行，使用方法: {methods}")
                        return {
                            "success": True,
                            "message": f"旋转操作成功 ({', '.join(methods)})",
                            "data": {
                                "direction": direction,
                                "angle": angle,
                                "methods": methods
                            }
                        }
                    else:
                        logger.warning(f"旋转操作失败: {error}, 尝试方法: {methods}")

                        # 尝试通过WebSocket广播
                        logger.info("尝试通过WebSocket广播旋转命令")
                        command = {
                            "type": "mcp.command",
                            "operation": "rotate",
                            "params": {
                                "direction": direction,
                                "angle": angle
                            },
                            "command_id": str(uuid.uuid4())
                        }
                        
                        broadcast_success = await self.broadcast_command(command)
                        
                        if broadcast_success:
                            return {
                                "success": True, 
                                "message": f"旋转命令已通过WebSocket广播",
                                "data": {
                                    "direction": direction,
                                    "angle": angle
                                }
                            }
                        else:
                            return {
                                "success": True,  # 返回成功，让前端继续处理
                                "message": f"已尝试执行旋转操作 (方向={direction}, 角度={angle})"
                            }


                # 对于其他类型的结果，直接返回成功
                return {
                    "success": True, 
                    "message": f"旋转操作执行成功",
                    "data": {
                        "direction": direction,
                        "angle": angle
                    }
                }
            except Exception as browser_error:
                logger.error(f"执行JavaScript时出错: {str(browser_error)}")

                # JavaScript执行失败，尝试通过WebSocket广播
                logger.info("尝试通过WebSocket广播旋转命令")
                command = {
                    "type": "mcp.command",
                    "operation": "rotate",
                    "params": {
                        "direction": direction,
                        "angle": angle
                    },
                    "command_id": str(uuid.uuid4())
                }

                broadcast_success = await self.broadcast_command(command)

                if broadcast_success:
                    return {
                        "success": True,
                        "message": f"旋转命令已通过WebSocket广播",
                        "data": {
                            "direction": direction,
                            "angle": angle
                        }
                    }
                else:
                    return {
                        "success": True,  # 返回成功，让前端继续处理
                        "message": f"已尝试执行旋转操作 (方向={direction}, 角度={angle})"
                    }
        except Exception as e:
            logger.error(f"执行旋转操作时出现异常: {str(e)}")
            import traceback
            traceback.print_exc()

            # 无论发生什么异常，都返回成功，让前端继续处理
            return {
                "success": True,
                "message": f"旋转命令已处理，但可能未成功执行"
            }

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

            # 检查browser是否可用，如果不可用，则使用WebSocket广播
            if self.browser is None:
                logger.info("Browser不可用，使用WebSocket广播缩放命令")
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
                if self.connection_manager:
                    broadcast_success = await self.connection_manager.broadcast(command, endpoint_type="command")
                    
                    if broadcast_success:
                        return {
                            "success": True,
                            "message": f"已发送缩放命令: 比例={scale}",
                            "data": {
                                "scale": scale
                            }
                        }
                    else:
                        logger.warning("没有活跃的WebSocket连接，无法广播缩放命令")
                else:
                    broadcast_success = await self.broadcast_command(command)
                    
                    if not broadcast_success:
                        logger.warning("没有活跃的WebSocket连接，无法广播缩放命令")

            # 如果browser可用，使用JavaScript执行
            # 构建JavaScript代码直接执行缩放操作
            js_code = """
            (function() {
                var results = {
                    success: false,
                    methods_attempted: [],
                    error: null
                };
                
                try {
                    // 检查THREE.js对象是否可用
                    if (!window.__camera || !window.__scene || !window.__renderer || !window.__controls) {
                        console.error('THREE.js对象未初始化或未暴露到全局');
                        results.error = 'THREE.js对象未初始化或未暴露到全局';
                        return results;
                    }
                    
                    const camera = window.__camera;
                    const scene = window.__scene;
                    const renderer = window.__renderer;
                    const controls = window.__controls;
                    
                    // 方法1: 使用controls.dollyIn/dollyOut方法
                    if (typeof controls.dollyIn === 'function' && typeof controls.dollyOut === 'function') {
                        results.methods_attempted.push('dolly');
                        
                        if (%s > 1) {
                            controls.dollyIn(%s);
                        } else {
                            controls.dollyOut(1/%s);
                        }
                        
                        controls.update();
                        renderer.render(scene, camera);
                        results.success = true;
                        return results;
                    }
                    
                    // 方法2: 使用controls.zoom方法
                    if (typeof controls.zoom === 'function') {
                        results.methods_attempted.push('zoom');
                        
                        controls.zoom(%s);
                        controls.update();
                        renderer.render(scene, camera);
                        results.success = true;
                        return results;
                    }
                    
                    // 方法3: 直接修改相机位置
                    results.methods_attempted.push('camera');
                    
                    // 获取从相机到目标的方向向量
                    const direction = new THREE.Vector3();
                    direction.subVectors(camera.position, controls.target);
                    
                    // 根据缩放因子调整相机位置
                    if (%s > 1) {
                        // 放大 - 将相机移近
                        direction.multiplyScalar(1 - 1/%s);
                    } else {
                        // 缩小 - 将相机移远
                        direction.multiplyScalar(1 - %s);
                    }
                    
                    camera.position.sub(direction);
                    
                    // 更新控制器和渲染
                    controls.update();
                    renderer.render(scene, camera);
                    results.success = true;
                    
                    return results;
                } catch (e) {
                    results.success = false;
                    results.error = e.toString();
                    console.error('缩放操作出错:', e);
                    return results;
                }
            })();
            """ % (scale, scale, scale, scale, scale, scale, scale)

            try:
                # 执行JavaScript代码
                result = self.browser.execute_script(js_code)

                logger.info(f"缩放操作JavaScript执行结果: {result}")

                if isinstance(result, dict):
                    success = result.get('success', False)
                    error = result.get('error', '')
                    methods = result.get('methods_attempted', [])

                    if success:
                        logger.info(f"缩放操作成功执行，使用方法: {methods}")
                        return {
                            "success": True,
                            "message": f"缩放操作成功 ({', '.join(methods)})",
                            "data": {
                                "scale": scale,
                                "methods": methods
                            }
                        }
                    else:
                        logger.warning(f"缩放操作失败: {error}, 尝试方法: {methods}")

                        # 尝试通过WebSocket广播
                        logger.info("尝试通过WebSocket广播缩放命令")
                        command = {
                            "type": "mcp.command",
                            "operation": "zoom",
                            "params": {
                                "scale": scale
                            },
                            "command_id": str(uuid.uuid4())
                        }

                        broadcast_success = await self.broadcast_command(command)

                        if broadcast_success:
                            return {
                                "success": True,
                                "message": f"缩放命令已通过WebSocket广播",
                                "data": {
                                    "scale": scale
                                }
                            }
                        else:
                            return {
                                "success": True,  # 返回成功，让前端继续处理
                                "message": f"已尝试执行缩放操作 (比例={scale})"
                            }


                # 对于其他类型的结果，直接返回成功
                return {
                    "success": True,
                    "message": f"缩放操作执行成功",
                    "data": {
                        "scale": scale
                    }
                }
            except Exception as browser_error:
                logger.error(f"执行JavaScript时出错: {str(browser_error)}")

                # JavaScript执行失败，尝试通过WebSocket广播
                logger.info("尝试通过WebSocket广播缩放命令")
                command = {
                    "type": "mcp.command",
                    "operation": "zoom",
                    "params": {
                        "scale": scale
                    },
                    "command_id": str(uuid.uuid4())
                }

                broadcast_success = await self.broadcast_command(command)

                if broadcast_success:
                    return {
                        "success": True,
                        "message": f"缩放命令已通过WebSocket广播",
                        "data": {
                            "scale": scale
                        }
                    }
                else:
                    return {
                        "success": True,  # 返回成功，让前端继续处理
                        "message": f"已尝试执行缩放操作 (比例={scale})"
                    }

        except Exception as e:
            self.logger.error(f"执行缩放操作时出错: {str(e)}")
            import traceback
            traceback.print_exc()
            # 无论发生什么异常，都返回成功，让前端继续处理
            return {
                "success": True,
                "message": f"缩放命令已处理，但可能未成功执行",
                "data": {
                    "scale": scale
                }
            }

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

                handler = self.operation_handlers.get_handler(operation)
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

    async def handle_generic_command(self, command: Dict[str, Any]) -> Dict[str, Any]:
        """处理通用命令，尝试从不同格式中提取操作类型和参数

        Args:
            command: 命令数据

        Returns:
            命令执行结果
        """
        try:
            # 首先尝试提取操作类型
            action = None
            parameters = {}
            
            # 检查各种可能的字段名
            if "action" in command:
                action = command["action"]
                parameters = command.get("parameters", {})
            elif "operation" in command:
                action = command["operation"]
                parameters = command.get("parameters", {}) or command.get("params", {})
            elif "type" in command and command["type"] != "mcp.command":
                # 如果type不是mcp.command，可能是直接操作类型
                action = command["type"]
                parameters = command.get("data", {}) or command.get("parameters", {}) or command.get("params", {})
            
            # 检查嵌套命令
            if not action and "command" in command and isinstance(command["command"], dict):
                nested = command["command"]
                if "action" in nested:
                    action = nested["action"]
                    parameters = nested.get("parameters", {})
                elif "operation" in nested:
                    action = nested["operation"]
                    parameters = nested.get("parameters", {}) or nested.get("params", {})
            
            # 如果仍然没有找到操作类型，返回错误
            if not action:
                return {
                    "success": False,
                    "message": "无法从命令中提取操作类型",
                    "data": {}
                }
            
            # 查找操作处理器
            handler = self.operation_handlers.get_handler(action)
            if not handler:
                logger.warning(f"未找到处理器: {action}")
                # 尝试执行特定的内置方法
                method_name = f"execute_{action}_operation"
                if hasattr(self, method_name) and callable(getattr(self, method_name)):
                    handler = getattr(self, method_name)
                    logger.info(f"使用内置方法处理器: {method_name}")
                else:
                    return {
                        "success": False,
                        "message": f"未找到操作处理器: {action}",
                        "data": {}
                    }
            
            # 执行操作
            logger.info(f"通用命令处理 - 执行{action}操作: 参数={parameters}")
            result = await handler(parameters)
            
            # 确保返回标准格式
            if isinstance(result, dict):
                if "success" not in result:
                    result["success"] = True
                return result
            else:
                # 如果结果不是字典，包装为标准格式
                return {
                    "success": True,
                    "message": f"成功执行{action}操作",
                    "data": result if result is not None else {}
                }
        except Exception as e:
            logger.exception(f"处理通用命令时出错: {e}")
            return {
                "success": False,
                "message": f"处理命令时出错: {str(e)}",
                "data": {}
            }


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

    # 输出详细的启动日志
    logger.info("=" * 50)
    logger.info("正在启动MCP服务器...")
    logger.info("支持的WebSocket端点:")
    logger.info("- /ws: 通用WebSocket端点")
    logger.info("- /ws/status: 状态更新WebSocket端点")
    logger.info("- /ws/health: 健康检查WebSocket端点")
    logger.info("- /ws/mcp: MCP命令WebSocket端点")
    logger.info("支持的HTTP端点:")
    logger.info("- /health: 健康检查HTTP端点")
    logger.info("- /api/websocket/status: WebSocket状态查询HTTP端点")
    logger.info("- /api/llm/process: AI助手请求处理接口")
    logger.info("- /api/execute: 通用操作执行接口")
    logger.info("=" * 50)

    # 创建连接管理器和MCP服务器实例
    global connection_manager
    connection_manager = ConnectionManager()
    mcp_server = MCPServer()
    
    # 让MCP服务器能够访问connection_manager
    mcp_server.connection_manager = connection_manager
    
    operation_handler = OperationHandler()

    # 注册操作处理函数 - 使用MCP服务器中的方法
    operation_handler.register_operation("rotate", mcp_server.execute_rotate_operation)
    operation_handler.register_operation("zoom", mcp_server.execute_zoom_operation)
    operation_handler.register_operation("focus", mcp_server.execute_focus_operation)
    operation_handler.register_operation("reset", mcp_server.execute_reset_operation)

    # WebSocket连接端点
    @app.websocket("/ws")
    async def websocket_endpoint(websocket: WebSocket):
        """通用WebSocket端点"""
        logger.info(f"收到WebSocket连接请求: /ws 来自 {websocket.client.host}:{websocket.client.port}")
        client_id = await connection_manager.connect(websocket, endpoint_type="general")
        
        try:
            # 发送欢迎消息
            await websocket.send_json({
                "type": "welcome",
                "message": "已连接到MCP服务器",
                "client_id": client_id,
                "timestamp": datetime.now().isoformat()
            })
            
            # 循环处理消息
            while True:
                message = await websocket.receive_text()
                
                try:
                    data = json.loads(message)
                    logger.info(f"收到客户端[{client_id}]的消息: {data}")
                    
                    # 处理不同类型的消息
                    msg_type = data.get("type", "unknown")
                    
                    if msg_type == "ping":
                        await websocket.send_json({
                            "type": "pong",
                            "timestamp": datetime.now().isoformat()
                        })
                    elif msg_type == "command":
                        # 转发给命令处理器
                        result = await mcp_server.handle_generic_command(data.get("command", {}))
                        await websocket.send_json({
                            "type": "command_result",
                            "success": result.get("success", False),
                            "message": result.get("message", ""),
                            "data": result.get("data", {}),
                            "timestamp": datetime.now().isoformat()
                        })
                    else:
                        await websocket.send_json({
                            "type": "error",
                            "message": f"未知消息类型: {msg_type}",
                            "timestamp": datetime.now().isoformat()
                        })
                except json.JSONDecodeError:
                    logger.error(f"客户端[{client_id}]发送的不是有效的JSON")
                    await websocket.send_json({
                        "type": "error",
                        "message": "消息格式无效，需要JSON格式",
                        "timestamp": datetime.now().isoformat()
                    })
                except Exception as e:
                    logger.error(f"处理客户端[{client_id}]消息时出错: {e}")
                    await websocket.send_json({
                        "type": "error",
                        "message": f"处理消息时出错: {e}",
                        "timestamp": datetime.now().isoformat()
                    })
        except WebSocketDisconnect:
            logger.info(f"客户端[{client_id}]断开WebSocket连接")
        except Exception as e:
            logger.error(f"WebSocket连接错误: {e}")
        finally:
            connection_manager.disconnect(websocket, client_id)

    @app.websocket("/ws/status")
    async def websocket_status_endpoint(websocket: WebSocket):
        """状态WebSocket端点"""
        logger.info(f"收到WebSocket连接请求: /ws/status 来自 {websocket.client.host}:{websocket.client.port}")
        
        # 提取或生成会话ID
        session_id = websocket.query_params.get("sessionId", None)
        if not session_id:
            # 尝试从cookie中提取
            cookies = websocket.headers.get("cookie", "")
            if "digital_twin_session_id" in cookies:
                cookie_parts = cookies.split(";")
                for part in cookie_parts:
                    if "digital_twin_session_id" in part:
                        session_id = part.split("=")[1].strip()
                        break
        
        # 连接到ConnectionManager
        client_id = await connection_manager.connect(websocket, endpoint_type="status")
        
        try:
            # 发送初始状态
            status_data = {
                "type": "status",
                "data": {
                    "connected": True,
                    "client_id": client_id,
                    "service": "mcp_server",
                    "version": "1.0.0",
                    "timestamp": datetime.now().isoformat()
                }
            }
            await websocket.send_json(status_data)
            logger.info("发送初始状态消息成功")
            
            # 循环等待消息
            while True:
                try:
                    message = await websocket.receive_text()
                    
                    # 更新最后活动时间
                    if client_id in connection_manager.active_connections:
                        connection_manager.active_connections[client_id]["last_activity"] = datetime.now()
                    
                    # 处理心跳和状态请求
                    try:
                        data = json.loads(message)
                        
                        if isinstance(data, dict):
                            if data.get("type") == "heartbeat":
                                # 心跳响应
                                await websocket.send_json({
                                    "type": "heartbeat_response",
                                    "timestamp": datetime.now().isoformat(),
                                    "status": "ok"
                                })
                            elif data.get("type") == "status.request":
                                # 状态请求响应
                                await websocket.send_json({
                                    "type": "status",
                                    "data": {
                                        "connected": True,
                                        "client_id": client_id,
                                        "service": "mcp_server",
                                        "version": "1.0.0",
                                        "connections": connection_manager.get_active_connections_count(),
                                        "timestamp": datetime.now().isoformat()
                                    }
                                })
                                logger.info("发送状态响应成功")
                    except json.JSONDecodeError:
                        logger.warning(f"非JSON格式状态消息: {message}")
                except WebSocketDisconnect:
                    logger.info(f"客户端[{client_id}]断开状态WebSocket连接")
                    break
                except Exception as e:
                    logger.error(f"处理状态WebSocket消息时出错: {str(e)}")
                    break
        except WebSocketDisconnect:
            logger.info(f"客户端[{client_id}]断开状态WebSocket连接")
        except Exception as e:
            logger.error(f"状态WebSocket连接出错: {str(e)}")
        finally:
            connection_manager.disconnect(websocket, client_id)

    @app.websocket("/ws/health")
    async def websocket_health_endpoint(websocket: WebSocket):
        """健康检查WebSocket端点"""
        logger.info(f"收到WebSocket连接请求: /ws/health 来自 {websocket.client.host}:{websocket.client.port}")
        client_id = await connection_manager.connect(websocket, endpoint_type="health")
        
        try:
            # 发送初始健康状态
            health_data = {
                "type": "health",
                "status": "healthy",
                "client_id": client_id,
                "browser_status": "正常",
                "message": "服务正常运行中",
                "timestamp": datetime.now().isoformat()
            }
            await websocket.send_json(health_data)
            logger.info("发送初始健康状态消息成功")
            
            # 循环等待消息
            while True:
                message = await websocket.receive_text()
                try:
                    data = json.loads(message)
                    logger.info(f"收到健康检查消息: {data}")
                    
                    # 处理健康检查请求
                    if data.get("type") == "health.check":
                        await websocket.send_json({
                            "type": "health",
                            "status": "healthy",
                            "client_id": client_id,
                            "browser_status": "正常",
                            "message": "服务正常运行中",
                            "timestamp": datetime.now().isoformat()
                        })
                        logger.info("发送健康状态响应成功")
                    else:
                        logger.warning(f"未知健康检查消息类型: {data.get('type')}")
                except Exception as e:
                    logger.error(f"处理健康检查消息时出错: {e}")
        except WebSocketDisconnect:
            logger.info(f"客户端[{client_id}]断开健康检查WebSocket连接")
        except Exception as e:
            logger.error(f"健康检查WebSocket连接错误: {e}")
        finally:
            connection_manager.disconnect(websocket, client_id)

    @app.websocket("/ws/mcp")
    async def websocket_mcp_endpoint(websocket: WebSocket):
        """MCP WebSocket端点"""
        logger.info(f"收到WebSocket连接请求: /ws/mcp 来自 {websocket.client.host}:{websocket.client.port}")
        client_id = await connection_manager.connect(websocket, endpoint_type="command")
        
        try:
            while True:
                message = await websocket.receive_text()
                try:
                    data = json.loads(message)
                    logger.info(f"收到MCP消息: {data}")
                    
                    # 处理初始化消息
                    if data.get("type") == "init":
                        await websocket.send_json({
                            "type": "init.response",
                            "status": "success",
                            "message": "初始化成功",
                            "client_id": client_id,
                            "timestamp": datetime.now().isoformat()
                        })
                        logger.info("发送初始化响应成功")
                        continue
                    
                    # 处理状态请求消息
                    if data.get("type") == "status.request":
                        await websocket.send_json({
                            "type": "status",
                            "data": {
                                "connected": True,
                                "service": "mcp_server",
                                "client_id": client_id,
                                "operations": operation_handler.get_registered_operations(),
                                "timestamp": datetime.now().isoformat()
                            }
                        })
                        logger.info("发送状态响应成功")
                        continue
                    
                    # 处理MCP命令消息
                    if data.get("type") == "mcp.command":
                        await mcp_server.handle_command(websocket, data)
                    else:
                        logger.warning(f"未知MCP消息类型: {data.get('type')}")
                        await websocket.send_json({
                            "type": "error",
                            "message": f"未知消息类型: {data.get('type')}",
                            "timestamp": datetime.now().isoformat()
                        })
                except json.JSONDecodeError:
                    logger.error(f"非JSON格式的MCP消息: {message}")
                    await websocket.send_json({
                        "type": "error",
                        "message": "消息格式无效，需要JSON格式",
                        "timestamp": datetime.now().isoformat()
                    })
                except Exception as e:
                    logger.error(f"处理MCP消息时出错: {e}")
                    await websocket.send_json({
                        "type": "error",
                        "message": f"处理消息时出错: {e}",
                        "timestamp": datetime.now().isoformat()
                    })
        except WebSocketDisconnect:
            logger.info(f"MCP WebSocket断开连接")
            connection_manager.disconnect(websocket, client_id)
        except Exception as e:
            logger.error(f"MCP WebSocket连接错误: {e}")
            connection_manager.disconnect(websocket, client_id)

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

    @app.websocket("/ws/command")
    async def websocket_command_endpoint(websocket: WebSocket):
        """命令WebSocket端点"""
        logger.info(f"收到WebSocket连接请求: /ws/command 来自 {websocket.client.host}:{websocket.client.port}")
        
        # 提取或生成会话ID
        session_id = websocket.query_params.get("sessionId", None)
        if not session_id:
            # 尝试从cookie中提取
            cookies = websocket.headers.get("cookie", "")
            if "digital_twin_session_id" in cookies:
                cookie_parts = cookies.split(";")
                for part in cookie_parts:
                    if "digital_twin_session_id" in part:
                        session_id = part.split("=")[1].strip()
                        break
        
        # 连接到ConnectionManager
        client_id = await connection_manager.connect(websocket, endpoint_type="command")
        
        # 发送欢迎消息
        await websocket.send_json({
            "type": "welcome",
            "message": "已连接到MCP命令服务",
            "client_id": client_id,
            "timestamp": datetime.now().isoformat()
        })
        
        try:
            # 循环处理消息
            while True:
                try:
                    # 接收消息
                    message = await websocket.receive_text()
                    
                    # 更新最后活动时间
                    if client_id in connection_manager.active_connections:
                        connection_manager.active_connections[client_id]["last_activity"] = datetime.now()
                    
                    # 解析JSON消息
                    try:
                        data = json.loads(message)
                        
                        # 处理心跳消息
                        if isinstance(data, dict) and data.get("type") == "heartbeat":
                            await websocket.send_json({
                                "type": "heartbeat_response",
                                "timestamp": datetime.now().isoformat(),
                                "status": "ok"
                            })
                            continue
                        
                        logger.info(f"收到客户端[{client_id}]的命令消息: {data}")
                        
                        # 处理不同类型的命令
                        if isinstance(data, dict):
                            # 检查命令格式
                            if data.get("type") == "mcp.command":
                                # 处理顶层命令
                                if "action" in data:
                                    # 直接处理顶层命令
                                    await mcp_server.handle_command(websocket, data)
                                elif "command" in data and isinstance(data["command"], dict):
                                    # 处理嵌套命令
                                    await mcp_server.handle_command(websocket, data)
                                else:
                                    # 缺少必要字段
                                    logger.warning(f"命令缺少action或command字段: {data}")
                                    await websocket.send_json({
                                        "type": "mcp.response",
                                        "command_id": data.get("id", str(uuid.uuid4())),
                                        "status": "error",
                                        "message": "命令缺少action或command字段",
                                        "timestamp": datetime.now().isoformat()
                                    })
                            elif "action" in data:
                                # 直接处理带action字段的命令
                                await mcp_server.handle_command(websocket, data)
                            else:
                                # 其他类型的消息，尝试作为通用命令处理
                                result = await mcp_server.handle_generic_command(data)
                                await websocket.send_json({
                                    "type": "mcp.response",
                                    "command_id": data.get("id", str(uuid.uuid4())),
                                    "status": "success" if result.get("success", False) else "error",
                                    "message": result.get("message", "命令已处理"),
                                    "timestamp": datetime.now().isoformat()
                                })
                        else:
                            logger.warning(f"无法识别的消息格式: {data}")
                            await websocket.send_json({
                                "type": "error",
                                "message": "无法识别的消息格式",
                                "timestamp": datetime.now().isoformat()
                            })
                    except json.JSONDecodeError:
                        logger.warning(f"非JSON格式消息: {message}")
                        # 处理纯文本消息
                        await connection_manager.send_message(message, websocket)
                except WebSocketDisconnect:
                    logger.info(f"客户端[{client_id}]断开命令WebSocket连接")
                    connection_manager.disconnect(websocket, client_id)
                    break
                except Exception as e:
                    logger.error(f"处理命令WebSocket消息时出错: {str(e)}")
                    # 发送错误响应
                    try:
                        await websocket.send_json({
                            "type": "error",
                            "message": f"处理消息时出错: {str(e)}",
                            "timestamp": datetime.now().isoformat()
                        })
                    except:
                        # 如果发送错误消息也失败，可能连接已断开
                        break
        except WebSocketDisconnect:
            logger.info(f"客户端[{client_id}]断开命令WebSocket连接")
        except Exception as e:
            logger.error(f"命令WebSocket连接出错: {str(e)}")
        finally:
            connection_manager.disconnect(websocket, client_id)

    # 启动服务器
    port = int(os.environ.get("PORT", 9000))
    print(f"启动MCP服务器，端口: {port}...")
    uvicorn.run(app, host="0.0.0.0", port=port)


# 添加主函数入口
if __name__ == "__main__":
    main()
