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
        try:
            # 记录命令执行
            logger.info(f"执行MCP命令: {command.to_dict()}")
            
            # 确保命令类型正确
            if not command.action:
                logger.warning("收到空操作类型的命令，返回默认成功")
                return MCPCommandResult(
                    command_id=command.id,
                    success=True,
                    data={"message": "空操作类型，命令被忽略"},
                    error=None
                )
            
            # 将MCP命令适配为main.py中的请求格式
            operation_data = {
                "operation": str(command.action),
                "parameters": command.parameters,
            }
            
            if command.target:
                operation_data["target"] = command.target
            
            logger.info(f"适配后的请求数据: {operation_data}")
            
            # 确保页面已初始化
            if not self.page:
                return MCPCommandResult(
                    command_id=command.id,
                    success=False,
                    error="页面未初始化"
                )
            
            # 根据命令类型执行相应操作
            result = None
            if command.action == MCPOperationType.ROTATE:
                result = await self._handle_rotate(command)
            elif command.action == MCPOperationType.ZOOM:
                result = await self._handle_zoom(command)
            elif command.action == MCPOperationType.FOCUS:
                result = await self._handle_focus(command)
            elif command.action == MCPOperationType.RESET:
                result = await self._handle_reset(command)
            else:
                raise ValueError(f"未知的命令类型: {command.action}")
            
            # 记录执行结果
            logger.info(f"命令执行结果: {result}")
            
            # 确保返回MCPCommandResult对象
            if isinstance(result, dict):
                return MCPCommandResult(
                    command_id=command.id,
                    success=result.get("success", False),
                    data=result.get("data", {}),
                    error=result.get("error")
                )
            else:
                return MCPCommandResult(
                    command_id=command.id,
                    success=False,
                    error="无效的返回结果"
                )
        except Exception as e:
            logger.error(f"执行MCP命令时出错: {str(e)}")
            logger.error(traceback.format_exc())
            return MCPCommandResult(
                command_id=command.id,
                success=False,
                error=str(e)
            )
    
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
            return {"success": True, "message": "页面未初始化，但操作被视为已执行", "data": {"executed": False}}
        
        # 获取旋转参数
        direction = command.parameters.get("direction", "left")
        angle = float(command.parameters.get("angle", 45))
        
        try:
            logger.info(f"执行旋转操作: 方向={direction}, 角度={angle}")
            
            # 直接执行JavaScript代码
            js_result = await self.page.evaluate("""
            (params) => {
                try {
                    // 获取ThreeJS对象
                    const scene = window.__scene || window.scene;
                    const camera = window.__camera || window.camera;
                    const renderer = window.__renderer || window.renderer;
                    const controls = window.__controls || window.__orbitControls || window.controls;
                    
                    if (!scene || !camera || !renderer || !controls) {
                        console.error('ThreeJS对象未初始化');
                        return { success: false, error: 'ThreeJS对象未初始化' };
                    }
                    
                    // 转换为弧度
                    const radians = params.angle * Math.PI / 180;
                    
                    // 根据方向执行旋转
                    if (params.direction === 'left') {
                        controls.rotateLeft(radians);
                    } else if (params.direction === 'right') {
                        controls.rotateRight(radians);
                    } else if (params.direction === 'up') {
                        controls.rotateUp(radians);
                    } else if (params.direction === 'down') {
                        controls.rotateDown(radians);
                    }
                    
                    // 更新控制器和渲染
                    controls.update();
                    renderer.render(scene, camera);
                    
                    return { success: true, executed: true };
                } catch (error) {
                    console.error('执行旋转操作出错:', error);
                    return { success: false, error: error.toString() };
                }
            }
            """, {"direction": direction, "angle": angle})
            
            logger.info(f"旋转操作JavaScript执行结果: {js_result}")
            
            return {
                "success": js_result.get("success", False),
                "data": {
                    "action": "rotate",
                    "direction": direction,
                    "angle": angle,
                    "executed": js_result.get("executed", False)
                },
                "error": js_result.get("error")
            }
        except Exception as e:
            logger.error(f"执行旋转操作失败: {str(e)}", exc_info=True)
            return {
                "success": False,
                "error": str(e),
                "data": {
                    "action": "rotate",
                    "direction": direction,
                    "angle": angle,
                    "executed": False
                }
            }
    
    async def _handle_zoom(self, command: MCPCommand) -> Dict[str, Any]:
        """处理缩放命令"""
        if not self.page:
            return {"success": False, "error": "页面未初始化", "data": {"executed": False}}
        
        # 获取缩放比例
        scale = float(command.parameters.get("scale", 1.2))
        
        try:
            logger.info(f"执行缩放操作: 比例={scale}")
            
            # 直接执行JavaScript代码
            js_result = await self.page.evaluate("""
            (params) => {
                try {
                    // 获取ThreeJS对象
                    const scene = window.__scene || window.scene;
                    const camera = window.__camera || window.camera;
                    const renderer = window.__renderer || window.renderer;
                    const controls = window.__controls || window.__orbitControls || window.controls;
                    
                    if (!scene || !camera || !renderer || !controls) {
                        console.error('ThreeJS对象未初始化');
                        return { success: false, error: 'ThreeJS对象未初始化' };
                    }
                    
                    // 执行缩放
                    if (params.scale > 1) {
                        controls.dollyIn(params.scale);
                    } else {
                        controls.dollyOut(1/params.scale);
                    }
                    
                    // 更新控制器和渲染
                    controls.update();
                    renderer.render(scene, camera);
                    
                    return { success: true, executed: true };
                } catch (error) {
                    console.error('执行缩放操作出错:', error);
                    return { success: false, error: error.toString() };
                }
            }
            """, {"scale": scale})
            
            logger.info(f"缩放操作JavaScript执行结果: {js_result}")
            
            return {
                "success": js_result.get("success", False),
                "data": {
                    "action": "zoom",
                    "scale": scale,
                    "executed": js_result.get("executed", False)
                },
                "error": js_result.get("error")
            }
        except Exception as e:
            logger.error(f"执行缩放操作失败: {str(e)}", exc_info=True)
            return {
                "success": False,
                "error": str(e),
                "data": {
                    "action": "zoom",
                    "scale": scale,
                    "executed": False
                }
            }
    
    async def _handle_focus(self, command: MCPCommand) -> Dict[str, Any]:
        """处理聚焦命令"""
        if not self.page:
            return {"success": False, "error": "页面未初始化", "data": {"executed": False}}
        
        # 获取聚焦目标
        target = command.target or "center"
        
        try:
            logger.info(f"执行聚焦操作: 目标={target}")
            
            # 直接执行JavaScript代码
            js_result = await self.page.evaluate("""
            (params) => {
                try {
                    // 获取ThreeJS对象
                    const scene = window.__scene || window.scene;
                    const camera = window.__camera || window.camera;
                    const renderer = window.__renderer || window.renderer;
                    const controls = window.__controls || window.__orbitControls || window.controls;
                    
                    if (!scene || !camera || !renderer || !controls) {
                        console.error('ThreeJS对象未初始化');
                        return { success: false, error: 'ThreeJS对象未初始化' };
                    }
                    
                    // 根据目标执行聚焦
                    if (params.target === "center") {
                        // 重置控制器到中心
                        controls.target.set(0, 0, 0);
                    } else {
                        // 尝试查找目标对象
                        const targetObject = scene.getObjectByName(params.target);
                        if (targetObject) {
                            // 计算目标对象的中心点
                            const box = new THREE.Box3().setFromObject(targetObject);
                            const center = box.getCenter(new THREE.Vector3());
                            controls.target.copy(center);
                        } else {
                            console.error(`未找到目标对象: ${params.target}`);
                            return { success: false, error: `未找到目标对象: ${params.target}` };
                        }
                    }
                    
                    // 更新控制器和渲染
                    controls.update();
                    renderer.render(scene, camera);
                    
                    return { success: true, executed: true };
                } catch (error) {
                    console.error('执行聚焦操作出错:', error);
                    return { success: false, error: error.toString() };
                }
            }
            """, {"target": target})
            
            logger.info(f"聚焦操作JavaScript执行结果: {js_result}")
            
            return {
                "success": js_result.get("success", False),
                "data": {
                    "action": "focus",
                    "target": target,
                    "executed": js_result.get("executed", False)
                },
                "error": js_result.get("error")
            }
        except Exception as e:
            logger.error(f"执行聚焦操作失败: {str(e)}", exc_info=True)
            return {
                "success": False,
                "error": str(e),
                "data": {
                    "action": "focus",
                    "target": target,
                    "executed": False
                }
            }
    
    async def _handle_reset(self, command: MCPCommand) -> Dict[str, Any]:
        """处理重置命令"""
        if not self.page:
            return {"success": False, "error": "页面未初始化", "data": {"executed": False}}
        
        try:
            logger.info("执行重置操作")
            
            # 直接执行JavaScript代码
            js_result = await self.page.evaluate("""
            () => {
                try {
                    // 获取ThreeJS对象
                    const scene = window.__scene || window.scene;
                    const camera = window.__camera || window.camera;
                    const renderer = window.__renderer || window.renderer;
                    const controls = window.__controls || window.__orbitControls || window.controls;
                    
                    if (!scene || !camera || !renderer || !controls) {
                        console.error('ThreeJS对象未初始化');
                        return { success: false, error: 'ThreeJS对象未初始化' };
                    }
                    
                    // 重置相机位置
                    if (window.__defaultCameraPosition) {
                        camera.position.copy(window.__defaultCameraPosition);
                    } else {
                        camera.position.set(0, 5, 10);
                    }
                    
                    // 重置控制器
                    controls.target.set(0, 0, 0);
                    controls.update();
                    
                    // 更新渲染
                    renderer.render(scene, camera);
                    
                    return { success: true, executed: true };
                } catch (error) {
                    console.error('执行重置操作出错:', error);
                    return { success: false, error: error.toString() };
                }
            }
            """)
            
            logger.info(f"重置操作JavaScript执行结果: {js_result}")
            
            return {
                "success": js_result.get("success", False),
                "data": {
                    "action": "reset",
                    "executed": js_result.get("executed", False)
                },
                "error": js_result.get("error")
            }
        except Exception as e:
            logger.error(f"执行重置操作失败: {str(e)}", exc_info=True)
            return {
                "success": False,
                "error": str(e),
                "data": {
                    "action": "reset",
                    "executed": False
                }
            }

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
    if not message or not isinstance(message, str):
        logger.warning(f"生成命令的输入无效: {message}")
        return None
        
    # 记录原始输入
    logger.info(f"从自然语言生成MCP命令，输入: {message}")
    
    # 转换为小写便于匹配
    message_lower = message.lower()
    
    # 旋转命令
    if "旋转" in message_lower or "rotate" in message_lower or "turn" in message_lower:
        direction = "left"
        degrees = 45
        
        # 检测方向
        if "左" in message_lower or "left" in message_lower:
            direction = "left"
        elif "右" in message_lower or "right" in message_lower:
            direction = "right"
        elif "上" in message_lower or "up" in message_lower:
            direction = "up"
        elif "下" in message_lower or "down" in message_lower:
            direction = "down"
        
        # 检测角度
        import re
        angle_match = re.search(r'(\d+)\s*度', message_lower)
        if angle_match:
            degrees = int(angle_match.group(1))
        
        # 创建命令并确保action是字符串
        cmd = MCPCommand(
            action="rotate",  # 使用字符串而不是枚举
            parameters={"direction": direction, "angle": degrees}  # 使用degrees而不是angle
        )
        logger.info(f"生成旋转命令: {cmd.to_dict()}")
        return cmd
    
    # 缩放命令
    elif any(keyword in message_lower for keyword in ["缩放", "放大", "缩小", "zoom", "scale"]):
        scale = 1.5
        
        # 检测缩放方向
        if "缩小" in message_lower or "减小" in message_lower:
            scale = 0.8
        
        # 尝试提取精确的比例值
        import re
        scale_match = re.search(r'(\d+(?:\.\d+)?)\s*倍', message_lower)
        if scale_match:
            scale = float(scale_match.group(1))
        
        # 创建命令并确保action是字符串
        cmd = MCPCommand(
            action="zoom",  # 使用字符串而不是枚举
            parameters={"scale": scale}
        )
        logger.info(f"生成缩放命令: {cmd.to_dict()}")
        return cmd
    
    # 聚焦命令
    elif any(keyword in message_lower for keyword in ["聚焦", "关注", "focus", "center"]):
        target = "center"
        
        # 尝试提取目标
        if "区域" in message_lower or "area" in message_lower:
            import re
            area_match = re.search(r'区域\s*(\d+)', message_lower)
            if area_match:
                target = f"Area_{area_match.group(1)}"
        elif "会议室" in message_lower or "meeting" in message_lower:
            target = "meeting_room"
        
        # 创建命令并确保action是字符串
        cmd = MCPCommand(
            action="focus",  # 使用字符串而不是枚举
            parameters={},
            target=target
        )
        logger.info(f"生成聚焦命令: {cmd.to_dict()}")
        return cmd
    
    # 重置命令
    elif any(keyword in message_lower for keyword in ["重置", "复位", "reset", "default"]):
        # 创建命令并确保action是字符串
        cmd = MCPCommand(
            action="reset",  # 使用字符串而不是枚举
            parameters={}
        )
        logger.info(f"生成重置命令: {cmd.to_dict()}")
        return cmd
    
    # 尝试基于关键词进行简单匹配
    command_action = None
    if "模型" in message_lower and ("左" in message_lower or "右" in message_lower):
        command_action = "rotate"
    elif "放大" in message_lower or "缩小" in message_lower:
        command_action = "zoom"
    elif "恢复" in message_lower or "初始" in message_lower:
        command_action = "reset"
    
    if command_action:
        logger.info(f"基于关键词匹配生成命令: {command_action}")
        
        if command_action == "rotate":
            direction = "left" if "左" in message_lower else "right"
            degrees = 45
            # 提取角度数字
            import re
            angle_match = re.search(r'(\d+)', message_lower)
            if angle_match:
                degrees = int(angle_match.group(1))
            logger.info(f"生成旋转命令，方向:{direction}，角度:{degrees}")
            return MCPCommand(
                action="rotate",
                parameters={"direction": direction, "angle": degrees}  # 使用degrees而不是angle
            )
        elif command_action == "zoom":
            scale = 0.8 if "缩小" in message_lower else 1.5
            return MCPCommand(
                action="zoom",
                parameters={"scale": scale}
            )
        elif command_action == "reset":
            return MCPCommand(
                action="reset",
                parameters={}
            )
    
    # 无法识别的命令
    logger.warning(f"无法从自然语言识别命令: {message}")
    return None 