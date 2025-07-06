#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
日志设置模块
提供统一的日志配置和管理功能
"""

import os
import logging
import logging.handlers
from pathlib import Path
from typing import Optional
from .config_manager import LoggingConfig, LogLevel


# 全局日志器缓存
_loggers = {}


def setup_logger(config: Optional[LoggingConfig] = None, name: str = None) -> logging.Logger:
    """
    设置日志器
    
    Args:
        config: 日志配置对象
        name: 日志器名称，默认为调用模块名
    
    Returns:
        配置好的日志器
    """
    if config is None:
        config = LoggingConfig()
    
    if name is None:
        # 获取调用者的模块名
        import inspect
        frame = inspect.currentframe().f_back
        name = frame.f_globals.get('__name__', 'test_framework')
    
    # 如果已经配置过，直接返回
    if name in _loggers:
        return _loggers[name]
    
    # 创建日志器
    logger = logging.getLogger(name)
    logger.setLevel(_get_log_level(config.level))
    
    # 清除现有的处理器
    logger.handlers.clear()
    
    # 创建格式化器
    formatter = logging.Formatter(
        fmt=config.format,
        datefmt=config.date_format
    )
    
    # 添加控制台处理器
    if config.console_handler:
        console_handler = logging.StreamHandler()
        console_handler.setLevel(_get_log_level(config.level))
        console_handler.setFormatter(formatter)
        logger.addHandler(console_handler)
    
    # 添加文件处理器
    if config.file_handler:
        # 确保日志目录存在
        log_dir = Path(config.log_dir)
        log_dir.mkdir(parents=True, exist_ok=True)
        
        # 创建轮转文件处理器
        file_handler = logging.handlers.RotatingFileHandler(
            filename=config.log_file_path,
            maxBytes=config.max_file_size,
            backupCount=config.backup_count,
            encoding=config.encoding
        )
        file_handler.setLevel(_get_log_level(config.level))
        file_handler.setFormatter(formatter)
        logger.addHandler(file_handler)
    
    # 防止日志传播到根日志器
    logger.propagate = False
    
    # 缓存日志器
    _loggers[name] = logger
    
    return logger


def get_logger(name: str = None) -> logging.Logger:
    """
    获取日志器
    
    Args:
        name: 日志器名称，默认为调用模块名
    
    Returns:
        日志器实例
    """
    if name is None:
        # 获取调用者的模块名
        import inspect
        frame = inspect.currentframe().f_back
        name = frame.f_globals.get('__name__', 'test_framework')
    
    # 如果已经存在，直接返回
    if name in _loggers:
        return _loggers[name]
    
    # 否则使用默认配置创建
    return setup_logger(name=name)


def _get_log_level(level: LogLevel) -> int:
    """
    将LogLevel枚举转换为logging模块的级别
    
    Args:
        level: LogLevel枚举值
    
    Returns:
        logging模块的日志级别
    """
    level_mapping = {
        LogLevel.DEBUG: logging.DEBUG,
        LogLevel.INFO: logging.INFO,
        LogLevel.WARNING: logging.WARNING,
        LogLevel.ERROR: logging.ERROR,
        LogLevel.CRITICAL: logging.CRITICAL
    }
    return level_mapping.get(level, logging.INFO)


def configure_root_logger(config: LoggingConfig):
    """
    配置根日志器
    
    Args:
        config: 日志配置对象
    """
    root_logger = logging.getLogger()
    root_logger.setLevel(_get_log_level(config.level))
    
    # 清除现有处理器
    root_logger.handlers.clear()
    
    # 使用setup_logger配置根日志器
    setup_logger(config, 'root')


def disable_external_loggers():
    """
    禁用外部库的日志输出
    """
    # 禁用一些常见的第三方库日志
    external_loggers = [
        'urllib3.connectionpool',
        'selenium.webdriver.remote.remote_connection',
        'requests.packages.urllib3.connectionpool',
        'PIL.PngImagePlugin',
        'matplotlib.font_manager'
    ]
    
    for logger_name in external_loggers:
        logging.getLogger(logger_name).setLevel(logging.WARNING)


def setup_test_logging(log_level: str = 'INFO', log_file: str = None):
    """
    快速设置测试日志
    
    Args:
        log_level: 日志级别字符串
        log_file: 日志文件路径
    """
    config = LoggingConfig()
    
    # 设置日志级别
    try:
        config.level = LogLevel(log_level.upper())
    except ValueError:
        config.level = LogLevel.INFO
    
    # 设置日志文件
    if log_file:
        config.log_file = log_file
        config.file_handler = True
    
    # 配置根日志器
    configure_root_logger(config)
    
    # 禁用外部日志
    disable_external_loggers()
    
    return get_logger('test_framework')