#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
自然语言解析模块 (Natural Language Parsing Module)

用于解析来自AI助手的自然语言指令，并转换为标准的MCP命令
"""

import re
from typing import Tuple, Dict, Any, Optional

def parse_natural_language(message: str) -> Tuple[str, Dict[str, Any]]:
    """
    解析自然语言消息，提取操作类型和参数
    :param message: 自然语言消息
    :return: 操作类型和参数元组 (operation, parameters)
    """
    message = message.lower()
    parameters = {}
    
    # 解析旋转操作
    if any(keyword in message for keyword in ["旋转", "rotate", "turn", "spin"]):
        operation = "rotate"
        
        # 提取方向
        if "左" in message or "left" in message:
            parameters["direction"] = "left"
        elif "右" in message or "right" in message:
            parameters["direction"] = "right"
        elif "上" in message or "up" in message:
            parameters["direction"] = "up"
        elif "下" in message or "down" in message:
            parameters["direction"] = "down"
        else:
            parameters["direction"] = "left"  # 默认向左旋转
        
        # 提取角度
        angle_match = re.search(r'(\d+)(?:\s*度|°|\s*degree)', message)
        if angle_match:
            parameters["angle"] = float(angle_match.group(1))
        else:
            parameters["angle"] = 30.0  # 默认30度
        
        return operation, parameters
    
    # 解析缩放操作
    elif any(keyword in message for keyword in ["缩放", "放大", "缩小", "zoom", "scale", "magnify", "shrink"]):
        operation = "zoom"
        
        # 提取缩放比例
        scale_match = re.search(r'(\d+\.?\d*)(?:\s*倍|\s*times|\s*x)', message)
        
        if scale_match:
            scale = float(scale_match.group(1))
            parameters["scale"] = scale
        elif "放大" in message or "magnify" in message or "larger" in message:
            parameters["scale"] = 2.0  # 默认放大2倍
        elif "缩小" in message or "shrink" in message or "smaller" in message:
            parameters["scale"] = 0.5  # 默认缩小一半
        else:
            parameters["scale"] = 1.5  # 默认缩放比例
        
        return operation, parameters
    
    # 解析聚焦操作
    elif any(keyword in message for keyword in ["聚焦", "焦点", "集中", "关注", "focus", "zoom to", "look at", "定位", "locate"]):
        operation = "focus"
        
        # 提取目标对象
        area_match = re.search(r'(?:区域|area|区|区块|部分|part|component|组件)\s*(\d+|[一二三四五六七八九十]|\w+)', message)
        center_match = any(word in message for word in ["中心", "center", "中央", "central", "middle"])
        
        if area_match:
            # 获取区域数字
            area_id = area_match.group(1)
            # 将中文数字转换为阿拉伯数字
            zh_digits = {'一': '1', '二': '2', '三': '3', '四': '4', '五': '5', 
                         '六': '6', '七': '7', '八': '8', '九': '9', '十': '10'}
            if area_id in zh_digits:
                area_id = zh_digits[area_id]
            parameters["target"] = f"area{area_id}"
        elif center_match:
            parameters["target"] = "center"
        else:
            parameters["target"] = "center"  # 默认聚焦中心
        
        return operation, parameters
    
    # 解析重置操作
    elif any(keyword in message for keyword in ["重置", "复位", "reset", "restore", "default", "初始", "original"]):
        operation = "reset"
        return operation, parameters
    
    # 默认返回空操作
    return "", {}

def extract_numeric_value(text: str) -> Optional[float]:
    """
    从文本中提取数字值
    :param text: 输入文本
    :return: 提取的数字，如果未找到则返回None
    """
    # 匹配数字模式
    match = re.search(r'(\d+\.?\d*|\.\d+)', text)
    if match:
        return float(match.group(1))
    return None

if __name__ == "__main__":
    # 测试解析函数
    test_messages = [
        "请向左旋转模型45度",
        "将模型放大2倍",
        "聚焦到区域3",
        "请重置模型视图",
        "对模型进行缩小操作",
        "定位到区域一"
    ]
    
    for msg in test_messages:
        op, params = parse_natural_language(msg)
        print(f"消息: '{msg}'")
        print(f"解析结果: 操作={op}, 参数={params}")
        print("-" * 50) 