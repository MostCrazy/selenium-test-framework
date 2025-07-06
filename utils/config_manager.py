#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
配置管理器
负责加载、管理和验证测试框架的配置信息
"""

import os
import yaml
import json
from pathlib import Path
from typing import Dict, Any, Optional, Union
from dataclasses import dataclass, field
from enum import Enum


class Environment(Enum):
    """环境枚举"""
    LOCAL = "local"
    DEV = "dev"
    TEST = "test"
    STAGING = "staging"
    PROD = "prod"


class BrowserType(Enum):
    """浏览器类型枚举"""
    CHROME = "chrome"
    FIREFOX = "firefox"
    EDGE = "edge"
    SAFARI = "safari"


class LogLevel(Enum):
    """日志级别枚举"""
    DEBUG = "DEBUG"
    INFO = "INFO"
    WARNING = "WARNING"
    ERROR = "ERROR"
    CRITICAL = "CRITICAL"


@dataclass
class DatabaseConfig:
    """数据库配置"""
    type: str = "mysql"
    host: str = "localhost"
    port: int = 3306
    username: str = "root"
    password: str = ""
    database: str = "test_db"
    charset: str = "utf8mb4"
    pool_size: int = 10
    max_overflow: int = 20
    pool_timeout: int = 30
    pool_recycle: int = 3600
    autocommit: bool = True
    
    def get_connection_string(self) -> str:
        """获取数据库连接字符串"""
        if self.type.lower() == "mysql":
            return f"mysql+pymysql://{self.username}:{self.password}@{self.host}:{self.port}/{self.database}?charset={self.charset}"
        elif self.type.lower() == "postgresql":
            return f"postgresql://{self.username}:{self.password}@{self.host}:{self.port}/{self.database}"
        elif self.type.lower() == "sqlite":
            return f"sqlite:///{self.database}"
        else:
            raise ValueError(f"不支持的数据库类型: {self.type}")


@dataclass
class BrowserConfig:
    """浏览器配置"""
    browser_type: BrowserType = BrowserType.CHROME
    headless: bool = False
    window_size: tuple = (1920, 1080)
    maximize_window: bool = True
    implicit_wait: int = 10
    page_load_timeout: int = 30
    script_timeout: int = 30
    download_dir: str = "downloads"
    enable_logging: bool = True
    log_level: str = "INFO"
    chrome_options: list = field(default_factory=list)
    firefox_options: list = field(default_factory=list)
    edge_options: list = field(default_factory=list)
    
    def get_chrome_options(self) -> list:
        """获取Chrome选项"""
        default_options = [
            "--no-sandbox",
            "--disable-dev-shm-usage",
            "--disable-gpu",
            "--disable-extensions"
        ]
        return default_options + self.chrome_options
    
    def get_firefox_options(self) -> list:
        """获取Firefox选项"""
        return self.firefox_options
    
    def get_edge_options(self) -> list:
        """获取Edge选项"""
        return self.edge_options


@dataclass
class ApiConfig:
    """API配置"""
    base_url: str = "http://localhost:8080"
    timeout: int = 30
    retry_count: int = 3
    retry_delay: int = 1
    verify_ssl: bool = True
    auth_type: str = "none"  # none, basic, bearer, api_key
    username: str = ""
    password: str = ""
    token: str = ""
    api_key: str = ""
    headers: dict = field(default_factory=dict)
    proxy: dict = field(default_factory=dict)
    
    def get_auth_headers(self) -> dict:
        """获取认证头"""
        headers = self.headers.copy()
        
        if self.auth_type == "bearer" and self.token:
            headers["Authorization"] = f"Bearer {self.token}"
        elif self.auth_type == "api_key" and self.api_key:
            headers["X-API-Key"] = self.api_key
        
        return headers


@dataclass
class ReportConfig:
    """报告配置"""
    output_dir: str = "reports"
    formats: list = field(default_factory=lambda: ["html", "json"])
    
    # HTML报告配置
    html_title: str = "自动化测试报告"
    html_description: str = "测试执行结果报告"
    html_theme: str = "default"
    
    # JSON报告配置
    json_indent: int = 2
    
    # Allure报告配置
    allure_results_dir: str = "allure-results"
    allure_report_dir: str = "allure-report"
    
    # 邮件报告配置
    email_enabled: bool = False
    email_recipients: list = field(default_factory=list)
    email_subject_template: str = "测试报告 - {status} - {timestamp}"
    email_send_on_failure: bool = True
    email_send_on_success: bool = False


@dataclass
class LogConfig:
    """日志配置"""
    level: LogLevel = LogLevel.INFO
    log_dir: str = "logs"
    log_format: str = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    date_format: str = "%Y-%m-%d %H:%M:%S"
    
    # 文件处理器配置
    file_handler_enabled: bool = True
    file_max_bytes: int = 10 * 1024 * 1024  # 10MB
    file_backup_count: int = 5
    
    # 控制台处理器配置
    console_handler_enabled: bool = True
    
    # 第三方库日志级别
    third_party_log_level: LogLevel = LogLevel.WARNING


@dataclass
class TestConfig:
    """测试配置"""
    parallel_mode: bool = False
    max_workers: int = 4
    retry_failed_tests: bool = True
    max_retry_count: int = 2
    test_timeout: int = 300
    
    # 测试发现配置
    test_patterns: list = field(default_factory=lambda: ["test_*.py", "*_test.py"])
    test_directories: list = field(default_factory=lambda: ["tests"])
    
    # 测试标签过滤
    include_tags: list = field(default_factory=list)
    exclude_tags: list = field(default_factory=list)
    
    # 测试数据配置
    test_data_dir: str = "test_data"
    test_data_formats: list = field(default_factory=lambda: ["json", "yaml", "csv"])


class ConfigManager:
    """配置管理器"""
    
    def __init__(self, config_dir: str = "config", environment: str = "local"):
        """
        初始化配置管理器
        
        Args:
            config_dir: 配置文件目录
            environment: 环境名称
        """
        self.config_dir = Path(config_dir)
        self.environment = environment
        self._config_cache: Dict[str, Any] = {}
        
        # 确保配置目录存在
        self.config_dir.mkdir(exist_ok=True)
        
        # 加载配置
        self._load_config()
    
    def _load_default_config(self) -> Dict[str, Any]:
        """加载默认配置"""
        return {
            "database": {
                "type": "mysql",
                "host": "localhost",
                "port": 3306,
                "username": "root",
                "password": "",
                "database": "test_db",
                "charset": "utf8mb4",
                "pool_size": 10,
                "max_overflow": 20,
                "pool_timeout": 30,
                "pool_recycle": 3600,
                "autocommit": True
            },
            "browser": {
                "browser_type": "chrome",
                "headless": False,
                "window_size": [1920, 1080],
                "maximize_window": True,
                "implicit_wait": 10,
                "page_load_timeout": 30,
                "script_timeout": 30,
                "download_dir": "downloads",
                "enable_logging": True,
                "log_level": "INFO",
                "chrome_options": [],
                "firefox_options": [],
                "edge_options": []
            },
            "api": {
                "base_url": "http://localhost:8080",
                "timeout": 30,
                "retry_count": 3,
                "retry_delay": 1,
                "verify_ssl": True,
                "auth_type": "none",
                "username": "",
                "password": "",
                "token": "",
                "api_key": "",
                "headers": {},
                "proxy": {}
            },
            "report": {
                "output_dir": "reports",
                "formats": ["html", "json"],
                "html_title": "自动化测试报告",
                "html_description": "测试执行结果报告",
                "html_theme": "default",
                "json_indent": 2,
                "allure_results_dir": "allure-results",
                "allure_report_dir": "allure-report",
                "email_enabled": False,
                "email_recipients": [],
                "email_subject_template": "测试报告 - {status} - {timestamp}",
                "email_send_on_failure": True,
                "email_send_on_success": False
            },
            "log": {
                "level": "INFO",
                "log_dir": "logs",
                "log_format": "%(asctime)s - %(name)s - %(levelname)s - %(message)s",
                "date_format": "%Y-%m-%d %H:%M:%S",
                "file_handler_enabled": True,
                "file_max_bytes": 10485760,
                "file_backup_count": 5,
                "console_handler_enabled": True,
                "third_party_log_level": "WARNING"
            },
            "test": {
                "parallel_mode": False,
                "max_workers": 4,
                "retry_failed_tests": True,
                "max_retry_count": 2,
                "test_timeout": 300,
                "test_patterns": ["test_*.py", "*_test.py"],
                "test_directories": ["tests"],
                "include_tags": [],
                "exclude_tags": [],
                "test_data_dir": "test_data",
                "test_data_formats": ["json", "yaml", "csv"]
            }
        }
    
    def _load_config_from_file(self, file_path: Path) -> Dict[str, Any]:
        """从文件加载配置"""
        if not file_path.exists():
            return {}
        
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                if file_path.suffix.lower() in ['.yml', '.yaml']:
                    return yaml.safe_load(f) or {}
                elif file_path.suffix.lower() == '.json':
                    return json.load(f) or {}
                else:
                    raise ValueError(f"不支持的配置文件格式: {file_path.suffix}")
        except Exception as e:
            print(f"加载配置文件失败 {file_path}: {e}")
            return {}
    
    def _load_config_from_env(self) -> Dict[str, Any]:
        """从环境变量加载配置"""
        env_config = {}
        
        # 数据库配置
        if os.getenv('DB_HOST'):
            env_config.setdefault('database', {})['host'] = os.getenv('DB_HOST')
        if os.getenv('DB_PORT'):
            env_config.setdefault('database', {})['port'] = int(os.getenv('DB_PORT'))
        if os.getenv('DB_USERNAME'):
            env_config.setdefault('database', {})['username'] = os.getenv('DB_USERNAME')
        if os.getenv('DB_PASSWORD'):
            env_config.setdefault('database', {})['password'] = os.getenv('DB_PASSWORD')
        if os.getenv('DB_DATABASE'):
            env_config.setdefault('database', {})['database'] = os.getenv('DB_DATABASE')
        
        # 浏览器配置
        if os.getenv('BROWSER_TYPE'):
            env_config.setdefault('browser', {})['browser_type'] = os.getenv('BROWSER_TYPE')
        if os.getenv('BROWSER_HEADLESS'):
            env_config.setdefault('browser', {})['headless'] = os.getenv('BROWSER_HEADLESS').lower() == 'true'
        
        # API配置
        if os.getenv('API_BASE_URL'):
            env_config.setdefault('api', {})['base_url'] = os.getenv('API_BASE_URL')
        if os.getenv('API_TOKEN'):
            env_config.setdefault('api', {})['token'] = os.getenv('API_TOKEN')
        
        return env_config
    
    def _merge_configs(self, *configs: Dict[str, Any]) -> Dict[str, Any]:
        """合并多个配置字典"""
        result = {}
        
        for config in configs:
            for key, value in config.items():
                if key in result and isinstance(result[key], dict) and isinstance(value, dict):
                    result[key] = self._merge_configs(result[key], value)
                else:
                    result[key] = value
        
        return result
    
    def _load_config(self):
        """加载配置"""
        # 1. 加载默认配置
        default_config = self._load_default_config()
        
        # 2. 加载通用配置文件
        common_config_file = self.config_dir / "config.yaml"
        common_config = self._load_config_from_file(common_config_file)
        
        # 3. 加载环境特定配置文件
        env_config_file = self.config_dir / f"{self.environment}.yaml"
        env_config = self._load_config_from_file(env_config_file)
        
        # 4. 加载环境变量配置
        env_var_config = self._load_config_from_env()
        
        # 5. 合并所有配置（优先级：环境变量 > 环境配置 > 通用配置 > 默认配置）
        self._config_cache = self._merge_configs(
            default_config,
            common_config,
            env_config,
            env_var_config
        )
    
    def get_database_config(self) -> DatabaseConfig:
        """获取数据库配置"""
        db_config = self._config_cache.get('database', {})
        return DatabaseConfig(**db_config)
    
    def get_browser_config(self) -> BrowserConfig:
        """获取浏览器配置"""
        browser_config = self._config_cache.get('browser', {})
        
        # 转换browser_type字符串为枚举
        if 'browser_type' in browser_config:
            browser_type_str = browser_config['browser_type']
            if isinstance(browser_type_str, str):
                browser_config['browser_type'] = BrowserType(browser_type_str.lower())
        
        # 转换window_size列表为元组
        if 'window_size' in browser_config and isinstance(browser_config['window_size'], list):
            browser_config['window_size'] = tuple(browser_config['window_size'])
        
        return BrowserConfig(**browser_config)
    
    def get_api_config(self) -> ApiConfig:
        """获取API配置"""
        api_config = self._config_cache.get('api', {})
        return ApiConfig(**api_config)
    
    def get_report_config(self) -> ReportConfig:
        """获取报告配置"""
        report_config = self._config_cache.get('report', {})
        return ReportConfig(**report_config)
    
    def get_log_config(self) -> LogConfig:
        """获取日志配置"""
        log_config = self._config_cache.get('log', {})
        
        # 转换level字符串为枚举
        if 'level' in log_config and isinstance(log_config['level'], str):
            log_config['level'] = LogLevel(log_config['level'].upper())
        
        if 'third_party_log_level' in log_config and isinstance(log_config['third_party_log_level'], str):
            log_config['third_party_log_level'] = LogLevel(log_config['third_party_log_level'].upper())
        
        return LogConfig(**log_config)
    
    def get_test_config(self) -> TestConfig:
        """获取测试配置"""
        test_config = self._config_cache.get('test', {})
        return TestConfig(**test_config)
    
    def get_config(self, key: str, default: Any = None) -> Any:
        """获取配置值"""
        keys = key.split('.')
        value = self._config_cache
        
        for k in keys:
            if isinstance(value, dict) and k in value:
                value = value[k]
            else:
                return default
        
        return value
    
    def set_config(self, key: str, value: Any):
        """设置配置值"""
        keys = key.split('.')
        config = self._config_cache
        
        for k in keys[:-1]:
            if k not in config:
                config[k] = {}
            config = config[k]
        
        config[keys[-1]] = value
    
    def save_config(self, file_path: Optional[Union[str, Path]] = None):
        """保存配置到文件"""
        if file_path is None:
            file_path = self.config_dir / f"{self.environment}.yaml"
        else:
            file_path = Path(file_path)
        
        # 确保目录存在
        file_path.parent.mkdir(parents=True, exist_ok=True)
        
        try:
            with open(file_path, 'w', encoding='utf-8') as f:
                yaml.dump(self._config_cache, f, default_flow_style=False, allow_unicode=True, indent=2)
            print(f"配置已保存到: {file_path}")
        except Exception as e:
            print(f"保存配置文件失败: {e}")
    
    def create_default_configs(self):
        """创建默认配置文件"""
        # 创建主配置文件
        main_config = {
            "# 主配置文件": None,
            "# 通用配置，所有环境共享": None,
            "database": {
                "type": "mysql",
                "charset": "utf8mb4",
                "pool_size": 10,
                "max_overflow": 20,
                "pool_timeout": 30,
                "pool_recycle": 3600,
                "autocommit": True
            },
            "browser": {
                "window_size": [1920, 1080],
                "maximize_window": True,
                "implicit_wait": 10,
                "page_load_timeout": 30,
                "script_timeout": 30,
                "enable_logging": True,
                "log_level": "INFO"
            },
            "api": {
                "timeout": 30,
                "retry_count": 3,
                "retry_delay": 1,
                "verify_ssl": True,
                "auth_type": "none"
            },
            "report": {
                "output_dir": "reports",
                "formats": ["html", "json"],
                "html_title": "自动化测试报告",
                "html_description": "测试执行结果报告",
                "html_theme": "default",
                "json_indent": 2,
                "allure_results_dir": "allure-results",
                "allure_report_dir": "allure-report"
            },
            "log": {
                "level": "INFO",
                "log_dir": "logs",
                "log_format": "%(asctime)s - %(name)s - %(levelname)s - %(message)s",
                "date_format": "%Y-%m-%d %H:%M:%S",
                "file_handler_enabled": True,
                "file_max_bytes": 10485760,
                "file_backup_count": 5,
                "console_handler_enabled": True,
                "third_party_log_level": "WARNING"
            },
            "test": {
                "parallel_mode": False,
                "max_workers": 4,
                "retry_failed_tests": True,
                "max_retry_count": 2,
                "test_timeout": 300,
                "test_patterns": ["test_*.py", "*_test.py"],
                "test_directories": ["tests"],
                "test_data_dir": "test_data",
                "test_data_formats": ["json", "yaml", "csv"]
            }
        }
        
        # 保存主配置文件
        main_config_file = self.config_dir / "config.yaml"
        with open(main_config_file, 'w', encoding='utf-8') as f:
            yaml.dump(main_config, f, default_flow_style=False, allow_unicode=True, indent=2)
        
        # 创建环境特定配置文件
        environments = {
            "local": {
                "# 本地开发环境配置": None,
                "database": {
                    "host": "localhost",
                    "port": 3306,
                    "username": "root",
                    "password": "",
                    "database": "test_db"
                },
                "browser": {
                    "browser_type": "chrome",
                    "headless": False,
                    "download_dir": "downloads"
                },
                "api": {
                    "base_url": "http://localhost:8080"
                }
            },
            "test": {
                "# 测试环境配置": None,
                "database": {
                    "host": "test-db.example.com",
                    "port": 3306,
                    "username": "test_user",
                    "password": "test_password",
                    "database": "test_db"
                },
                "browser": {
                    "browser_type": "chrome",
                    "headless": True,
                    "download_dir": "/tmp/downloads"
                },
                "api": {
                    "base_url": "https://test-api.example.com"
                }
            },
            "prod": {
                "# 生产环境配置": None,
                "database": {
                    "host": "prod-db.example.com",
                    "port": 3306,
                    "username": "prod_user",
                    "password": "${DB_PASSWORD}",  # 使用环境变量
                    "database": "prod_db"
                },
                "browser": {
                    "browser_type": "chrome",
                    "headless": True,
                    "download_dir": "/tmp/downloads"
                },
                "api": {
                    "base_url": "https://api.example.com",
                    "auth_type": "bearer",
                    "token": "${API_TOKEN}"  # 使用环境变量
                }
            }
        }
        
        for env_name, env_config in environments.items():
            env_config_file = self.config_dir / f"{env_name}.yaml"
            with open(env_config_file, 'w', encoding='utf-8') as f:
                yaml.dump(env_config, f, default_flow_style=False, allow_unicode=True, indent=2)
        
        print(f"默认配置文件已创建在: {self.config_dir}")
    
    def validate_config(self) -> bool:
        """验证配置的有效性"""
        try:
            # 验证数据库配置
            db_config = self.get_database_config()
            if not db_config.host or not db_config.username:
                print("数据库配置无效：缺少主机或用户名")
                return False
            
            # 验证API配置
            api_config = self.get_api_config()
            if not api_config.base_url:
                print("API配置无效：缺少基础URL")
                return False
            
            # 验证报告配置
            report_config = self.get_report_config()
            if not report_config.output_dir:
                print("报告配置无效：缺少输出目录")
                return False
            
            return True
            
        except Exception as e:
            print(f"配置验证失败: {e}")
            return False
    
    def get_environment_info(self) -> Dict[str, Any]:
        """获取环境信息"""
        return {
            "environment": self.environment,
            "config_dir": str(self.config_dir),
            "config_files": [
                str(f) for f in self.config_dir.glob("*.yaml")
                if f.is_file()
            ]
        }


# 全局配置管理器实例
_config_manager: Optional[ConfigManager] = None


def get_config_manager(config_dir: str = "config", environment: str = "local") -> ConfigManager:
    """获取配置管理器实例"""
    global _config_manager
    if _config_manager is None:
        _config_manager = ConfigManager(config_dir, environment)
    return _config_manager


def get_database_config() -> DatabaseConfig:
    """获取数据库配置"""
    return get_config_manager().get_database_config()


def get_browser_config() -> BrowserConfig:
    """获取浏览器配置"""
    return get_config_manager().get_browser_config()


def get_api_config() -> ApiConfig:
    """获取API配置"""
    return get_config_manager().get_api_config()


def get_report_config() -> ReportConfig:
    """获取报告配置"""
    return get_config_manager().get_report_config()


def get_log_config() -> LogConfig:
    """获取日志配置"""
    return get_config_manager().get_log_config()


def get_test_config() -> TestConfig:
    """获取测试配置"""
    return get_config_manager().get_test_config()


if __name__ == "__main__":
    # 使用示例
    config_manager = ConfigManager()
    
    # 创建默认配置文件
    config_manager.create_default_configs()
    
    # 获取各种配置
    db_config = config_manager.get_database_config()
    browser_config = config_manager.get_browser_config()
    api_config = config_manager.get_api_config()
    
    print(f"数据库连接字符串: {db_config.get_connection_string()}")
    print(f"浏览器类型: {browser_config.browser_type.value}")
    print(f"API基础URL: {api_config.base_url}")