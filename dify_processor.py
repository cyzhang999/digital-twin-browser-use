import os
import json
import re
import httpx
import logging
from typing import Dict, Any, Optional, Tuple
from urllib.parse import urlparse
from dotenv import load_dotenv

# 加载环境变量
load_dotenv()

# 获取logger
from logger_config import get_logger
logger = get_logger("dify-processor")

# 从环境变量获取配置
DIFY_API_KEY = os.getenv("DIFY_API_KEY", "")
DIFY_API_URL = os.getenv("DIFY_API_URL", "")
DIFY_TIMEOUT = int(os.getenv("DIFY_TIMEOUT", "30"))

# 验证Dify API配置
if not DIFY_API_URL:
    logger.warning("未配置Dify API URL，将使用本地解析")
if not DIFY_API_KEY:
    logger.warning("未配置Dify API Key，将使用本地解析")

# 操作指令的正则表达式模式
PATTERN_ROTATE = re.compile(r'(?:向|)(左|右)(?:旋转|)(?:([\d\.]+)(?:度|))?', re.IGNORECASE)
PATTERN_ZOOM = re.compile(r'(?:放大|缩小)([\d\.]+)(?:倍|)', re.IGNORECASE)
PATTERN_FOCUS = re.compile(r'聚焦(?:到|)?([\w\d_]+)', re.IGNORECASE)
PATTERN_RESET = re.compile(r'(?:重置|复位|恢复)(?:视图|模型|)', re.IGNORECASE)

def call_dify_api(message: str) -> str:
    """
    调用Dify API，发送用户消息并获取响应
    
    Args:
        message: 用户消息
        
    Returns:
        Dify API的响应文本
        
    Raises:
        Exception: 当API调用失败或响应解析失败时抛出
    """
    # 检查API配置
    if not DIFY_API_URL or not DIFY_API_KEY:
        logger.warning("Dify API未完全配置，使用默认响应")
        return json.dumps(extract_model_operation_from_text(message) or {})
    
    try:
        # 准备请求头和参数
        headers = {
            "Authorization": f"Bearer {DIFY_API_KEY}",
            "Content-Type": "application/json"
        }
        
        # 解析URL域名
        parsed_url = urlparse(DIFY_API_URL)
        domain = f"{parsed_url.scheme}://{parsed_url.netloc}"
        
        # 检查URL是否包含路径
        api_path = parsed_url.path
        if not api_path or api_path == "/":
            # 使用默认的聊天路径
            api_path = "/v1/chat-messages"
        
        # 完整API URL
        api_url = f"{domain}{api_path}"
        
        # 准备请求数据
        data = {
            "inputs": {},
            "query": message,
            "response_mode": "streaming",
            "conversation_id": None,
            "user": "browser-service"
        }
        
        logger.debug(f"发送请求到Dify API: {api_url}")
        logger.debug(f"请求数据: {json.dumps(data)}")
        
        # 发送POST请求
        with httpx.Client(timeout=DIFY_TIMEOUT) as client:
            response = client.post(api_url, headers=headers, json=data)
            
            # 检查响应状态
            if response.status_code != 200:
                logger.error(f"Dify API返回错误状态码: {response.status_code}, 响应: {response.text}")
                return json.dumps(extract_model_operation_from_text(message) or get_default_operation())
            
            # 处理响应内容
            response_text = response.text
            
            # 验证响应不为空
            if not response_text:
                logger.error("Dify API返回空响应")
                return json.dumps(extract_model_operation_from_text(message) or get_default_operation())
            
            logger.debug(f"Dify API响应原始数据: {response_text[:200]}...")
            
            # 返回处理后的响应
            return response_text
            
    except httpx.RequestError as e:
        logger.error(f"请求Dify API时出错: {str(e)}")
        # 返回从用户消息中提取的操作或默认操作
        return json.dumps(extract_model_operation_from_text(message) or get_default_operation())
    except Exception as e:
        logger.error(f"调用Dify API过程中出现异常: {str(e)}")
        # 返回从用户消息中提取的操作或默认操作
        return json.dumps(extract_model_operation_from_text(message) or get_default_operation())

def extract_json_from_text(text: str) -> Dict[str, Any]:
    """
    从文本中提取JSON对象，适用于从LLM响应中解析
    
    Args:
        text: 包含可能的JSON的文本
        
    Returns:
        提取的JSON对象
    """
    if not text:
        logger.warning("提取JSON失败: 输入文本为空")
        return {}
    
    # 首先尝试整个文本是否为有效JSON
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass
    
    # 尝试使用正则表达式查找JSON对象
    try:
        # 查找 { ... } 模式
        json_pattern = r'\{(?:[^{}]|(?:\{(?:[^{}]|(?:\{[^{}]*\}))*\}))*\}'
        matches = re.findall(json_pattern, text)
        if matches:
            for match in matches:
                try:
                    return json.loads(match)
                except json.JSONDecodeError:
                    continue
    except Exception as e:
        logger.warning(f"正则表达式提取JSON失败: {e}")
    
    # 如果JSON提取失败，尝试直接从文本中理解模型操作
    operation = extract_model_operation_from_text(text)
    if operation:
        logger.info(f"从文本中直接提取操作: {operation}")
        return operation
    
    # 所有方法都失败时返回空对象
    logger.warning("所有JSON提取方法均失败")
    return {}

def extract_model_operation_from_text(text: str) -> Optional[Dict[str, Any]]:
    """
    直接从文本中提取模型操作指令
    
    Args:
        text: 用户输入或LLM响应文本
        
    Returns:
        操作指令对象或None
    """
    if not text:
        return None
    
    text = text.lower()
    
    # 检查重置操作
    if PATTERN_RESET.search(text):
        return {
            "operation": "reset"
        }
    
    # 检查旋转操作
    rotate_match = PATTERN_ROTATE.search(text)
    if rotate_match or "旋转" in text:
        direction = "left"  # 默认方向
        angle = 45  # 默认角度
        
        if rotate_match:
            if rotate_match.group(1) == "右":
                direction = "right"
            
            if rotate_match.group(2):
                try:
                    angle = int(float(rotate_match.group(2)))
                except (ValueError, TypeError):
                    pass
        
        return {
            "operation": "rotate",
            "parameters": {
                "direction": direction,
                "angle": angle
            }
        }
    
    # 检查缩放操作
    zoom_match = PATTERN_ZOOM.search(text)
    if zoom_match or "放大" in text or "缩小" in text:
        scale = 1.5  # 默认比例
        
        if zoom_match and zoom_match.group(1):
            try:
                scale = float(zoom_match.group(1))
            except (ValueError, TypeError):
                pass
        
        # 如果是缩小，转换比例
        if "缩小" in text and scale > 1:
            scale = 1 / scale
        
        return {
            "operation": "zoom",
            "parameters": {
                "scale": scale
            }
        }
    
    # 检查聚焦操作
    focus_match = PATTERN_FOCUS.search(text)
    if focus_match:
        target = focus_match.group(1)
        return {
            "operation": "focus",
            "parameters": {
                "target": target
            }
        }
    
    # 未识别的操作
    return None

def get_default_operation() -> Dict[str, Any]:
    """
    返回默认操作
    当所有解析方法都失败时使用
    
    Returns:
        默认操作对象
    """
    return {
        "operation": "rotate",
        "parameters": {
            "direction": "left",
            "angle": 45
        }
    }

def process_user_message(message: str) -> Tuple[Dict[str, Any], str]:
    """
    处理用户消息，调用Dify API并解析响应
    
    Args:
        message: 用户消息
        
    Returns:
        (操作对象, 原始响应)
    """
    try:
        # 调用Dify API
        dify_response = call_dify_api(message)
        
        # 如果响应为空，使用本地解析
        if not dify_response:
            logger.warning("Dify API返回空响应，使用本地解析")
            operation = extract_model_operation_from_text(message) or get_default_operation()
            return operation, json.dumps({"text": "使用本地解析", "operation": operation})
        
        # 从响应中提取JSON
        operation = extract_json_from_text(dify_response)
        
        # 如果提取失败，尝试本地解析
        if not operation:
            logger.warning("从Dify响应中提取JSON失败，使用本地解析")
            operation = extract_model_operation_from_text(message) or get_default_operation()
        
        return operation, dify_response
        
    except Exception as e:
        logger.error(f"处理用户消息时出错: {e}")
        # 使用本地解析作为备选
        operation = extract_model_operation_from_text(message) or get_default_operation()
        return operation, json.dumps({"error": str(e), "operation": operation})

# 测试代码
if __name__ == "__main__":
    # 测试直接解析
    test_messages = [
        "向左旋转45度",
        "右转90度",
        "缩小2倍",
        "放大1.5倍",
        "聚焦到发动机",
        "重置视图",
        "旋转模型",
        "无法识别的指令"
    ]
    
    for msg in test_messages:
        print(f"\n测试消息: '{msg}'")
        operation, response = process_user_message(msg)
        print(f"提取的操作: {operation}")
        print(f"原始响应: {response[:100]}..." if len(response) > 100 else response) 