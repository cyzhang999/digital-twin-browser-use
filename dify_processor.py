#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
Dify工具处理器 (Dify Tool Processor)
负责处理和注册Dify工具，用于管理与Dify API的交互
"""

import json
import logging
from typing import Dict, List, Any, Callable, Optional
import httpx
import asyncio

logger = logging.getLogger(__name__)

class DifyProcessor:
    """
    Dify工具处理器
    
    负责：
    1. 注册MCP工具到Dify
    2. 处理来自Dify的工具调用
    3. 提供工具执行结果
    """
    
    def __init__(self, api_base_url: str, api_key: str):
        """
        初始化Dify工具处理器
        
        Args:
            api_base_url: Dify API基础URL
            api_key: Dify API密钥
        """
        self.api_base_url = api_base_url.rstrip('/')
        self.api_key = api_key
        # 工具处理函数映射
        self.tool_handlers: Dict[str, Callable] = {}
        # 注册的工具定义
        self.registered_tools: List[Dict[str, Any]] = []
        logger.info(f"Dify工具处理器已初始化，API基础URL: {api_base_url}")
    
    def register_tool(self, tool_name: str, description: str, parameters: Dict, handler: Callable) -> None:
        """
        注册工具到Dify
        
        Args:
            tool_name: 工具名称
            description: 工具描述
            parameters: 工具参数定义
            handler: 工具处理函数
        """
        # 定义工具
        tool_definition = {
            "name": tool_name,
            "description": description,
            "parameters": {
                "type": "object",
                "properties": parameters,
                "required": list(parameters.keys())
            }
        }
        
        # 添加到已注册工具列表
        self.registered_tools.append(tool_definition)
        
        # 注册处理函数
        self.tool_handlers[tool_name] = handler
        
        logger.info(f"工具已注册: {tool_name}")
    
    async def register_tools_to_dify(self, app_id: str) -> bool:
        """
        将注册的工具提交到Dify应用
        
        Args:
            app_id: Dify应用ID
            
        Returns:
            注册是否成功
        """
        if not self.registered_tools:
            logger.warning("没有工具可注册到Dify")
            return False
            
        url = f"{self.api_base_url}/apps/{app_id}/tools"
        
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }
        
        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    url,
                    headers=headers,
                    json={"tools": self.registered_tools},
                    timeout=30.0
                )
                
                if response.status_code in (200, 201):
                    logger.info(f"成功注册 {len(self.registered_tools)} 个工具到Dify应用 {app_id}")
                    return True
                else:
                    logger.error(f"注册工具到Dify失败: {response.status_code} - {response.text}")
                    return False
        except Exception as e:
            logger.error(f"注册工具到Dify时发生错误: {e}")
            return False
    
    async def process_tool_call(self, tool_name: str, parameters: Dict[str, Any]) -> Dict[str, Any]:
        """
        处理工具调用
        
        Args:
            tool_name: 被调用的工具名称
            parameters: 调用参数
            
        Returns:
            工具执行结果
        """
        logger.info(f"处理工具调用: {tool_name} 参数: {parameters}")
        
        if tool_name not in self.tool_handlers:
            logger.error(f"未找到工具处理程序: {tool_name}")
            return {
                "status": "error",
                "message": f"未知工具: {tool_name}"
            }
        
        try:
            # 获取处理函数
            handler = self.tool_handlers[tool_name]
            
            # 执行处理函数（支持同步和异步）
            if asyncio.iscoroutinefunction(handler):
                result = await handler(**parameters)
            else:
                result = handler(**parameters)
                
            logger.info(f"工具 {tool_name} 执行成功")
            return {
                "status": "success",
                "result": result
            }
        except Exception as e:
            logger.error(f"工具 {tool_name} 执行失败: {e}", exc_info=True)
            return {
                "status": "error",
                "message": f"执行错误: {str(e)}"
            }
    
    async def handle_dify_webhook(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """
        处理来自Dify的Webhook调用
        
        Args:
            payload: Webhook载荷
            
        Returns:
            处理结果
        """
        logger.debug(f"收到Dify Webhook: {json.dumps(payload, ensure_ascii=False)}")
        
        try:
            # 提取工具调用信息
            tool_calls = payload.get("tool_calls", [])
            
            if not tool_calls:
                logger.warning("Webhook中未找到工具调用")
                return {
                    "status": "error",
                    "message": "未找到工具调用"
                }
            
            # 处理所有工具调用
            results = []
            for tool_call in tool_calls:
                tool_name = tool_call.get("name")
                parameters = tool_call.get("parameters", {})
                call_id = tool_call.get("id", "unknown")
                
                # 处理单个工具调用
                result = await self.process_tool_call(tool_name, parameters)
                results.append({
                    "call_id": call_id,
                    "tool_name": tool_name,
                    **result
                })
            
            return {
                "status": "success",
                "results": results
            }
        except Exception as e:
            logger.error(f"处理Dify Webhook时发生错误: {e}", exc_info=True)
            return {
                "status": "error",
                "message": f"处理错误: {str(e)}"
            }
            
    async def execute_dify_tool(self, tool_name: str, parameters: Dict[str, Any]) -> Dict[str, Any]:
        """
        直接执行Dify工具（用于本地调用）
        
        Args:
            tool_name: 工具名称
            parameters: 工具参数
            
        Returns:
            执行结果
        """
        return await self.process_tool_call(tool_name, parameters) 