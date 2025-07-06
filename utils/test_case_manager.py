#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
测试用例管理器
用于动态生成、管理和执行测试用例
"""

import os
import json
import yaml
import inspect
import importlib
from typing import List, Dict, Any, Callable, Optional, Type, Union
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
import logging
from datetime import datetime
import pytest
import allure

from .data_provider import DataManager, load_test_data


class TestPriority(Enum):
    """测试优先级"""
    LOW = 1
    MEDIUM = 2
    HIGH = 3
    CRITICAL = 4


class TestType(Enum):
    """测试类型"""
    SMOKE = "smoke"
    REGRESSION = "regression"
    INTEGRATION = "integration"
    UNIT = "unit"
    API = "api"
    UI = "ui"
    PERFORMANCE = "performance"
    SECURITY = "security"


class TestStatus(Enum):
    """测试状态"""
    PENDING = "pending"
    RUNNING = "running"
    PASSED = "passed"
    FAILED = "failed"
    SKIPPED = "skipped"
    BLOCKED = "blocked"


@dataclass
class TestCase:
    """测试用例数据类"""
    id: str
    name: str
    description: str
    test_function: Callable
    priority: TestPriority = TestPriority.MEDIUM
    test_type: TestType = TestType.REGRESSION
    tags: List[str] = field(default_factory=list)
    data: Dict[str, Any] = field(default_factory=dict)
    preconditions: List[str] = field(default_factory=list)
    postconditions: List[str] = field(default_factory=list)
    expected_result: str = ""
    timeout: int = 300
    retry_count: int = 0
    dependencies: List[str] = field(default_factory=list)
    status: TestStatus = TestStatus.PENDING
    execution_time: float = 0.0
    error_message: str = ""
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)


@dataclass
class TestSuite:
    """测试套件数据类"""
    id: str
    name: str
    description: str
    test_cases: List[TestCase] = field(default_factory=list)
    setup_function: Optional[Callable] = None
    teardown_function: Optional[Callable] = None
    parallel: bool = False
    max_workers: int = 1
    tags: List[str] = field(default_factory=list)
    created_at: datetime = field(default_factory=datetime.now)


class TestCaseBuilder:
    """测试用例构建器"""
    
    def __init__(self):
        self._test_case = TestCase(
            id="",
            name="",
            description="",
            test_function=lambda: None
        )
    
    def with_id(self, test_id: str) -> 'TestCaseBuilder':
        """设置测试用例ID"""
        self._test_case.id = test_id
        return self
    
    def with_name(self, name: str) -> 'TestCaseBuilder':
        """设置测试用例名称"""
        self._test_case.name = name
        return self
    
    def with_description(self, description: str) -> 'TestCaseBuilder':
        """设置测试用例描述"""
        self._test_case.description = description
        return self
    
    def with_function(self, test_function: Callable) -> 'TestCaseBuilder':
        """设置测试函数"""
        self._test_case.test_function = test_function
        return self
    
    def with_priority(self, priority: TestPriority) -> 'TestCaseBuilder':
        """设置测试优先级"""
        self._test_case.priority = priority
        return self
    
    def with_type(self, test_type: TestType) -> 'TestCaseBuilder':
        """设置测试类型"""
        self._test_case.test_type = test_type
        return self
    
    def with_tags(self, tags: List[str]) -> 'TestCaseBuilder':
        """设置测试标签"""
        self._test_case.tags = tags
        return self
    
    def with_data(self, data: Dict[str, Any]) -> 'TestCaseBuilder':
        """设置测试数据"""
        self._test_case.data = data
        return self
    
    def with_timeout(self, timeout: int) -> 'TestCaseBuilder':
        """设置超时时间"""
        self._test_case.timeout = timeout
        return self
    
    def with_retry(self, retry_count: int) -> 'TestCaseBuilder':
        """设置重试次数"""
        self._test_case.retry_count = retry_count
        return self
    
    def with_dependencies(self, dependencies: List[str]) -> 'TestCaseBuilder':
        """设置依赖项"""
        self._test_case.dependencies = dependencies
        return self
    
    def build(self) -> TestCase:
        """构建测试用例"""
        if not self._test_case.id:
            self._test_case.id = f"test_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        
        if not self._test_case.name:
            self._test_case.name = self._test_case.test_function.__name__
        
        return self._test_case


class TestCaseManager:
    """测试用例管理器"""
    
    def __init__(self):
        self.test_cases: Dict[str, TestCase] = {}
        self.test_suites: Dict[str, TestSuite] = {}
        self.data_manager = DataManager()
        self.logger = logging.getLogger(__name__)
    
    def register_test_case(self, test_case: TestCase) -> None:
        """注册测试用例"""
        self.test_cases[test_case.id] = test_case
        self.logger.info(f"注册测试用例: {test_case.id} - {test_case.name}")
    
    def register_test_suite(self, test_suite: TestSuite) -> None:
        """注册测试套件"""
        self.test_suites[test_suite.id] = test_suite
        
        # 注册套件中的所有测试用例
        for test_case in test_suite.test_cases:
            self.register_test_case(test_case)
        
        self.logger.info(f"注册测试套件: {test_suite.id} - {test_suite.name}")
    
    def get_test_case(self, test_id: str) -> Optional[TestCase]:
        """获取测试用例"""
        return self.test_cases.get(test_id)
    
    def get_test_suite(self, suite_id: str) -> Optional[TestSuite]:
        """获取测试套件"""
        return self.test_suites.get(suite_id)
    
    def filter_test_cases(self, **filters) -> List[TestCase]:
        """过滤测试用例
        
        支持的过滤条件:
        - priority: 测试优先级
        - test_type: 测试类型
        - tags: 标签列表
        - status: 测试状态
        """
        filtered_cases = list(self.test_cases.values())
        
        if 'priority' in filters:
            priority = filters['priority']
            if isinstance(priority, str):
                priority = TestPriority[priority.upper()]
            filtered_cases = [tc for tc in filtered_cases if tc.priority == priority]
        
        if 'test_type' in filters:
            test_type = filters['test_type']
            if isinstance(test_type, str):
                test_type = TestType(test_type.lower())
            filtered_cases = [tc for tc in filtered_cases if tc.test_type == test_type]
        
        if 'tags' in filters:
            required_tags = filters['tags']
            if isinstance(required_tags, str):
                required_tags = [required_tags]
            filtered_cases = [tc for tc in filtered_cases 
                            if any(tag in tc.tags for tag in required_tags)]
        
        if 'status' in filters:
            status = filters['status']
            if isinstance(status, str):
                status = TestStatus(status.lower())
            filtered_cases = [tc for tc in filtered_cases if tc.status == status]
        
        return filtered_cases
    
    def create_test_case_from_data(self, test_data: Dict[str, Any], 
                                 test_function: Callable) -> TestCase:
        """从数据创建测试用例"""
        builder = TestCaseBuilder()
        
        builder.with_id(test_data.get('id', ''))
        builder.with_name(test_data.get('name', ''))
        builder.with_description(test_data.get('description', ''))
        builder.with_function(test_function)
        
        if 'priority' in test_data:
            priority_str = test_data['priority'].upper()
            if hasattr(TestPriority, priority_str):
                builder.with_priority(TestPriority[priority_str])
        
        if 'test_type' in test_data:
            test_type_str = test_data['test_type'].lower()
            if hasattr(TestType, test_type_str.upper()):
                builder.with_type(TestType(test_type_str))
        
        if 'tags' in test_data:
            builder.with_tags(test_data['tags'])
        
        if 'timeout' in test_data:
            builder.with_timeout(test_data['timeout'])
        
        if 'retry_count' in test_data:
            builder.with_retry(test_data['retry_count'])
        
        # 将所有数据作为测试数据
        builder.with_data(test_data)
        
        return builder.build()
    
    def load_test_cases_from_file(self, file_path: str, 
                                test_function: Callable) -> List[TestCase]:
        """从文件加载测试用例"""
        test_data_list = self.data_manager.load_data(file_path)
        test_cases = []
        
        for test_data in test_data_list:
            test_case = self.create_test_case_from_data(test_data, test_function)
            test_cases.append(test_case)
            self.register_test_case(test_case)
        
        return test_cases
    
    def generate_pytest_cases(self, test_cases: List[TestCase]) -> List[tuple]:
        """为pytest生成参数化测试用例"""
        pytest_cases = []
        
        for test_case in test_cases:
            # 创建包含测试用例信息的元组
            case_data = (
                test_case.data,
                test_case.id,
                test_case.name,
                test_case.description,
                test_case.expected_result
            )
            pytest_cases.append(case_data)
        
        return pytest_cases
    
    def execute_test_case(self, test_case: TestCase, **kwargs) -> bool:
        """执行单个测试用例"""
        try:
            test_case.status = TestStatus.RUNNING
            start_time = datetime.now()
            
            # 执行测试函数
            result = test_case.test_function(test_case.data, **kwargs)
            
            end_time = datetime.now()
            test_case.execution_time = (end_time - start_time).total_seconds()
            test_case.status = TestStatus.PASSED
            test_case.updated_at = end_time
            
            self.logger.info(f"测试用例 {test_case.id} 执行成功")
            return True
            
        except Exception as e:
            test_case.status = TestStatus.FAILED
            test_case.error_message = str(e)
            test_case.updated_at = datetime.now()
            
            self.logger.error(f"测试用例 {test_case.id} 执行失败: {e}")
            return False
    
    def execute_test_suite(self, test_suite: TestSuite, **kwargs) -> Dict[str, bool]:
        """执行测试套件"""
        results = {}
        
        try:
            # 执行setup
            if test_suite.setup_function:
                test_suite.setup_function()
            
            # 执行测试用例
            for test_case in test_suite.test_cases:
                result = self.execute_test_case(test_case, **kwargs)
                results[test_case.id] = result
            
        finally:
            # 执行teardown
            if test_suite.teardown_function:
                test_suite.teardown_function()
        
        return results
    
    def get_test_statistics(self) -> Dict[str, Any]:
        """获取测试统计信息"""
        total_cases = len(self.test_cases)
        
        status_counts = {}
        for status in TestStatus:
            count = len([tc for tc in self.test_cases.values() if tc.status == status])
            status_counts[status.value] = count
        
        priority_counts = {}
        for priority in TestPriority:
            count = len([tc for tc in self.test_cases.values() if tc.priority == priority])
            priority_counts[priority.name.lower()] = count
        
        type_counts = {}
        for test_type in TestType:
            count = len([tc for tc in self.test_cases.values() if tc.test_type == test_type])
            type_counts[test_type.value] = count
        
        return {
            'total_cases': total_cases,
            'total_suites': len(self.test_suites),
            'status_distribution': status_counts,
            'priority_distribution': priority_counts,
            'type_distribution': type_counts
        }
    
    def export_test_cases(self, file_path: str, format: str = 'json') -> bool:
        """导出测试用例"""
        try:
            export_data = []
            
            for test_case in self.test_cases.values():
                case_data = {
                    'id': test_case.id,
                    'name': test_case.name,
                    'description': test_case.description,
                    'priority': test_case.priority.name.lower(),
                    'test_type': test_case.test_type.value,
                    'tags': test_case.tags,
                    'data': test_case.data,
                    'timeout': test_case.timeout,
                    'retry_count': test_case.retry_count,
                    'status': test_case.status.value,
                    'execution_time': test_case.execution_time,
                    'created_at': test_case.created_at.isoformat(),
                    'updated_at': test_case.updated_at.isoformat()
                }
                export_data.append(case_data)
            
            return self.data_manager.save_data(export_data, file_path)
            
        except Exception as e:
            self.logger.error(f"导出测试用例失败: {e}")
            return False
    
    def import_test_cases(self, file_path: str) -> bool:
        """导入测试用例"""
        try:
            import_data = self.data_manager.load_data(file_path)
            
            for case_data in import_data:
                # 创建一个虚拟的测试函数
                def dummy_test_function(data):
                    pass
                
                test_case = self.create_test_case_from_data(case_data, dummy_test_function)
                
                # 恢复状态和时间信息
                if 'status' in case_data:
                    test_case.status = TestStatus(case_data['status'])
                
                if 'execution_time' in case_data:
                    test_case.execution_time = case_data['execution_time']
                
                if 'created_at' in case_data:
                    test_case.created_at = datetime.fromisoformat(case_data['created_at'])
                
                if 'updated_at' in case_data:
                    test_case.updated_at = datetime.fromisoformat(case_data['updated_at'])
                
                self.register_test_case(test_case)
            
            return True
            
        except Exception as e:
            self.logger.error(f"导入测试用例失败: {e}")
            return False
    
    def clear_all(self):
        """清空所有测试用例和套件"""
        self.test_cases.clear()
        self.test_suites.clear()
        self.logger.info("已清空所有测试用例和套件")


class TestCaseDecorator:
    """测试用例装饰器"""
    
    def __init__(self, manager: TestCaseManager):
        self.manager = manager
    
    def test_case(self, test_id: str = None, name: str = None, 
                 description: str = None, priority: TestPriority = TestPriority.MEDIUM,
                 test_type: TestType = TestType.REGRESSION, tags: List[str] = None,
                 timeout: int = 300, retry_count: int = 0):
        """测试用例装饰器"""
        def decorator(func):
            builder = TestCaseBuilder()
            
            builder.with_id(test_id or func.__name__)
            builder.with_name(name or func.__name__)
            builder.with_description(description or func.__doc__ or "")
            builder.with_function(func)
            builder.with_priority(priority)
            builder.with_type(test_type)
            builder.with_tags(tags or [])
            builder.with_timeout(timeout)
            builder.with_retry(retry_count)
            
            test_case = builder.build()
            self.manager.register_test_case(test_case)
            
            return func
        
        return decorator
    
    def test_suite(self, suite_id: str, name: str, description: str = "",
                  setup_function: Callable = None, teardown_function: Callable = None,
                  parallel: bool = False, max_workers: int = 1, tags: List[str] = None):
        """测试套件装饰器"""
        def decorator(cls):
            test_suite = TestSuite(
                id=suite_id,
                name=name,
                description=description,
                setup_function=setup_function,
                teardown_function=teardown_function,
                parallel=parallel,
                max_workers=max_workers,
                tags=tags or []
            )
            
            # 查找类中的测试方法
            for attr_name in dir(cls):
                if attr_name.startswith('test_'):
                    method = getattr(cls, attr_name)
                    if callable(method):
                        # 为每个测试方法创建测试用例
                        test_case = TestCase(
                            id=f"{suite_id}_{attr_name}",
                            name=attr_name,
                            description=method.__doc__ or "",
                            test_function=method
                        )
                        test_suite.test_cases.append(test_case)
            
            self.manager.register_test_suite(test_suite)
            return cls
        
        return decorator


# 全局测试用例管理器实例
_test_case_manager = TestCaseManager()


def get_test_case_manager() -> TestCaseManager:
    """获取测试用例管理器实例"""
    return _test_case_manager


def create_test_case_decorator() -> TestCaseDecorator:
    """创建测试用例装饰器"""
    return TestCaseDecorator(_test_case_manager)


# 便捷装饰器实例
test_decorator = create_test_case_decorator()
test_case = test_decorator.test_case
test_suite = test_decorator.test_suite


# Pytest集成函数
def pytest_generate_tests(metafunc):
    """Pytest动态生成测试用例"""
    if 'test_case_data' in metafunc.fixturenames:
        manager = get_test_case_manager()
        
        # 根据测试函数名查找对应的测试用例
        test_function_name = metafunc.function.__name__
        matching_cases = [tc for tc in manager.test_cases.values() 
                         if tc.test_function.__name__ == test_function_name]
        
        if matching_cases:
            test_data = [(tc.data, tc.id, tc.name) for tc in matching_cases]
            metafunc.parametrize('test_case_data,test_id,test_name', test_data)


def parametrize_with_test_cases(test_cases: List[TestCase]):
    """使用测试用例进行参数化"""
    test_data = [(tc.data, tc.id, tc.name, tc.description) for tc in test_cases]
    return pytest.mark.parametrize(
        'test_data,test_id,test_name,test_description', 
        test_data,
        ids=[tc.id for tc in test_cases]
    )