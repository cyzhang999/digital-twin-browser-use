#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
MCP适配器模块
(MCP Adapter Module)

实现MCP协议标准，用于处理来自前端的WebSocket消息和执行模型操作。
MCP (Model Control Protocol) 协议定义了一套标准的模型操作协议，
允许通过统一接口对3D模型进行操作。
"""

import json
import logging
import asyncio
import traceback
from typing import Dict, Any, List, Optional, Union, Callable
from datetime import datetime
from enum import Enum

# 配置日志
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("mcp_adapter")

# MCP操作类型
class MCPOperationType(str, Enum):
    ROTATE = "rotate"
    ZOOM = "zoom"
    FOCUS = "focus"
    RESET = "reset"
    CUSTOM = "custom"  # 自定义操作

# MCP服务器配置
class MCPServerConfig:
    """MCP服务器配置"""
    def __init__(self, server_id: str, command: str, args: List[str], env: Dict[str, str] = None):
        self.server_id = server_id
        self.command = command
        self.args = args
        self.env = env or {}

# MCP命令
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
        self.id = command_id or datetime.now().isoformat()
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            "id": self.id,
            "action": self.action,
            "target": self.target,
            "parameters": self.parameters
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

# MCP消息
class MCPMessage:
    """MCP消息"""
    def __init__(
        self, 
        type: str, 
        data: Any = None, 
        timestamp: str = None,
        message_id: str = None
    ):
        self.type = type
        self.data = data
        self.timestamp = timestamp or datetime.now().isoformat()
        self.id = message_id or datetime.now().isoformat()
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        result = {
            "type": self.type,
            "timestamp": self.timestamp,
            "id": self.id
        }
        
        if self.data is not None:
            if isinstance(self.data, dict):
                result.update(self.data)
            else:
                result["data"] = self.data
        
        return result
    
    def to_json(self) -> str:
        """转换为JSON字符串"""
        return json.dumps(self.to_dict())
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'MCPMessage':
        """从字典创建消息"""
        msg_type = data.pop("type", "unknown")
        timestamp = data.pop("timestamp", None)
        msg_id = data.pop("id", None)
        
        # 剩余的数据作为消息数据
        return cls(
            type=msg_type,
            data=data,
            timestamp=timestamp,
            message_id=msg_id
        )
    
    @classmethod
    def command(cls, command: MCPCommand) -> 'MCPMessage':
        """创建命令消息"""
        return cls(
            type="command",
            data={"command": command.to_dict()}
        )
    
    @classmethod
    def response(cls, command_id: str, success: bool, result: Any = None) -> 'MCPMessage':
        """创建响应消息"""
        return cls(
            type="response",
            data={
                "commandId": command_id,
                "success": success,
                "result": result
            }
        )
    
    @classmethod
    def error(cls, error_message: str, error_code: int = 500) -> 'MCPMessage':
        """创建错误消息"""
        return cls(
            type="error",
            data={
                "message": error_message,
                "code": error_code
            }
        )

# MCP客户端连接
class MCPClientConnection:
    """MCP客户端连接"""
    def __init__(self, client_id: str, websocket, client_type: str = "unknown"):
        self.client_id = client_id
        self.websocket = websocket
        self.client_type = client_type
        self.connected_at = datetime.now().isoformat()
        self.last_activity = datetime.now().isoformat()
    
    async def send_message(self, message: Union[MCPMessage, Dict, str]) -> bool:
        """发送消息到客户端"""
        try:
            # 更新最后活动时间
            self.last_activity = datetime.now().isoformat()
            
            # 将消息转换为JSON字符串
            if isinstance(message, MCPMessage):
                message_json = message.to_json()
            elif isinstance(message, dict):
                message_json = json.dumps(message)
            else:
                message_json = message
            
            # 发送消息
            logger.debug(f"向客户端 {self.client_id} 发送消息: {message_json[:200]}...")
            await self.websocket.send_text(message_json)
            return True
        except Exception as e:
            logger.error(f"向客户端 {self.client_id} 发送消息失败: {str(e)}")
            logger.debug(traceback.format_exc())
            return False
    
    async def send_command(self, command: MCPCommand) -> bool:
        """发送命令"""
        return await self.send_message(MCPMessage.command(command))

# MCP适配器
class MCPAdapter:
    """MCP适配器，处理MCP协议消息"""
    def __init__(self):
        self.clients: Dict[str, MCPClientConnection] = {}
        self.command_handlers: Dict[str, Callable] = {}
        self.message_handlers: Dict[str, Callable] = {}
        self.page = None  # Playwright页面引用
        
        # 注册默认消息处理器
        self.register_message_handler("init", self._handle_init)
        self.register_message_handler("ping", self._handle_ping)
        self.register_message_handler("commandResult", self._handle_command_result)
        self.register_message_handler("command", self._handle_command_message)
        
        # 注册默认命令处理器
        self.register_command_handler(MCPOperationType.ROTATE, self._handle_rotate)
        self.register_command_handler(MCPOperationType.ZOOM, self._handle_zoom)
        self.register_command_handler(MCPOperationType.FOCUS, self._handle_focus)
        self.register_command_handler(MCPOperationType.RESET, self._handle_reset)
    
    def set_page(self, page):
        """设置Playwright页面引用"""
        self.page = page
    
    def register_client(self, client_id: str, websocket, client_type: str = "unknown") -> MCPClientConnection:
        """注册新客户端"""
        try:
            logger.info(f"注册新客户端: {client_id}, 类型: {client_type}")
            client = MCPClientConnection(client_id, websocket, client_type)
            self.clients[client_id] = client
            
            # 记录已连接客户端数量
            connected_count = len(self.clients)
            logger.info(f"当前活跃连接: {connected_count}")
            
            return client
        except Exception as e:
            logger.error(f"注册客户端 {client_id} 失败: {str(e)}")
            logger.debug(traceback.format_exc())
            # 尝试创建一个基本的客户端连接
            return MCPClientConnection(client_id, websocket, client_type)
    
    def unregister_client(self, client_id: str):
        """注销客户端"""
        if client_id in self.clients:
            logger.info(f"注销客户端: {client_id}")
            del self.clients[client_id]
            
            # 记录已连接客户端数量
            connected_count = len(self.clients)
            logger.info(f"当前活跃连接: {connected_count}")
        else:
            logger.warning(f"尝试注销不存在的客户端: {client_id}")
    
    def register_message_handler(self, message_type: str, handler: Callable):
        """注册消息处理器"""
        self.message_handlers[message_type] = handler
    
    def register_command_handler(self, action_type: str, handler: Callable):
        """注册命令处理器"""
        self.command_handlers[action_type] = handler
    
    async def process_message(self, message_data: str, client: MCPClientConnection) -> Optional[MCPMessage]:
        """处理接收到的消息"""
        try:
            # 解析消息
            data = json.loads(message_data)
            message_type = data.get("type", "unknown")
            
            logger.debug(f"收到消息: {message_type} 来自 {client.client_id}")
            
            # 查找并调用对应处理器
            handler = self.message_handlers.get(message_type)
            if handler:
                return await handler(data, client)
            else:
                logger.warning(f"未注册的消息类型: {message_type}")
                return MCPMessage.error(f"未注册的消息类型: {message_type}")
        except json.JSONDecodeError:
            logger.error(f"无效的JSON消息: {message_data}")
            return MCPMessage.error("无效的JSON消息")
        except Exception as e:
            logger.error(f"处理消息时出错: {e}")
            logger.debug(traceback.format_exc())
            return MCPMessage.error(f"处理消息时出错: {str(e)}")
    
    async def execute_command(self, command: MCPCommand) -> Dict[str, Any]:
        """执行命令"""
        try:
            logger.info(f"执行命令: {command.action}")
            
            # 查找并调用对应处理器
            handler = self.command_handlers.get(command.action)
            if handler:
                return await handler(command)
            else:
                logger.warning(f"未注册的命令: {command.action}")
                return {"success": False, "error": f"未注册的命令: {command.action}"}
        except Exception as e:
            logger.error(f"执行命令时出错: {e}")
            logger.debug(traceback.format_exc())
            return {"success": False, "error": f"执行命令时出错: {str(e)}"}
    
    async def broadcast_command(self, command: MCPCommand, exclude_client_id: str = None) -> int:
        """广播命令到所有客户端"""
        sent_count = 0
        message = MCPMessage.command(command)
        
        for client_id, client in self.clients.items():
            if exclude_client_id and client_id == exclude_client_id:
                continue
            
            if await client.send_message(message):
                sent_count += 1
        
        return sent_count
    
    # 默认消息处理器
    async def _handle_init(self, data: Dict[str, Any], client: MCPClientConnection) -> MCPMessage:
        """处理初始化消息"""
        client_type = data.get("clientType", "unknown")
        client.client_type = client_type
        
        logger.info(f"客户端初始化: {client.client_id} ({client_type})")
        
        return MCPMessage(
            type="connection_established",
            data={
                "message": "连接已建立",
                "clientId": client.client_id,
                "clientType": client_type
            }
        )
    
    async def _handle_ping(self, data: Dict[str, Any], client: MCPClientConnection) -> MCPMessage:
        """处理Ping消息"""
        return MCPMessage(
            type="pong",
            data={
                "timestamp": datetime.now().isoformat(),
                "echo": data.get("timestamp")
            }
        )
    
    async def _handle_command_result(self, data: Dict[str, Any], client: MCPClientConnection) -> None:
        """处理命令结果消息"""
        command_id = data.get("commandId")
        action = data.get("action")
        result = data.get("result", {})
        
        logger.info(f"收到命令结果: {action} (ID: {command_id}) - 成功: {result.get('success', False)}")
        
        # 这里不需要返回消息
        return None
    
    async def _handle_command_message(self, data: Dict[str, Any], client: MCPClientConnection) -> MCPMessage:
        """处理命令消息"""
        try:
            command_data = data.get("command")
            if not command_data:
                logger.warning("收到的命令消息中缺少command字段")
                return MCPMessage.error("命令消息缺少必要字段")
                
            # 创建命令对象
            command = MCPCommand.from_dict(command_data)
            
            logger.info(f"收到命令消息: {command.action} (ID: {command.id}) 来自客户端 {client.client_id}")
            
            # 执行命令
            result = await self.execute_command(command)
            
            # 返回命令执行结果
            return MCPMessage.response(command.id, result.get("success", False), result)
        except Exception as e:
            logger.error(f"处理命令消息时出错: {e}")
            logger.debug(traceback.format_exc())
            return MCPMessage.error(f"处理命令消息时出错: {str(e)}")
    
    # 默认命令处理器
    async def _handle_rotate(self, command: MCPCommand) -> Dict[str, Any]:
        """处理旋转命令"""
        if not self.page:
            return {"success": False, "error": "页面未初始化"}
        
        try:
            target = command.target
            direction = command.parameters.get("direction", "left")
            angle = command.parameters.get("angle", 45)
            
            # 使用Playwright执行JavaScript
            result = await self.page.evaluate("""
            (params) => {
                try {
                    console.log(`MCP旋转命令: ${JSON.stringify(params)}`);
                    
                    // 尝试使用全局旋转函数
                    if (typeof window.rotateModel === 'function') {
                        return window.rotateModel(params);
                    } else {
                        console.error('rotateModel函数未定义');
                        return {success: false, error: "rotateModel函数未定义"};
                    }
                } catch (error) {
                    console.error('执行旋转操作出错:', error);
                    return {success: false, error: error.toString()};
                }
            }
            """, {"target": target, "direction": direction, "angle": angle})
            
            return result if isinstance(result, dict) else {"success": bool(result)}
        except Exception as e:
            logger.error(f"执行旋转命令时出错: {e}")
            return {"success": False, "error": f"执行旋转命令时出错: {str(e)}"}
    
    async def _handle_zoom(self, command: MCPCommand) -> Dict[str, Any]:
        """处理缩放命令"""
        if not self.page:
            return {"success": False, "error": "页面未初始化"}
        
        try:
            target = command.target
            scale = command.parameters.get("scale", 1.5)
            
            # 使用Playwright执行JavaScript
            result = await self.page.evaluate("""
            (params) => {
                try {
                    console.log(`MCP缩放命令: ${JSON.stringify(params)}`);
                    
                    // 尝试使用全局缩放函数
                    if (typeof window.zoomModel === 'function') {
                        return window.zoomModel(params);
                    } else {
                        console.error('zoomModel函数未定义');
                        return {success: false, error: "zoomModel函数未定义"};
                    }
                } catch (error) {
                    console.error('执行缩放操作出错:', error);
                    return {success: false, error: error.toString()};
                }
            }
            """, {"target": target, "scale": scale})
            
            return result if isinstance(result, dict) else {"success": bool(result)}
        except Exception as e:
            logger.error(f"执行缩放命令时出错: {e}")
            return {"success": False, "error": f"执行缩放命令时出错: {str(e)}"}
    
    async def _handle_focus(self, command: MCPCommand) -> Dict[str, Any]:
        """处理聚焦命令"""
        if not self.page:
            return {"success": False, "error": "页面未初始化"}
        
        try:
            target = command.target
            
            # 使用Playwright执行JavaScript
            result = await self.page.evaluate("""
            (params) => {
                try {
                    console.log(`MCP聚焦命令: ${JSON.stringify(params)}`);
                    
                    // 尝试使用全局聚焦函数
                    if (typeof window.focusOnModel === 'function') {
                        return window.focusOnModel(params);
                    } else {
                        console.error('focusOnModel函数未定义');
                        return {success: false, error: "focusOnModel函数未定义"};
                    }
                } catch (error) {
                    console.error('执行聚焦操作出错:', error);
                    return {success: false, error: error.toString()};
                }
            }
            """, {"target": target})
            
            return result if isinstance(result, dict) else {"success": bool(result)}
        except Exception as e:
            logger.error(f"执行聚焦命令时出错: {e}")
            return {"success": False, "error": f"执行聚焦命令时出错: {str(e)}"}
    
    async def _handle_reset(self, command: MCPCommand) -> Dict[str, Any]:
        """处理重置命令"""
        if not self.page:
            return {"success": False, "error": "页面未初始化"}
        
        try:
            # 使用Playwright执行JavaScript
            result = await self.page.evaluate("""
            (params) => {
                try {
                    console.log('MCP重置命令');
                    
                    // 尝试使用全局重置函数
                    if (typeof window.resetModel === 'function') {
                        return window.resetModel(params);
                    } else {
                        console.error('resetModel函数未定义');
                        return {success: false, error: "resetModel函数未定义"};
                    }
                } catch (error) {
                    console.error('执行重置操作出错:', error);
                    return {success: false, error: error.toString()};
                }
            }
            """, {})
            
            return result if isinstance(result, dict) else {"success": bool(result)}
        except Exception as e:
            logger.error(f"执行重置命令时出错: {e}")
            return {"success": False, "error": f"执行重置命令时出错: {str(e)}"}

# 全局MCP适配器实例
mcp_adapter = MCPAdapter()

# 辅助函数：从自然语言生成MCP命令
async def generate_mcp_command_from_nl(message: str) -> Optional[MCPCommand]:
    """从自然语言生成MCP命令"""
    # 简单的规则匹配，实际项目中应使用NLU或调用大模型
    message = message.lower()
    
    # 旋转命令
    if "旋转" in message or "rotate" in message:
        direction = "left" if "左" in message or "left" in message else "right"
        # 提取角度，默认为45度
        import re
        angle_match = re.search(r'(\d+)(?:度|°|degree)', message)
        angle = int(angle_match.group(1)) if angle_match else 45
        
        return MCPCommand.rotate(direction, angle)
    
    # 缩放命令
    elif "缩放" in message or "放大" in message or "缩小" in message or "zoom" in message:
        if "放大" in message:
            scale = 1.5
        elif "缩小" in message:
            scale = 0.75
        else:
            # 提取比例，默认为1.5
            import re
            scale_match = re.search(r'(\d+(?:\.\d+)?)', message)
            scale = float(scale_match.group(1)) if scale_match else 1.5
        
        return MCPCommand.zoom(scale)
    
    # 聚焦命令
    elif "聚焦" in message or "focus" in message:
        # 尝试提取目标
        import re
        target_match = re.search(r'(到|on|至|在)\s*([A-Za-z0-9_]+|[\u4e00-\u9fa5]+(?:区域|地区|室|厅|房|区))', message)
        target = target_match.group(2) if target_match else "center"
        
        # 处理中文区域名称映射
        if target in ["中心", "中央", "center"]:
            target = "center"
        elif "会议" in target:
            target = "meeting_room"
        elif "办公" in target:
            target = "office_area"
        
        return MCPCommand.focus(target)
    
    # 重置命令
    elif "重置" in message or "复位" in message or "reset" in message:
        return MCPCommand.reset()
    
    # 无法识别
    return None

# 测试代码
if __name__ == "__main__":
    async def test():
        # 测试从自然语言生成命令
        nl_messages = [
            "向左旋转模型45度",
            "放大模型1.5倍",
            "聚焦到会议室区域",
            "重置模型视图"
        ]
        
        for message in nl_messages:
            command = await generate_mcp_command_from_nl(message)
            if command:
                print(f"消息: {message}")
                print(f"生成命令: {json.dumps(command.to_dict(), ensure_ascii=False)}")
                print()
    
    asyncio.run(test()) 