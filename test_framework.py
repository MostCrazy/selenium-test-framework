#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
自动化测试框架主入口
整合所有组件，提供统一的测试框架接口
"""

import os
import sys
import argparse
import logging
from typing import Dict, List, Any, Optional
from pathlib import Path
from datetime import datetime
import json
import yaml

# 添加项目根目录到Python路径
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from utils.config_manager import (
    ConfigManager, Environment, BrowserType,
    get_config_manager
)
from utils.logger_setup import setup_logger
from utils.test_executor import TestExecutor, ExecutionMode as TestExecutionMode
from utils.test_data_manager import TestDataManager, DataSource, create_user_schema, create_product_schema
from utils.report_generator import ReportGenerator
from utils.browser_manager import BrowserManager
from utils.api_client import APIClient
from utils.database_helper import DatabaseHelper


class TestFramework:
    """自动化测试框架主类"""
    
    def __init__(self, config_dir: str = "config", environment: Environment = None):
        """初始化测试框架"""
        self.config_dir = Path(config_dir)
        self.environment = environment or self._detect_environment()
        
        # 初始化配置管理器
        self.config_manager = ConfigManager(str(self.config_dir), self.environment)
        
        # 设置日志
        self.logger = setup_logger(self.config_manager.get_logging_config())
        self.logger.info(f"测试框架初始化，环境: {self.environment.value}")
        
        # 初始化各个组件
        self._initialize_components()
        
        # 框架状态
        self.initialized = True
        self.start_time = None
        self.end_time = None
    
    def _detect_environment(self) -> Environment:
        """检测运行环境"""
        env_name = os.getenv('TEST_ENV', 'local').lower()
        try:
            return Environment(env_name)
        except ValueError:
            return Environment.LOCAL
    
    def _initialize_components(self):
        """初始化框架组件"""
        try:
            # 获取配置
            self.test_config = self.config_manager.get_test_config()
            self.browser_config = self.config_manager.get_browser_config()
            self.api_config = self.config_manager.get_api_config()
            self.db_config = self.config_manager.get_database_config()
            self.report_config = self.config_manager.get_report_config()
            
            # 初始化组件
            self.test_executor = TestExecutor(str(self.config_dir))
            self.data_manager = TestDataManager(self.test_config.test_data_dir)
            self.report_generator = ReportGenerator()
            
            # 可选组件（按需初始化）
            self.browser_manager = None
            self.api_client = None
            self.db_helper = None
            
            self.logger.info("框架组件初始化完成")
            
        except Exception as e:
            self.logger.error(f"组件初始化失败: {e}")
            raise
    
    def setup(self):
        """框架设置"""
        try:
            self.logger.info("开始框架设置")
            
            # 创建必要的目录
            self._create_directories()
            
            # 初始化数据模式
            self._setup_data_schemas()
            
            # 验证配置
            self._validate_configuration()
            
            self.logger.info("框架设置完成")
            
        except Exception as e:
            self.logger.error(f"框架设置失败: {e}")
            raise
    
    def _create_directories(self):
        """创建必要的目录"""
        directories = [
            self.test_config.test_data_dir,
            self.test_config.test_output_dir,
            self.report_config.output_dir,
            self.config_manager.get_logging_config().log_dir,
            "screenshots",
            "videos",
            "allure-results",
            "temp"
        ]
        
        for directory in directories:
            Path(directory).mkdir(parents=True, exist_ok=True)
            self.logger.debug(f"创建目录: {directory}")
    
    def _setup_data_schemas(self):
        """设置数据模式"""
        try:
            # 创建预定义的数据模式
            user_schema = create_user_schema()
            product_schema = create_product_schema()
            
            self.data_manager.create_schema(user_schema)
            self.data_manager.create_schema(product_schema)
            
            self.logger.info("数据模式设置完成")
            
        except Exception as e:
            self.logger.warning(f"数据模式设置失败: {e}")
    
    def _validate_configuration(self):
        """验证配置"""
        validation_errors = self.config_manager.validate_config()
        if validation_errors:
            self.logger.warning(f"配置验证发现问题: {validation_errors}")
        else:
            self.logger.info("配置验证通过")
    
    def get_browser_manager(self) -> BrowserManager:
        """获取浏览器管理器"""
        if self.browser_manager is None:
            self.browser_manager = BrowserManager(self.browser_config)
        return self.browser_manager
    
    def get_api_client(self) -> APIClient:
        """获取API客户端"""
        if self.api_client is None:
            self.api_client = APIClient(self.api_config)
        return self.api_client
    
    def get_database_helper(self) -> DatabaseHelper:
        """获取数据库助手"""
        if self.db_helper is None:
            self.db_helper = DatabaseHelper(self.db_config)
        return self.db_helper
    
    def discover_tests(self, test_dirs: List[str] = None, 
                      test_pattern: str = "test_*.py",
                      framework: str = "pytest") -> List:
        """发现测试用例"""
        if test_dirs is None:
            test_dirs = ["tests"]
        
        return self.test_executor.discover_tests(test_dirs, test_pattern, framework)
    
    def run_tests(self, test_cases: List = None,
                 test_dirs: List[str] = None,
                 execution_mode: str = "sequential",
                 tags: List[str] = None,
                 markers: List[str] = None,
                 pattern: str = None,
                 generate_report: bool = True) -> Dict[str, Any]:
        """运行测试"""
        self.start_time = datetime.now()
        
        try:
            # 如果没有提供测试用例，则发现测试
            if test_cases is None:
                if test_dirs is None:
                    test_dirs = ["tests"]
                test_cases = self.discover_tests(test_dirs)
            
            if not test_cases:
                self.logger.warning("没有找到要执行的测试用例")
                return {'success': False, 'message': '没有找到测试用例'}
            
            # 转换执行模式
            exec_mode = self._convert_execution_mode(execution_mode)
            
            # 执行测试
            results = self.test_executor.execute_tests(
                test_cases=test_cases,
                execution_mode=exec_mode,
                tags=tags,
                markers=markers,
                pattern=pattern
            )
            
            self.end_time = datetime.now()
            
            # 生成报告
            reports = {}
            if generate_report and results:
                reports = self.test_executor.generate_reports(results)
            
            # 计算统计信息
            stats = self._calculate_test_stats(results)
            
            return {
                'success': True,
                'stats': stats,
                'results': results,
                'reports': reports,
                'execution_time': (self.end_time - self.start_time).total_seconds()
            }
            
        except Exception as e:
            self.logger.error(f"测试执行失败: {e}")
            return {'success': False, 'message': str(e)}
    
    def _convert_execution_mode(self, mode: str) -> TestExecutionMode:
        """转换执行模式"""
        mode_map = {
            'sequential': TestExecutionMode.SEQUENTIAL,
            'parallel_thread': TestExecutionMode.PARALLEL_THREAD,
            'parallel_process': TestExecutionMode.PARALLEL_PROCESS,
            'distributed': TestExecutionMode.DISTRIBUTED
        }
        return mode_map.get(mode.lower(), TestExecutionMode.SEQUENTIAL)
    
    def _calculate_test_stats(self, results: List) -> Dict[str, Any]:
        """计算测试统计信息"""
        if not results:
            return {}
        
        total = len(results)
        passed = sum(1 for r in results if r.passed)
        failed = sum(1 for r in results if r.failed)
        skipped = sum(1 for r in results if r.skipped)
        
        return {
            'total': total,
            'passed': passed,
            'failed': failed,
            'skipped': skipped,
            'pass_rate': (passed / total * 100) if total > 0 else 0,
            'total_duration': sum(r.duration for r in results)
        }
    
    def generate_test_data(self, schema_name: str, count: int = 10, 
                          format: str = "json") -> Optional[str]:
        """生成测试数据"""
        try:
            data_source = DataSource(format.lower())
            return self.data_manager.generate_data(schema_name, count, data_source)
        except Exception as e:
            self.logger.error(f"生成测试数据失败: {e}")
            return None
    
    def load_test_data(self, file_path: str, cache_key: str = None) -> List[Dict[str, Any]]:
        """加载测试数据"""
        return self.data_manager.load_test_data(file_path, cache_key)
    
    def cleanup(self):
        """清理资源"""
        try:
            self.logger.info("开始清理框架资源")
            
            # 关闭浏览器
            if self.browser_manager:
                self.browser_manager.quit_all_drivers()
            
            # 关闭数据库连接
            if self.db_helper:
                self.db_helper.close_connection()
            
            # 清理临时数据
            if hasattr(self, 'data_manager'):
                self.data_manager.cleanup_temp_data()
            
            self.logger.info("框架资源清理完成")
            
        except Exception as e:
            self.logger.error(f"清理资源失败: {e}")
    
    def get_framework_info(self) -> Dict[str, Any]:
        """获取框架信息"""
        return {
            'version': '1.0.0',
            'environment': self.environment.value,
            'config_dir': str(self.config_dir),
            'initialized': self.initialized,
            'start_time': self.start_time.isoformat() if self.start_time else None,
            'end_time': self.end_time.isoformat() if self.end_time else None,
            'components': {
                'browser_manager': self.browser_manager is not None,
                'api_client': self.api_client is not None,
                'db_helper': self.db_helper is not None
            }
        }
    
    def create_default_config(self):
        """创建默认配置"""
        self.config_manager.create_default_configs()
        self.logger.info("默认配置已创建")


def create_cli_parser() -> argparse.ArgumentParser:
    """创建命令行参数解析器"""
    parser = argparse.ArgumentParser(
        description="自动化测试框架",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例用法:
  python test_framework.py --discover tests/
  python test_framework.py --run tests/ --mode parallel_thread
  python test_framework.py --run tests/ --tags smoke --generate-data user 50
  python test_framework.py --init-config
        """
    )
    
    # 基本选项
    parser.add_argument('--env', choices=['local', 'dev', 'test', 'staging', 'prod'],
                       default='local', help='运行环境')
    parser.add_argument('--config-dir', default='config', help='配置目录')
    parser.add_argument('--log-level', choices=['DEBUG', 'INFO', 'WARNING', 'ERROR'],
                       default='INFO', help='日志级别')
    
    # 测试发现和执行
    parser.add_argument('--discover', nargs='+', metavar='DIR',
                       help='发现指定目录中的测试')
    parser.add_argument('--run', nargs='+', metavar='DIR',
                       help='运行指定目录中的测试')
    parser.add_argument('--pattern', default='test_*.py',
                       help='测试文件模式')
    parser.add_argument('--framework', choices=['pytest', 'unittest'],
                       default='pytest', help='测试框架')
    
    # 执行选项
    parser.add_argument('--mode', choices=['sequential', 'parallel_thread', 'parallel_process'],
                       default='sequential', help='执行模式')
    parser.add_argument('--workers', type=int, default=1,
                       help='并行工作进程数')
    parser.add_argument('--tags', nargs='+', help='按标签过滤测试')
    parser.add_argument('--markers', nargs='+', help='按标记过滤测试')
    parser.add_argument('--filter', help='按模式过滤测试')
    
    # 报告选项
    parser.add_argument('--no-report', action='store_true',
                       help='不生成测试报告')
    parser.add_argument('--report-dir', default='reports',
                       help='报告输出目录')
    
    # 数据管理
    parser.add_argument('--generate-data', nargs=2, metavar=('SCHEMA', 'COUNT'),
                       help='生成测试数据 (模式名称 数量)')
    parser.add_argument('--data-format', choices=['json', 'csv', 'yaml', 'excel'],
                       default='json', help='数据格式')
    
    # 配置管理
    parser.add_argument('--init-config', action='store_true',
                       help='初始化默认配置')
    parser.add_argument('--validate-config', action='store_true',
                       help='验证配置')
    
    # 其他选项
    parser.add_argument('--info', action='store_true',
                       help='显示框架信息')
    parser.add_argument('--cleanup', action='store_true',
                       help='清理临时文件')
    
    return parser


def main():
    """主函数"""
    parser = create_cli_parser()
    args = parser.parse_args()
    
    # 设置环境
    try:
        environment = Environment(args.env)
    except ValueError:
        print(f"无效的环境: {args.env}")
        return 1
    
    # 初始化框架
    try:
        framework = TestFramework(args.config_dir, environment)
        
        # 设置日志级别
        logging.getLogger().setLevel(getattr(logging, args.log_level))
        
        # 执行命令
        if args.init_config:
            framework.create_default_config()
            print("默认配置已创建")
            return 0
        
        if args.validate_config:
            errors = framework.config_manager.validate_config()
            if errors:
                print(f"配置验证失败: {errors}")
                return 1
            else:
                print("配置验证通过")
                return 0
        
        if args.info:
            info = framework.get_framework_info()
            print(json.dumps(info, indent=2, ensure_ascii=False))
            return 0
        
        if args.cleanup:
            framework.cleanup()
            print("清理完成")
            return 0
        
        # 设置框架
        framework.setup()
        
        if args.generate_data:
            schema_name, count = args.generate_data
            file_path = framework.generate_test_data(
                schema_name, int(count), args.data_format
            )
            if file_path:
                print(f"测试数据已生成: {file_path}")
            else:
                print("生成测试数据失败")
                return 1
        
        if args.discover:
            test_cases = framework.discover_tests(
                args.discover, args.pattern, args.framework
            )
            print(f"发现 {len(test_cases)} 个测试用例:")
            for tc in test_cases:
                print(f"  - {tc.name} ({tc.file_path})")
        
        if args.run:
            result = framework.run_tests(
                test_dirs=args.run,
                execution_mode=args.mode,
                tags=args.tags,
                markers=args.markers,
                pattern=args.filter,
                generate_report=not args.no_report
            )
            
            if result['success']:
                stats = result['stats']
                print(f"\n测试执行完成:")
                print(f"总计: {stats['total']}, 通过: {stats['passed']}, 失败: {stats['failed']}, 跳过: {stats['skipped']}")
                print(f"通过率: {stats['pass_rate']:.1f}%")
                print(f"执行时间: {result['execution_time']:.2f}s")
                
                if result['reports']:
                    print(f"\n生成的报告:")
                    for report_type, report_path in result['reports'].items():
                        print(f"  {report_type}: {report_path}")
                
                return 0 if stats['failed'] == 0 else 1
            else:
                print(f"测试执行失败: {result['message']}")
                return 1
        
        # 如果没有指定任何操作，显示帮助
        if not any([args.discover, args.run, args.generate_data, args.init_config, 
                   args.validate_config, args.info, args.cleanup]):
            parser.print_help()
            return 0
        
    except KeyboardInterrupt:
        print("\n用户中断执行")
        return 130
    except Exception as e:
        print(f"执行失败: {e}")
        return 1
    finally:
        # 清理资源
        if 'framework' in locals():
            framework.cleanup()


if __name__ == "__main__":
    sys.exit(main())