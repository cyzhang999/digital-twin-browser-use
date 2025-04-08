import os
import sys
import logging
from logging.handlers import RotatingFileHandler
import time
from typing import Optional

# 默认日志配置
DEFAULT_LOG_LEVEL = "INFO"
DEFAULT_LOG_DIR = "logs"
DEFAULT_LOG_FILE = "digital-twin-browser.log"

# 日志格式
CONSOLE_LOG_FORMAT = "%(asctime)s [%(levelname)s] %(name)s: %(message)s"
FILE_LOG_FORMAT = "%(asctime)s [%(levelname)s] %(name)s (%(filename)s:%(lineno)d): %(message)s"
DATE_FORMAT = "%Y-%m-%d %H:%M:%S"

# 单例模式 - 确保只创建一个日志实例
_logger_instance: Optional[logging.Logger] = None

def get_logger(name: str = "digital-twin-browser"):
    """
    获取配置好的日志记录器实例
    
    Args:
        name: 日志记录器名称
        
    Returns:
        配置好的日志记录器
    """
    global _logger_instance
    
    if _logger_instance is not None:
        return _logger_instance
    
    # 从环境变量获取日志级别
    log_level = os.getenv("LOG_LEVEL", DEFAULT_LOG_LEVEL).upper()
    log_dir = os.getenv("LOG_DIR", DEFAULT_LOG_DIR)
    log_file = os.getenv("LOG_FILE", DEFAULT_LOG_FILE)
    
    # 创建日志记录器
    logger = logging.getLogger(name)
    
    # 设置日志级别
    numeric_level = getattr(logging, log_level, logging.INFO)
    logger.setLevel(numeric_level)
    
    # 避免重复添加处理器
    if logger.handlers:
        return logger
    
    # 控制台处理器
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(logging.Formatter(CONSOLE_LOG_FORMAT, DATE_FORMAT))
    console_handler.setLevel(numeric_level)
    logger.addHandler(console_handler)
    
    # 确保日志目录存在
    if not os.path.exists(log_dir):
        try:
            os.makedirs(log_dir)
        except Exception as e:
            print(f"无法创建日志目录 {log_dir}: {e}")
            # 继续使用控制台日志
            _logger_instance = logger
            return logger
    
    # 文件处理器(旋转文件)
    try:
        file_path = os.path.join(log_dir, log_file)
        file_handler = RotatingFileHandler(
            file_path, 
            maxBytes=10 * 1024 * 1024,  # 10MB
            backupCount=5,
            encoding='utf-8'
        )
        file_handler.setFormatter(logging.Formatter(FILE_LOG_FORMAT, DATE_FORMAT))
        file_handler.setLevel(numeric_level)
        logger.addHandler(file_handler)
        
        # 记录文件日志路径
        logger.info(f"日志文件路径: {os.path.abspath(file_path)}")
    except Exception as e:
        logger.error(f"设置文件日志失败: {e}")
        logger.warning("将只使用控制台日志输出")
    
    logger.info(f"日志级别设置为: {log_level}")
    logger.info(f"启动时间: {time.strftime(DATE_FORMAT)}")
    
    _logger_instance = logger
    return logger

def log_system_info(logger):
    """记录系统信息"""
    import platform
    
    logger.info("系统信息:")
    logger.info(f"  操作系统: {platform.system()} {platform.release()}")
    logger.info(f"  Python版本: {platform.python_version()}")
    
    # 检查关键包版本
    try:
        import playwright
        logger.info(f"  Playwright版本: {playwright.__version__}")
    except (ImportError, AttributeError):
        logger.warning("  Playwright未安装或无法获取版本")
    
    try:
        import fastapi
        logger.info(f"  FastAPI版本: {fastapi.__version__}")
    except (ImportError, AttributeError):
        logger.warning("  FastAPI未安装或无法获取版本")
    
    # 记录环境变量
    logger.info("环境变量配置:")
    for key, value in os.environ.items():
        if key.startswith(("BROWSER_", "FRONTEND_", "LOG_", "API_", "VIEWPORT_", "HEADLESS")):
            if "KEY" in key and value:  # 避免记录敏感信息的完整值
                masked_value = value[:3] + "*" * (len(value) - 6) + value[-3:] if len(value) > 8 else "****"
                logger.info(f"  {key}: {masked_value}")
            else:
                logger.info(f"  {key}: {value}")

# 示例用法
if __name__ == "__main__":
    # 测试日志配置
    logger = get_logger()
    logger.debug("这是一条调试日志")
    logger.info("这是一条信息日志")
    logger.warning("这是一条警告日志")
    logger.error("这是一条错误日志")
    log_system_info(logger) 