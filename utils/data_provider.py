#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
数据驱动测试的数据提供者
支持从多种数据源读取测试数据
"""

import json
import csv
import yaml
import os
import sqlite3
import pandas as pd
from typing import List, Dict, Any, Iterator, Union, Optional
from pathlib import Path
import logging
from abc import ABC, abstractmethod


class DataProvider(ABC):
    """数据提供者抽象基类"""
    
    @abstractmethod
    def load_data(self, source: str, **kwargs) -> List[Dict[str, Any]]:
        """加载数据"""
        pass
    
    @abstractmethod
    def save_data(self, data: List[Dict[str, Any]], destination: str, **kwargs) -> bool:
        """保存数据"""
        pass


class JSONDataProvider(DataProvider):
    """JSON数据提供者"""
    
    def load_data(self, source: str, **kwargs) -> List[Dict[str, Any]]:
        """从JSON文件加载数据"""
        try:
            with open(source, 'r', encoding='utf-8') as f:
                data = json.load(f)
                
            # 如果数据是字典，转换为列表
            if isinstance(data, dict):
                return [data]
            elif isinstance(data, list):
                return data
            else:
                raise ValueError(f"Unsupported JSON data type: {type(data)}")
                
        except Exception as e:
            logging.error(f"Failed to load JSON data from {source}: {e}")
            return []
    
    def save_data(self, data: List[Dict[str, Any]], destination: str, **kwargs) -> bool:
        """保存数据到JSON文件"""
        try:
            with open(destination, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            return True
        except Exception as e:
            logging.error(f"Failed to save JSON data to {destination}: {e}")
            return False


class CSVDataProvider(DataProvider):
    """CSV数据提供者"""
    
    def load_data(self, source: str, **kwargs) -> List[Dict[str, Any]]:
        """从CSV文件加载数据"""
        try:
            encoding = kwargs.get('encoding', 'utf-8')
            delimiter = kwargs.get('delimiter', ',')
            
            data = []
            with open(source, 'r', encoding=encoding, newline='') as f:
                reader = csv.DictReader(f, delimiter=delimiter)
                for row in reader:
                    data.append(dict(row))
            
            return data
            
        except Exception as e:
            logging.error(f"Failed to load CSV data from {source}: {e}")
            return []
    
    def save_data(self, data: List[Dict[str, Any]], destination: str, **kwargs) -> bool:
        """保存数据到CSV文件"""
        try:
            if not data:
                return True
            
            encoding = kwargs.get('encoding', 'utf-8')
            delimiter = kwargs.get('delimiter', ',')
            
            fieldnames = data[0].keys()
            
            with open(destination, 'w', encoding=encoding, newline='') as f:
                writer = csv.DictWriter(f, fieldnames=fieldnames, delimiter=delimiter)
                writer.writeheader()
                writer.writerows(data)
            
            return True
            
        except Exception as e:
            logging.error(f"Failed to save CSV data to {destination}: {e}")
            return False


class YAMLDataProvider(DataProvider):
    """YAML数据提供者"""
    
    def load_data(self, source: str, **kwargs) -> List[Dict[str, Any]]:
        """从YAML文件加载数据"""
        try:
            with open(source, 'r', encoding='utf-8') as f:
                data = yaml.safe_load(f)
            
            # 如果数据是字典，转换为列表
            if isinstance(data, dict):
                return [data]
            elif isinstance(data, list):
                return data
            else:
                raise ValueError(f"Unsupported YAML data type: {type(data)}")
                
        except Exception as e:
            logging.error(f"Failed to load YAML data from {source}: {e}")
            return []
    
    def save_data(self, data: List[Dict[str, Any]], destination: str, **kwargs) -> bool:
        """保存数据到YAML文件"""
        try:
            with open(destination, 'w', encoding='utf-8') as f:
                yaml.dump(data, f, default_flow_style=False, allow_unicode=True)
            return True
        except Exception as e:
            logging.error(f"Failed to save YAML data to {destination}: {e}")
            return False


class ExcelDataProvider(DataProvider):
    """Excel数据提供者"""
    
    def load_data(self, source: str, **kwargs) -> List[Dict[str, Any]]:
        """从Excel文件加载数据"""
        try:
            sheet_name = kwargs.get('sheet_name', 0)
            header = kwargs.get('header', 0)
            
            df = pd.read_excel(source, sheet_name=sheet_name, header=header)
            
            # 将NaN值替换为None
            df = df.where(pd.notnull(df), None)
            
            # 转换为字典列表
            return df.to_dict('records')
            
        except Exception as e:
            logging.error(f"Failed to load Excel data from {source}: {e}")
            return []
    
    def save_data(self, data: List[Dict[str, Any]], destination: str, **kwargs) -> bool:
        """保存数据到Excel文件"""
        try:
            if not data:
                return True
            
            sheet_name = kwargs.get('sheet_name', 'Sheet1')
            index = kwargs.get('index', False)
            
            df = pd.DataFrame(data)
            df.to_excel(destination, sheet_name=sheet_name, index=index)
            
            return True
            
        except Exception as e:
            logging.error(f"Failed to save Excel data to {destination}: {e}")
            return False


class SQLiteDataProvider(DataProvider):
    """SQLite数据提供者"""
    
    def load_data(self, source: str, **kwargs) -> List[Dict[str, Any]]:
        """从SQLite数据库加载数据"""
        try:
            query = kwargs.get('query', 'SELECT * FROM test_data')
            
            conn = sqlite3.connect(source)
            conn.row_factory = sqlite3.Row  # 使结果可以按列名访问
            
            cursor = conn.cursor()
            cursor.execute(query)
            
            rows = cursor.fetchall()
            data = [dict(row) for row in rows]
            
            conn.close()
            return data
            
        except Exception as e:
            logging.error(f"Failed to load SQLite data from {source}: {e}")
            return []
    
    def save_data(self, data: List[Dict[str, Any]], destination: str, **kwargs) -> bool:
        """保存数据到SQLite数据库"""
        try:
            if not data:
                return True
            
            table_name = kwargs.get('table_name', 'test_data')
            if_exists = kwargs.get('if_exists', 'replace')  # 'fail', 'replace', 'append'
            
            df = pd.DataFrame(data)
            
            conn = sqlite3.connect(destination)
            df.to_sql(table_name, conn, if_exists=if_exists, index=False)
            conn.close()
            
            return True
            
        except Exception as e:
            logging.error(f"Failed to save SQLite data to {destination}: {e}")
            return False


class DataManager:
    """数据管理器 - 统一管理各种数据源"""
    
    def __init__(self):
        self.providers = {
            '.json': JSONDataProvider(),
            '.csv': CSVDataProvider(),
            '.yaml': YAMLDataProvider(),
            '.yml': YAMLDataProvider(),
            '.xlsx': ExcelDataProvider(),
            '.xls': ExcelDataProvider(),
            '.db': SQLiteDataProvider(),
            '.sqlite': SQLiteDataProvider(),
            '.sqlite3': SQLiteDataProvider()
        }
        self._cache = {}
    
    def register_provider(self, extension: str, provider: DataProvider):
        """注册新的数据提供者"""
        self.providers[extension] = provider
    
    def load_data(self, source: str, use_cache: bool = True, **kwargs) -> List[Dict[str, Any]]:
        """加载数据
        
        Args:
            source: 数据源路径
            use_cache: 是否使用缓存
            **kwargs: 传递给数据提供者的参数
        
        Returns:
            数据列表
        """
        # 检查缓存
        if use_cache and source in self._cache:
            return self._cache[source]
        
        # 获取文件扩展名
        ext = Path(source).suffix.lower()
        
        if ext not in self.providers:
            raise ValueError(f"Unsupported file type: {ext}")
        
        # 加载数据
        provider = self.providers[ext]
        data = provider.load_data(source, **kwargs)
        
        # 缓存数据
        if use_cache:
            self._cache[source] = data
        
        return data
    
    def save_data(self, data: List[Dict[str, Any]], destination: str, **kwargs) -> bool:
        """保存数据
        
        Args:
            data: 要保存的数据
            destination: 目标路径
            **kwargs: 传递给数据提供者的参数
        
        Returns:
            是否保存成功
        """
        # 确保目标目录存在
        os.makedirs(os.path.dirname(destination), exist_ok=True)
        
        # 获取文件扩展名
        ext = Path(destination).suffix.lower()
        
        if ext not in self.providers:
            raise ValueError(f"Unsupported file type: {ext}")
        
        # 保存数据
        provider = self.providers[ext]
        return provider.save_data(data, destination, **kwargs)
    
    def clear_cache(self):
        """清空缓存"""
        self._cache.clear()
    
    def remove_from_cache(self, source: str):
        """从缓存中移除指定数据源"""
        if source in self._cache:
            del self._cache[source]
    
    def get_cached_sources(self) -> List[str]:
        """获取已缓存的数据源列表"""
        return list(self._cache.keys())


class TestDataGenerator:
    """测试数据生成器"""
    
    @staticmethod
    def generate_user_data(count: int = 10) -> List[Dict[str, Any]]:
        """生成用户测试数据"""
        import random
        import string
        from datetime import datetime, timedelta
        
        data = []
        for i in range(count):
            username = f"user_{i+1:03d}"
            email = f"{username}@test.com"
            password = ''.join(random.choices(string.ascii_letters + string.digits, k=8))
            age = random.randint(18, 65)
            created_at = datetime.now() - timedelta(days=random.randint(1, 365))
            
            data.append({
                'id': i + 1,
                'username': username,
                'email': email,
                'password': password,
                'age': age,
                'created_at': created_at.isoformat(),
                'is_active': random.choice([True, False])
            })
        
        return data
    
    @staticmethod
    def generate_product_data(count: int = 20) -> List[Dict[str, Any]]:
        """生成产品测试数据"""
        import random
        
        categories = ['Electronics', 'Clothing', 'Books', 'Home', 'Sports']
        brands = ['Brand A', 'Brand B', 'Brand C', 'Brand D', 'Brand E']
        
        data = []
        for i in range(count):
            product_name = f"Product {i+1:03d}"
            category = random.choice(categories)
            brand = random.choice(brands)
            price = round(random.uniform(10.0, 1000.0), 2)
            stock = random.randint(0, 100)
            
            data.append({
                'id': i + 1,
                'name': product_name,
                'category': category,
                'brand': brand,
                'price': price,
                'stock': stock,
                'is_available': stock > 0
            })
        
        return data
    
    @staticmethod
    def generate_login_data(valid_count: int = 5, invalid_count: int = 5) -> List[Dict[str, Any]]:
        """生成登录测试数据"""
        data = []
        
        # 生成有效登录数据
        for i in range(valid_count):
            data.append({
                'username': f"valid_user_{i+1}",
                'password': f"valid_pass_{i+1}",
                'expected_result': 'success',
                'description': f"Valid login test case {i+1}"
            })
        
        # 生成无效登录数据
        invalid_cases = [
            {'username': '', 'password': 'password', 'description': 'Empty username'},
            {'username': 'username', 'password': '', 'description': 'Empty password'},
            {'username': '', 'password': '', 'description': 'Empty username and password'},
            {'username': 'invalid_user', 'password': 'wrong_password', 'description': 'Invalid credentials'},
            {'username': 'user@test.com', 'password': 'short', 'description': 'Short password'}
        ]
        
        for i, case in enumerate(invalid_cases[:invalid_count]):
            case['expected_result'] = 'failure'
            data.append(case)
        
        return data


class DataFilter:
    """数据过滤器"""
    
    @staticmethod
    def filter_by_condition(data: List[Dict[str, Any]], condition: callable) -> List[Dict[str, Any]]:
        """根据条件过滤数据"""
        return [item for item in data if condition(item)]
    
    @staticmethod
    def filter_by_field(data: List[Dict[str, Any]], field: str, value: Any) -> List[Dict[str, Any]]:
        """根据字段值过滤数据"""
        return [item for item in data if item.get(field) == value]
    
    @staticmethod
    def filter_by_fields(data: List[Dict[str, Any]], filters: Dict[str, Any]) -> List[Dict[str, Any]]:
        """根据多个字段过滤数据"""
        result = data
        for field, value in filters.items():
            result = DataFilter.filter_by_field(result, field, value)
        return result
    
    @staticmethod
    def filter_by_range(data: List[Dict[str, Any]], field: str, min_val: Any = None, max_val: Any = None) -> List[Dict[str, Any]]:
        """根据范围过滤数据"""
        result = []
        for item in data:
            value = item.get(field)
            if value is None:
                continue
            
            if min_val is not None and value < min_val:
                continue
            
            if max_val is not None and value > max_val:
                continue
            
            result.append(item)
        
        return result
    
    @staticmethod
    def sample_data(data: List[Dict[str, Any]], count: int, random_seed: int = None) -> List[Dict[str, Any]]:
        """随机采样数据"""
        import random
        
        if random_seed is not None:
            random.seed(random_seed)
        
        if count >= len(data):
            return data.copy()
        
        return random.sample(data, count)


# 全局数据管理器实例
_data_manager = DataManager()


def load_test_data(source: str, **kwargs) -> List[Dict[str, Any]]:
    """便捷函数：加载测试数据"""
    return _data_manager.load_data(source, **kwargs)


def save_test_data(data: List[Dict[str, Any]], destination: str, **kwargs) -> bool:
    """便捷函数：保存测试数据"""
    return _data_manager.save_data(data, destination, **kwargs)


def get_data_manager() -> DataManager:
    """获取数据管理器实例"""
    return _data_manager


# Pytest参数化装饰器辅助函数
def parametrize_from_file(source: str, **kwargs):
    """从文件创建pytest参数化装饰器
    
    Usage:
        @parametrize_from_file('test_data.json')
        def test_login(test_data):
            username = test_data['username']
            password = test_data['password']
            # 测试逻辑
    """
    import pytest
    
    data = load_test_data(source, **kwargs)
    
    # 生成测试ID
    ids = []
    for i, item in enumerate(data):
        test_id = item.get('id') or item.get('name') or item.get('description') or f"test_{i+1}"
        ids.append(str(test_id))
    
    return pytest.mark.parametrize('test_data', data, ids=ids)


def parametrize_from_data(data: List[Dict[str, Any]], param_name: str = 'test_data'):
    """从数据列表创建pytest参数化装饰器"""
    import pytest
    
    # 生成测试ID
    ids = []
    for i, item in enumerate(data):
        test_id = item.get('id') or item.get('name') or item.get('description') or f"test_{i+1}"
        ids.append(str(test_id))
    
    return pytest.mark.parametrize(param_name, data, ids=ids)