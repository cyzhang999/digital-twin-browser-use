#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
MCP命令构建器 (MCP Command Builder)
提供构建MCP协议命令的工具类
"""

import json
import logging
import uuid
from typing import Dict, Any, Optional, List, Union

logger = logging.getLogger(__name__)

class MCPCommandBuilder:
    """
    MCP命令构建器
    
    提供构建符合MCP协议的命令对象的方法
    支持创建各种类型的MCP操作命令
    """
    
    @staticmethod
    def create_command(operation: str, params: Dict[str, Any], command_id: Optional[str] = None) -> Dict[str, Any]:
        """
        创建基础MCP命令结构
        
        Args:
            operation: 操作类型
            params: 操作参数
            command_id: 可选的命令ID，不提供则自动生成
            
        Returns:
            MCP命令对象
        """
        if not command_id:
            command_id = str(uuid.uuid4())
            
        return {
            "type": "mcp.command",
            "command_id": command_id,
            "operation": operation,
            "params": params
        }
    
    @staticmethod
    def create_rotate_command(direction: str, angle: float = 30.0, command_id: Optional[str] = None) -> Dict[str, Any]:
        """
        创建旋转模型命令
        
        Args:
            direction: 旋转方向 (left, right, up, down)
            angle: 旋转角度，默认30度
            command_id: 可选的命令ID
            
        Returns:
            旋转命令对象
        """
        # 验证方向参数
        valid_directions = ["left", "right", "up", "down"]
        if direction not in valid_directions:
            raise ValueError(f"旋转方向必须是: {', '.join(valid_directions)}")
        
        # 构建参数
        params = {
            "direction": direction,
            "angle": angle
        }
        
        logger.debug(f"创建旋转命令: 方向={direction}, 角度={angle}")
        return MCPCommandBuilder.create_command("rotate", params, command_id)
    
    @staticmethod
    def create_zoom_command(scale: float, command_id: Optional[str] = None) -> Dict[str, Any]:
        """
        创建缩放模型命令
        
        Args:
            scale: 缩放比例，>1为放大，<1为缩小
            command_id: 可选的命令ID
            
        Returns:
            缩放命令对象
        """
        # 验证缩放参数
        if scale <= 0:
            raise ValueError("缩放比例必须大于0")
        
        # 构建参数
        params = {
            "scale": scale
        }
        
        logger.debug(f"创建缩放命令: 比例={scale}")
        return MCPCommandBuilder.create_command("zoom", params, command_id)
    
    @staticmethod
    def create_focus_command(target: str, command_id: Optional[str] = None) -> Dict[str, Any]:
        """
        创建聚焦模型命令
        
        Args:
            target: 要聚焦的目标组件名称
            command_id: 可选的命令ID
            
        Returns:
            聚焦命令对象
        """
        if not target:
            raise ValueError("目标组件名称不能为空")
        
        # 构建参数
        params = {
            "target": target
        }
        
        logger.debug(f"创建聚焦命令: 目标={target}")
        return MCPCommandBuilder.create_command("focus", params, command_id)
    
    @staticmethod
    def create_reset_command(command_id: Optional[str] = None) -> Dict[str, Any]:
        """
        创建重置模型视图命令
        
        Args:
            command_id: 可选的命令ID
            
        Returns:
            重置命令对象
        """
        logger.debug("创建重置视图命令")
        return MCPCommandBuilder.create_command("reset", {}, command_id)
    
    @staticmethod
    def create_highlight_command(component_id: str, 
                                color: Optional[str] = "#FF0000", 
                                duration: Optional[float] = None,
                                command_id: Optional[str] = None) -> Dict[str, Any]:
        """
        创建高亮组件命令
        
        Args:
            component_id: 要高亮的组件ID
            color: 高亮颜色，默认红色
            duration: 高亮持续时间（秒），默认无限
            command_id: 可选的命令ID
            
        Returns:
            高亮命令对象
        """
        if not component_id:
            raise ValueError("组件ID不能为空")
        
        # 构建参数
        params = {
            "component_id": component_id,
            "color": color
        }
        
        # 添加可选的持续时间
        if duration is not None:
            params["duration"] = duration
        
        logger.debug(f"创建高亮命令: 组件={component_id}, 颜色={color}")
        return MCPCommandBuilder.create_command("highlight", params, command_id)
    
    @staticmethod
    def create_animate_command(animation_type: str, 
                              target: Union[str, List[str]], 
                              duration: float = 1.0,
                              command_id: Optional[str] = None) -> Dict[str, Any]:
        """
        创建动画命令
        
        Args:
            animation_type: 动画类型 (slide, rotate, pulse)
            target: 要应用动画的目标组件ID或ID列表
            duration: 动画持续时间（秒）
            command_id: 可选的命令ID
            
        Returns:
            动画命令对象
        """
        # 验证动画类型
        valid_animations = ["slide", "rotate", "pulse"]
        if animation_type not in valid_animations:
            raise ValueError(f"动画类型必须是: {', '.join(valid_animations)}")
        
        # 转换单个目标为列表
        if isinstance(target, str):
            target = [target]
        
        # 构建参数
        params = {
            "type": animation_type,
            "targets": target,
            "duration": duration
        }
        
        logger.debug(f"创建动画命令: 类型={animation_type}, 目标数量={len(target)}")
        return MCPCommandBuilder.create_command("animate", params, command_id)
    
    @staticmethod
    def create_execute_js_command(code: str, command_id: Optional[str] = None) -> Dict[str, Any]:
        """
        创建执行JavaScript代码命令
        
        Args:
            code: 要执行的JavaScript代码
            command_id: 可选的命令ID
            
        Returns:
            执行JS命令对象
        """
        if not code:
            raise ValueError("JavaScript代码不能为空")
        
        # 构建参数
        params = {
            "code": code
        }
        
        logger.debug("创建执行JS命令")
        return MCPCommandBuilder.create_command("execute_js", params, command_id)
    
    @staticmethod
    def serialize_command(command: Dict[str, Any]) -> str:
        """
        将命令序列化为JSON字符串
        
        Args:
            command: MCP命令对象
            
        Returns:
            JSON字符串
        """
        return json.dumps(command, ensure_ascii=False)
    
    @staticmethod
    def create_batch_command(commands: List[Dict[str, Any]], command_id: Optional[str] = None) -> Dict[str, Any]:
        """
        创建批量命令（可一次执行多个命令）
        
        Args:
            commands: 命令列表
            command_id: 可选的命令ID
            
        Returns:
            批量命令对象
        """
        if not commands:
            raise ValueError("命令列表不能为空")
        
        # 构建参数
        params = {
            "commands": commands
        }
        
        logger.debug(f"创建批量命令: 命令数量={len(commands)}")
        return MCPCommandBuilder.create_command("batch", params, command_id) 