#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
MCP服务器实现
(MCP Server Implementation)

实现标准的MCP（Model Control Protocol）协议，提供更灵活的模型操作控制。
"""

import json
import logging
import asyncio
import os
import time
import traceback
import subprocess
import shlex
from typing import Dict, List, Any, Optional, Union, Callable
from enum import Enum
from datetime import datetime
import uuid

from fastapi import WebSocket, WebSocketDisconnect
from playwright.async_api import Page

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
        self.action = action
        self.parameters = parameters or {}
        self.target = target
        self.id = command_id or str(uuid.uuid4())
        self.timestamp = datetime.now().isoformat()
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            "id": self.id,
            "action": self.action,
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
    
    @classmethod
    def custom(cls, action: str, parameters: Dict[str, Any], target: str = None) -> 'MCPCommand':
        """创建自定义命令"""
        return cls(
            action=action,
            parameters=parameters,
            target=target
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

# MCP服务器配置
class MCPServerConfig:
    """MCP服务器配置"""
    def __init__(self, server_id: str, config: Dict[str, Any]):
        self.server_id = server_id
        self.command = config.get("command", "")
        self.args = config.get("args", [])
        self.env = config.get("env", {})
        self.cwd = config.get("cwd")
        self.max_retries = config.get("maxRetries", 3)
        self.timeout = config.get("timeout", 10)  # 超时时间（秒）

# MCP服务器实现
class MCPServer:
    """MCP服务器实现"""
    def __init__(self):
        self.servers: Dict[str, MCPServerConfig] = {}
        self.command_handlers: Dict[str, Callable] = {}
        self.active_connections: List[WebSocket] = []
        self.page: Optional[Page] = None
        self.command_results: Dict[str, asyncio.Future] = {}
        
        # 注册内置命令处理器
        self.register_command_handler(MCPOperationType.ROTATE, self._handle_rotate)
        self.register_command_handler(MCPOperationType.ZOOM, self._handle_zoom)
        self.register_command_handler(MCPOperationType.FOCUS, self._handle_focus)
        self.register_command_handler(MCPOperationType.RESET, self._handle_reset)
    
    def set_page(self, page: Page):
        """设置Playwright页面实例"""
        self.page = page
    
    def register_server(self, server_id: str, config: Dict[str, Any]):
        """注册MCP服务器"""
        self.servers[server_id] = MCPServerConfig(server_id, config)
        logger.info(f"注册MCP服务器: {server_id}")
    
    def register_command_handler(self, action_type: str, handler: Callable):
        """注册命令处理器"""
        self.command_handlers[action_type] = handler
        logger.debug(f"注册命令处理器: {action_type}")
    
    async def connect(self, websocket: WebSocket):
        """处理WebSocket连接"""
        await websocket.accept()
        self.active_connections.append(websocket)
        logger.info(f"WebSocket客户端已连接，当前连接数: {len(self.active_connections)}")
    
    def disconnect(self, websocket: WebSocket):
        """处理WebSocket断开连接"""
        if websocket in self.active_connections:
            self.active_connections.remove(websocket)
            logger.info(f"WebSocket客户端已断开，当前连接数: {len(self.active_connections)}")
    
    async def broadcast(self, message: Dict[str, Any]):
        """广播消息到所有连接的客户端"""
        if not self.active_connections:
            return
        
        disconnected = []
        message_json = json.dumps(message)
        
        for websocket in self.active_connections:
            try:
                await websocket.send_text(message_json)
            except Exception as e:
                logger.error(f"发送WebSocket消息失败: {e}")
                disconnected.append(websocket)
        
        # 移除断开的连接
        for websocket in disconnected:
            self.disconnect(websocket)
    
    async def broadcast_result(self, result: MCPCommandResult):
        """广播命令执行结果"""
        await self.broadcast({
            "type": "commandResult",
            "result": result.to_dict()
        })
    
    def generate_mcp_command(self, action: str, parameters: Dict[str, Any], server_id: str = "threejs-control") -> Dict[str, Any]:
        """生成标准MCP命令"""
        if server_id not in self.servers:
            raise ValueError(f"未找到服务器配置: {server_id}")
        
        server_config = self.servers[server_id]
        
        # 替换命令参数中的变量
        args = []
        for arg in server_config.args:
            if "${action}" in arg:
                arg = arg.replace("${action}", action)
            elif "${JSON.stringify(params)}" in arg:
                arg = arg.replace("${JSON.stringify(params)}", json.dumps(parameters))
            args.append(arg)
        
        return {
            "mcpServers": {
                server_id: {
                    "command": server_config.command,
                    "args": args,
                    "env": server_config.env
                }
            }
        }
    
    async def execute_command(self, command: MCPCommand) -> MCPCommandResult:
        """执行MCP命令"""
        logger.info(f"执行MCP命令: {command.to_dict()}")
        
        try:
            # 检查命令处理器
            if command.action in self.command_handlers:
                # 使用内置处理器
                result = await self.command_handlers[command.action](command)
                command_result = MCPCommandResult(
                    command_id=command.id,
                    success=result.get("success", False),
                    data=result.get("data"),
                    error=result.get("error")
                )
            else:
                # 使用外部MCP服务
                command_result = await self._execute_external_command(command)
            
            # 广播结果
            await self.broadcast_result(command_result)
            
            return command_result
        except Exception as e:
            logger.error(f"执行命令失败: {e}")
            logger.debug(traceback.format_exc())
            
            command_result = MCPCommandResult(
                command_id=command.id,
                success=False,
                error=str(e)
            )
            
            await self.broadcast_result(command_result)
            
            return command_result
    
    async def _execute_external_command(self, command: MCPCommand) -> MCPCommandResult:
        """执行外部MCP命令"""
        server_id = "threejs-control"  # 默认服务器ID
        
        if server_id not in self.servers:
            raise ValueError(f"未找到服务器配置: {server_id}")
        
        server_config = self.servers[server_id]
        
        # 生成MCP命令
        mcp_command = self.generate_mcp_command(
            action=command.action,
            parameters=command.parameters,
            server_id=server_id
        )
        
        logger.debug(f"生成MCP命令: {mcp_command}")
        
        # 创建Future对象用于等待命令执行结果
        future = asyncio.Future()
        self.command_results[command.id] = future
        
        try:
            # 执行命令
            process = await asyncio.create_subprocess_exec(
                server_config.command,
                *server_config.args,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                env={**os.environ, **server_config.env},
                cwd=server_config.cwd
            )
            
            # 等待进程执行完成
            stdout, stderr = await asyncio.wait_for(
                process.communicate(),
                timeout=server_config.timeout
            )
            
            if process.returncode != 0:
                logger.error(f"命令执行失败: {stderr.decode()}")
                return MCPCommandResult(
                    command_id=command.id,
                    success=False,
                    error=f"命令返回错误: {stderr.decode()}"
                )
            
            # 解析输出
            try:
                output = stdout.decode().strip()
                result = json.loads(output)
                
                return MCPCommandResult(
                    command_id=command.id,
                    success=True,
                    data=result
                )
            except json.JSONDecodeError:
                return MCPCommandResult(
                    command_id=command.id,
                    success=True,
                    data={"output": output}
                )
        except asyncio.TimeoutError:
            logger.error(f"命令执行超时: {command.id}")
            return MCPCommandResult(
                command_id=command.id,
                success=False,
                error="命令执行超时"
            )
        except Exception as e:
            logger.error(f"执行外部命令失败: {e}")
            return MCPCommandResult(
                command_id=command.id,
                success=False,
                error=str(e)
            )
        finally:
            # 清理Future对象
            if command.id in self.command_results:
                del self.command_results[command.id]
    
    async def _handle_rotate(self, command: MCPCommand) -> Dict[str, Any]:
        """处理旋转命令"""
        if not self.page:
            return {"success": False, "error": "页面未初始化"}
        
        parameters = command.parameters
        direction = parameters.get("direction", "left")
        angle = parameters.get("angle", 45)
        target = command.target
        
        try:
            # 使用page.evaluate执行前端JavaScript代码
            result = await self.page.evaluate("""({ direction, angle, target }) => {
                console.log(`正在执行旋转操作: 方向=${direction}, 角度=${angle}, 目标=${target}`);
                
                try {
                    // 方法1: 使用window.rotateModel
                    if (typeof window.rotateModel === 'function') {
                        return window.rotateModel({ direction, angle, target });
                    }
                    
                    // 方法2: 使用window.app对象
                    if (window.app && typeof window.app.rotateComponent === 'function') {
                        const result = window.app.rotateComponent(target, angle, direction);
                        return result.success;
                    }
                    
                    // 方法3: 直接操作OrbitControls
                    if (window.__orbitControls) {
                        const rotateAmount = (direction === 'left' ? 1 : -1) * (angle * Math.PI / 180);
                        window.__orbitControls.rotateLeft(rotateAmount);
                        window.__orbitControls.update();
                        return true;
                    }
                    
                    console.error('找不到可用的旋转方法');
                    return false;
                } catch (error) {
                    console.error('执行旋转操作出错:', error);
                    return false;
                }
            }""", {"direction": direction, "angle": angle, "target": target})
            
            success = bool(result)
            
            return {
                "success": success,
                "data": {
                    "executed": True,
                    "action": "rotate",
                    "parameters": {
                        "direction": direction,
                        "angle": angle,
                        "target": target
                    },
                    "original_return": result
                }
            }
        except Exception as e:
            logger.error(f"执行旋转操作时出错: {str(e)}")
            logger.debug(traceback.format_exc())
            return {"success": False, "error": str(e)}
    
    async def _handle_zoom(self, command: MCPCommand) -> Dict[str, Any]:
        """处理缩放命令"""
        if not self.page:
            return {"success": False, "error": "页面未初始化"}
        
        parameters = command.parameters
        scale = parameters.get("scale", 1.5)
        target = command.target
        
        try:
            # 使用page.evaluate执行前端JavaScript代码
            result = await self.page.evaluate("""({ scale, target }) => {
                console.log(`正在执行缩放操作: 比例=${scale}, 目标=${target}`);
                
                try {
                    // 方法1: 使用window.zoomModel
                    if (typeof window.zoomModel === 'function') {
                        return window.zoomModel({ scale, target });
                    }
                    
                    // 方法2: 使用window.app对象
                    if (window.app && typeof window.app.zoomComponent === 'function') {
                        const result = window.app.zoomComponent(target, scale);
                        return result.success;
                    }
                    
                    // 方法3: 直接操作OrbitControls
                    if (window.__orbitControls) {
                        window.__orbitControls.dollyIn(scale);
                        window.__orbitControls.update();
                        return true;
                    }
                    
                    console.error('找不到可用的缩放方法');
                    return false;
                } catch (error) {
                    console.error('执行缩放操作出错:', error);
                    return false;
                }
            }""", {"scale": scale, "target": target})
            
            success = bool(result)
            
            return {
                "success": success,
                "data": {
                    "executed": True,
                    "action": "zoom",
                    "parameters": {
                        "scale": scale,
                        "target": target
                    },
                    "original_return": result
                }
            }
        except Exception as e:
            logger.error(f"执行缩放操作时出错: {str(e)}")
            logger.debug(traceback.format_exc())
            return {"success": False, "error": str(e)}
    
    async def _handle_focus(self, command: MCPCommand) -> Dict[str, Any]:
        """处理聚焦命令"""
        if not self.page:
            return {"success": False, "error": "页面未初始化"}
        
        target = command.target or "center"
        
        try:
            # 使用page.evaluate执行前端JavaScript代码
            result = await self.page.evaluate("""({ target }) => {
                console.log(`正在执行聚焦操作: 目标=${target}`);
                
                try {
                    // 方法1: 使用window.focusOnModel
                    if (typeof window.focusOnModel === 'function') {
                        return window.focusOnModel({ target });
                    }
                    
                    // 方法2: 使用window.app对象
                    if (window.app && typeof window.app.focusOnComponent === 'function') {
                        const result = window.app.focusOnComponent(target);
                        return result.success;
                    }
                    
                    console.error('找不到可用的聚焦方法');
                    return false;
                } catch (error) {
                    console.error('执行聚焦操作出错:', error);
                    return false;
                }
            }""", {"target": target})
            
            success = bool(result)
            
            return {
                "success": success,
                "data": {
                    "executed": True,
                    "action": "focus",
                    "parameters": {
                        "target": target
                    },
                    "original_return": result
                }
            }
        except Exception as e:
            logger.error(f"执行聚焦操作时出错: {str(e)}")
            logger.debug(traceback.format_exc())
            return {"success": False, "error": str(e)}
    
    async def _handle_reset(self, command: MCPCommand) -> Dict[str, Any]:
        """处理重置命令"""
        if not self.page:
            return {"success": False, "error": "页面未初始化"}
        
        try:
            # 使用page.evaluate执行前端JavaScript代码
            result = await self.page.evaluate("""() => {
                console.log('正在执行重置操作');
                
                try {
                    // 方法1: 使用window.resetModel
                    if (typeof window.resetModel === 'function') {
                        return window.resetModel();
                    }
                    
                    // 方法2: 使用window.app对象
                    if (window.app && typeof window.app.resetModel === 'function') {
                        return window.app.resetModel();
                    }
                    
                    // 方法3: 直接操作OrbitControls
                    if (window.__orbitControls) {
                        window.__orbitControls.reset();
                        return true;
                    }
                    
                    console.error('找不到可用的重置方法');
                    return false;
                } catch (error) {
                    console.error('执行重置操作出错:', error);
                    return false;
                }
            }""")
            
            success = bool(result)
            
            return {
                "success": success,
                "data": {
                    "executed": True,
                    "action": "reset",
                    "original_return": result
                }
            }
        except Exception as e:
            logger.error(f"执行重置操作时出错: {str(e)}")
            logger.debug(traceback.format_exc())
            return {"success": False, "error": str(e)}

# 创建MCP服务器实例
mcp_server = MCPServer()

# 注册默认的ThreeJS控制服务器
mcp_server.register_server("threejs-control", {
    "command": "node",
    "args": [
        "mcp-adapter.js", 
        "--action=${action}", 
        "--params=${JSON.stringify(params)}"
    ],
    "env": {
        "THREEJS_SCENE_ID": "scene_001"
    }
})

# 从自然语言生成MCP命令
async def generate_mcp_command_from_nl(message: str) -> Optional[MCPCommand]:
    """从自然语言生成MCP命令"""
    # 简单的规则匹配（实际应用中可以使用更复杂的NLP模型）
    message = message.lower()
    
    # 旋转命令
    if "旋转" in message or "rotate" in message:
        direction = "left"
        angle = 45
        
        # 检测方向
        if "左" in message or "left" in message:
            direction = "left"
        elif "右" in message or "right" in message:
            direction = "right"
        
        # 检测角度
        import re
        angle_match = re.search(r'(\d+)\s*度', message)
        if angle_match:
            angle = int(angle_match.group(1))
        
        return MCPCommand.rotate(direction, angle)
    
    # 缩放命令
    elif "缩放" in message or "放大" in message or "缩小" in message or "zoom" in message:
        scale = 1.5
        
        # 检测缩放比例
        if "缩小" in message:
            scale = 0.8
        
        # 尝试提取精确的比例值
        import re
        scale_match = re.search(r'(\d+(?:\.\d+)?)\s*倍', message)
        if scale_match:
            scale = float(scale_match.group(1))
        
        return MCPCommand.zoom(scale)
    
    # 聚焦命令
    elif "聚焦" in message or "关注" in message or "focus" in message:
        target = "center"
        
        # 尝试提取目标
        if "区域" in message or "area" in message:
            import re
            area_match = re.search(r'区域\s*(\d+)', message)
            if area_match:
                target = f"Area_{area_match.group(1)}"
        elif "会议室" in message or "meeting" in message:
            target = "meeting_room"
        
        return MCPCommand.focus(target)
    
    # 重置命令
    elif "重置" in message or "复位" in message or "reset" in message:
        return MCPCommand.reset()
    
    # 无法识别的命令
    return None 