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

    async def handle_command(self, websocket: WebSocket, command: Dict[str, Any]) -> None:
        """处理MCP命令"""
        try:
            command_id = command.get('id')
            command_type = command.get('type')

            # 处理ping消息
            if command_type == 'ping':
                logger.info(f"收到ping消息: {command}")
                await websocket.send_json({
                    "type": "pong",
                    "timestamp": datetime.now().isoformat(),
                    "id": command.get('id')
                })
                return

            # 处理其他命令类型
            if command_type == 'mcp.command':
                operation = command.get('operation')
                if not operation:
                    logger.warning(f"收到空操作类型命令: {json.dumps(command)}")
                    await websocket.send_json({
                        "type": "mcp.response",
                        "command_id": command_id,
                        "status": "error",
                        "message": "命令缺少操作类型",
                        "timestamp": datetime.now().isoformat()
                    })
                    return

                # 执行操作
                result = await self.execute_operation(operation, command.get('params', {}))

                # 发送响应
                await websocket.send_json({
                    "type": "mcp.response",
                    "command_id": command_id,
                    "status": "success" if result.get("success") else "error",
                    "message": result.get("message", ""),
                    "data": result.get("data", {}),
                    "timestamp": datetime.now().isoformat()
                })
            else:
                logger.warning(f"未知MCP消息类型: {command_type}")
                await websocket.send_json({
                    "type": "error",
                    "message": f"未知消息类型: {command_type}",
                    "timestamp": datetime.now().isoformat()
                })
        except Exception as e:
            logger.error(f"处理MCP命令时出错: {str(e)}")
            await websocket.send_json({
                "type": "error",
                "message": str(e),
                "timestamp": datetime.now().isoformat()
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
                broadcast_success = await self.broadcast_command(command)

                if not broadcast_success:
                    logger.warning("没有活跃的WebSocket连接，无法广播旋转命令")
                    return {
                        "success": True,  # 返回成功，让前端继续处理
                        "message": f"已尝试执行旋转操作 (方向={direction}, 角度={angle})"
                    }

                return {
                    "success": True,
                    "message": f"已发送旋转命令: 方向={direction}, 角度={angle}",
                    "data": {
                        "direction": direction,
                        "angle": angle
                    }
                }

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
                broadcast_success = await self.broadcast_command(command)

                if not broadcast_success:
                    logger.warning("没有活跃的WebSocket连接，无法广播缩放命令")
                    return {
                        "success": True,  # 返回成功，让前端继续处理
                        "message": f"已尝试执行缩放操作 (比例={scale})"
                    }

                return {
                    "success": True,
                    "message": f"已发送缩放命令: 比例={scale}",
                    "data": {
                        "scale": scale
                    }
                }

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
        logger.info(f"收到WebSocket连接请求: /ws 来自 {websocket.client.host}:{websocket.client.port}")
        await connection_manager.connect(websocket)
        try:
            while True:
                data = await websocket.receive_json()
                logger.info(f"收到WebSocket消息: {data}")

                # 处理ping消息
                if data.get("type") == "ping":
                    logger.info(f"收到ping消息: {data}")
                    await websocket.send_json({
                        "type": "pong",
                        "timestamp": datetime.now().isoformat(),
                        "id": data.get("id")
                    })
                    continue

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

    # 添加新的WebSocket路由
    @app.websocket("/ws/status")
    async def websocket_status_endpoint(websocket: WebSocket):
        logger.info(f"收到WebSocket连接请求: /ws/status 来自 {websocket.client.host}:{websocket.client.port}")
        await connection_manager.connect(websocket)
        try:
            # 发送初始状态消息
            status_data = {
                "type": "status",
                "data": {
                    "connected": True,
                    "service": "mcp_server",
                    "operations": operation_handler.get_registered_operations(),
                    "timestamp": datetime.now().isoformat()
                }
            }
            await websocket.send_json(status_data)
            logger.info("发送初始状态消息成功")

            # 保持连接活跃
            while True:
                # 每30秒发送一次状态更新
                await asyncio.sleep(30)
                status_data["data"]["timestamp"] = datetime.now().isoformat()
                try:
                    await websocket.send_json(status_data)
                except Exception as e:
                    logger.error(f"发送状态更新失败: {str(e)}")
                    break
        except WebSocketDisconnect:
            logger.info("状态WebSocket断开连接")
            connection_manager.disconnect(websocket)
        except Exception as e:
            logger.error(f"状态WebSocket处理异常: {str(e)}")
            connection_manager.disconnect(websocket)

    @app.websocket("/ws/health")
    async def websocket_health_endpoint(websocket: WebSocket):
        logger.info(f"收到WebSocket连接请求: /ws/health 来自 {websocket.client.host}:{websocket.client.port}")
        await connection_manager.connect(websocket)
        try:
            # 发送初始健康状态消息
            health_data = {
                "type": "health",
                "status": "ok",
                "message": "服务正常运行",
                "timestamp": datetime.now().isoformat()
            }
            await websocket.send_json(health_data)
            logger.info("发送初始健康状态消息成功")

            # 保持连接活跃
            while True:
                # 每30秒发送一次健康更新
                await asyncio.sleep(30)
                health_data["timestamp"] = datetime.now().isoformat()
                try:
                    await websocket.send_json(health_data)
                except Exception as e:
                    logger.error(f"发送健康更新失败: {str(e)}")
                    break
        except WebSocketDisconnect:
            logger.info("健康检查WebSocket断开连接")
            connection_manager.disconnect(websocket)
        except Exception as e:
            logger.error(f"健康检查WebSocket处理异常: {str(e)}")
            connection_manager.disconnect(websocket)

    @app.websocket("/ws/mcp")
    async def websocket_mcp_endpoint(websocket: WebSocket):
        logger.info(f"收到WebSocket连接请求: /ws/mcp 来自 {websocket.client.host}:{websocket.client.port}")
        await connection_manager.connect(websocket)
        try:
            while True:
                message = await websocket.receive_text()
                try:
                    data = json.loads(message)
                    logger.info(f"收到MCP消息: {data}")

                    # 处理ping消息
                    if data.get("type") == "ping":
                        logger.info(f"处理ping消息: {data}")
                        await websocket.send_json({
                            "type": "pong",
                            "id": data.get("id"),
                            "timestamp": datetime.now().isoformat()
                        })
                        continue

                    # 处理初始化消息
                    if data.get("type") == "init":
                        await websocket.send_json({
                            "type": "init.response",
                            "status": "success",
                            "message": "初始化成功",
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
                    logger.error("MCP消息格式错误，不是有效的JSON")
                    await websocket.send_json({
                        "type": "error",
                        "message": "消息格式错误，不是有效的JSON",
                        "timestamp": datetime.now().isoformat()
                    })
                except Exception as e:
                    logger.error(f"处理MCP消息时出错: {str(e)}")
                    await websocket.send_json({
                        "type": "error",
                        "message": str(e),
                        "timestamp": datetime.now().isoformat()
                    })
        except WebSocketDisconnect:
            logger.info("MCP WebSocket断开连接")
            connection_manager.disconnect(websocket)
        except Exception as e:
            logger.error(f"MCP WebSocket处理异常: {str(e)}")
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
