#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
测试数据管理器
提供测试数据的生成、管理、验证和清理功能
"""

import os
import json
import csv
import yaml
import sqlite3
import random
import string
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional, Union, Callable
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
import pandas as pd
from faker import Faker
import allure


class DataType(Enum):
    """数据类型枚举"""
    STRING = "string"
    INTEGER = "integer"
    FLOAT = "float"
    BOOLEAN = "boolean"
    DATE = "date"
    DATETIME = "datetime"
    EMAIL = "email"
    PHONE = "phone"
    URL = "url"
    UUID = "uuid"
    JSON = "json"


class DataSource(Enum):
    """数据源类型枚举"""
    JSON = "json"
    CSV = "csv"
    YAML = "yaml"
    EXCEL = "excel"
    DATABASE = "database"
    API = "api"
    FAKER = "faker"


@dataclass
class DataField:
    """数据字段定义"""
    name: str
    data_type: DataType
    required: bool = True
    default_value: Any = None
    min_length: Optional[int] = None
    max_length: Optional[int] = None
    min_value: Optional[Union[int, float]] = None
    max_value: Optional[Union[int, float]] = None
    pattern: Optional[str] = None
    choices: Optional[List[Any]] = None
    faker_provider: Optional[str] = None
    validation_func: Optional[Callable] = None
    description: str = ""


@dataclass
class DataSchema:
    """数据模式定义"""
    name: str
    fields: List[DataField]
    description: str = ""
    version: str = "1.0"
    
    def validate(self, data: Dict[str, Any]) -> tuple[bool, List[str]]:
        """验证数据是否符合模式"""
        errors = []
        
        for field in self.fields:
            value = data.get(field.name)
            
            # 检查必填字段
            if field.required and value is None:
                errors.append(f"字段 '{field.name}' 是必填的")
                continue
            
            if value is not None:
                # 类型检查
                if not self._validate_type(value, field.data_type):
                    errors.append(f"字段 '{field.name}' 类型不匹配，期望 {field.data_type.value}")
                
                # 长度检查
                if field.min_length is not None and len(str(value)) < field.min_length:
                    errors.append(f"字段 '{field.name}' 长度不能小于 {field.min_length}")
                
                if field.max_length is not None and len(str(value)) > field.max_length:
                    errors.append(f"字段 '{field.name}' 长度不能大于 {field.max_length}")
                
                # 数值范围检查
                if field.min_value is not None and isinstance(value, (int, float)) and value < field.min_value:
                    errors.append(f"字段 '{field.name}' 值不能小于 {field.min_value}")
                
                if field.max_value is not None and isinstance(value, (int, float)) and value > field.max_value:
                    errors.append(f"字段 '{field.name}' 值不能大于 {field.max_value}")
                
                # 选择值检查
                if field.choices and value not in field.choices:
                    errors.append(f"字段 '{field.name}' 值必须在 {field.choices} 中")
                
                # 自定义验证
                if field.validation_func and not field.validation_func(value):
                    errors.append(f"字段 '{field.name}' 自定义验证失败")
        
        return len(errors) == 0, errors
    
    def _validate_type(self, value: Any, data_type: DataType) -> bool:
        """验证数据类型"""
        type_map = {
            DataType.STRING: str,
            DataType.INTEGER: int,
            DataType.FLOAT: (int, float),
            DataType.BOOLEAN: bool,
            DataType.DATE: str,  # 简化处理，实际应该验证日期格式
            DataType.DATETIME: str,
            DataType.EMAIL: str,
            DataType.PHONE: str,
            DataType.URL: str,
            DataType.UUID: str,
            DataType.JSON: (dict, list)
        }
        
        expected_type = type_map.get(data_type)
        if expected_type:
            return isinstance(value, expected_type)
        return True


class DataGenerator:
    """数据生成器"""
    
    def __init__(self, locale: str = 'zh_CN'):
        self.faker = Faker(locale)
        self.logger = logging.getLogger(__name__)
    
    def generate_by_schema(self, schema: DataSchema, count: int = 1) -> List[Dict[str, Any]]:
        """根据模式生成数据"""
        data_list = []
        
        for _ in range(count):
            data = {}
            for field in schema.fields:
                data[field.name] = self._generate_field_value(field)
            data_list.append(data)
        
        return data_list
    
    def _generate_field_value(self, field: DataField) -> Any:
        """生成字段值"""
        # 如果有选择值，随机选择一个
        if field.choices:
            return random.choice(field.choices)
        
        # 如果有默认值且不是必填，有概率返回默认值
        if field.default_value is not None and not field.required and random.random() < 0.3:
            return field.default_value
        
        # 根据数据类型生成值
        if field.data_type == DataType.STRING:
            return self._generate_string(field)
        elif field.data_type == DataType.INTEGER:
            return self._generate_integer(field)
        elif field.data_type == DataType.FLOAT:
            return self._generate_float(field)
        elif field.data_type == DataType.BOOLEAN:
            return random.choice([True, False])
        elif field.data_type == DataType.DATE:
            return self.faker.date().isoformat()
        elif field.data_type == DataType.DATETIME:
            return self.faker.date_time().isoformat()
        elif field.data_type == DataType.EMAIL:
            return self.faker.email()
        elif field.data_type == DataType.PHONE:
            return self.faker.phone_number()
        elif field.data_type == DataType.URL:
            return self.faker.url()
        elif field.data_type == DataType.UUID:
            return self.faker.uuid4()
        elif field.data_type == DataType.JSON:
            return {"key": self.faker.word(), "value": self.faker.sentence()}
        
        # 如果有Faker提供者，使用它
        if field.faker_provider:
            try:
                return getattr(self.faker, field.faker_provider)()
            except AttributeError:
                self.logger.warning(f"未知的Faker提供者: {field.faker_provider}")
        
        return field.default_value
    
    def _generate_string(self, field: DataField) -> str:
        """生成字符串"""
        min_len = field.min_length or 1
        max_len = field.max_length or 50
        length = random.randint(min_len, min(max_len, 100))
        
        if field.pattern:
            # 简化的模式匹配，实际应该使用正则表达式生成
            return self.faker.lexify('?' * length)
        
        return self.faker.text(max_nb_chars=length)
    
    def _generate_integer(self, field: DataField) -> int:
        """生成整数"""
        min_val = field.min_value or 0
        max_val = field.max_value or 1000
        return random.randint(int(min_val), int(max_val))
    
    def _generate_float(self, field: DataField) -> float:
        """生成浮点数"""
        min_val = field.min_value or 0.0
        max_val = field.max_value or 1000.0
        return round(random.uniform(min_val, max_val), 2)
    
    def generate_test_users(self, count: int = 10) -> List[Dict[str, Any]]:
        """生成测试用户数据"""
        users = []
        for _ in range(count):
            user = {
                'id': self.faker.uuid4(),
                'username': self.faker.user_name(),
                'email': self.faker.email(),
                'password': self.faker.password(length=12),
                'first_name': self.faker.first_name(),
                'last_name': self.faker.last_name(),
                'phone': self.faker.phone_number(),
                'address': self.faker.address(),
                'birth_date': self.faker.date_of_birth().isoformat(),
                'created_at': self.faker.date_time_this_year().isoformat(),
                'is_active': random.choice([True, False]),
                'role': random.choice(['user', 'admin', 'moderator'])
            }
            users.append(user)
        return users
    
    def generate_test_products(self, count: int = 20) -> List[Dict[str, Any]]:
        """生成测试产品数据"""
        products = []
        categories = ['电子产品', '服装', '家居', '图书', '运动', '美妆']
        
        for _ in range(count):
            product = {
                'id': self.faker.uuid4(),
                'name': self.faker.catch_phrase(),
                'description': self.faker.text(max_nb_chars=200),
                'price': round(random.uniform(10.0, 1000.0), 2),
                'category': random.choice(categories),
                'stock': random.randint(0, 100),
                'sku': self.faker.ean13(),
                'brand': self.faker.company(),
                'weight': round(random.uniform(0.1, 10.0), 2),
                'dimensions': {
                    'length': round(random.uniform(1, 50), 1),
                    'width': round(random.uniform(1, 50), 1),
                    'height': round(random.uniform(1, 50), 1)
                },
                'created_at': self.faker.date_time_this_year().isoformat(),
                'is_available': random.choice([True, False])
            }
            products.append(product)
        return products


class DataLoader:
    """数据加载器"""
    
    def __init__(self):
        self.logger = logging.getLogger(__name__)
    
    def load_from_json(self, file_path: str) -> List[Dict[str, Any]]:
        """从JSON文件加载数据"""
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            if isinstance(data, list):
                return data
            elif isinstance(data, dict):
                return [data]
            else:
                self.logger.error(f"不支持的JSON数据格式: {type(data)}")
                return []
                
        except Exception as e:
            self.logger.error(f"加载JSON文件失败: {e}")
            return []
    
    def load_from_csv(self, file_path: str) -> List[Dict[str, Any]]:
        """从CSV文件加载数据"""
        try:
            df = pd.read_csv(file_path)
            return df.to_dict('records')
        except Exception as e:
            self.logger.error(f"加载CSV文件失败: {e}")
            return []
    
    def load_from_yaml(self, file_path: str) -> List[Dict[str, Any]]:
        """从YAML文件加载数据"""
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                data = yaml.safe_load(f)
            
            if isinstance(data, list):
                return data
            elif isinstance(data, dict):
                return [data]
            else:
                return []
                
        except Exception as e:
            self.logger.error(f"加载YAML文件失败: {e}")
            return []
    
    def load_from_excel(self, file_path: str, sheet_name: str = None) -> List[Dict[str, Any]]:
        """从Excel文件加载数据"""
        try:
            df = pd.read_excel(file_path, sheet_name=sheet_name)
            return df.to_dict('records')
        except Exception as e:
            self.logger.error(f"加载Excel文件失败: {e}")
            return []
    
    def load_from_database(self, db_path: str, query: str) -> List[Dict[str, Any]]:
        """从数据库加载数据"""
        try:
            with sqlite3.connect(db_path) as conn:
                df = pd.read_sql_query(query, conn)
                return df.to_dict('records')
        except Exception as e:
            self.logger.error(f"从数据库加载数据失败: {e}")
            return []


class DataSaver:
    """数据保存器"""
    
    def __init__(self):
        self.logger = logging.getLogger(__name__)
    
    def save_to_json(self, data: List[Dict[str, Any]], file_path: str) -> bool:
        """保存数据到JSON文件"""
        try:
            os.makedirs(os.path.dirname(file_path), exist_ok=True)
            with open(file_path, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2, default=str)
            return True
        except Exception as e:
            self.logger.error(f"保存JSON文件失败: {e}")
            return False
    
    def save_to_csv(self, data: List[Dict[str, Any]], file_path: str) -> bool:
        """保存数据到CSV文件"""
        try:
            os.makedirs(os.path.dirname(file_path), exist_ok=True)
            df = pd.DataFrame(data)
            df.to_csv(file_path, index=False, encoding='utf-8-sig')
            return True
        except Exception as e:
            self.logger.error(f"保存CSV文件失败: {e}")
            return False
    
    def save_to_yaml(self, data: List[Dict[str, Any]], file_path: str) -> bool:
        """保存数据到YAML文件"""
        try:
            os.makedirs(os.path.dirname(file_path), exist_ok=True)
            with open(file_path, 'w', encoding='utf-8') as f:
                yaml.dump(data, f, default_flow_style=False, allow_unicode=True)
            return True
        except Exception as e:
            self.logger.error(f"保存YAML文件失败: {e}")
            return False
    
    def save_to_excel(self, data: List[Dict[str, Any]], file_path: str, sheet_name: str = 'Sheet1') -> bool:
        """保存数据到Excel文件"""
        try:
            os.makedirs(os.path.dirname(file_path), exist_ok=True)
            df = pd.DataFrame(data)
            df.to_excel(file_path, sheet_name=sheet_name, index=False)
            return True
        except Exception as e:
            self.logger.error(f"保存Excel文件失败: {e}")
            return False


class DataValidator:
    """数据验证器"""
    
    def __init__(self):
        self.logger = logging.getLogger(__name__)
    
    def validate_data(self, data: List[Dict[str, Any]], schema: DataSchema) -> Dict[str, Any]:
        """验证数据列表"""
        results = {
            'total': len(data),
            'valid': 0,
            'invalid': 0,
            'errors': []
        }
        
        for i, item in enumerate(data):
            is_valid, errors = schema.validate(item)
            if is_valid:
                results['valid'] += 1
            else:
                results['invalid'] += 1
                results['errors'].append({
                    'index': i,
                    'data': item,
                    'errors': errors
                })
        
        return results
    
    def validate_email(self, email: str) -> bool:
        """验证邮箱格式"""
        import re
        pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
        return bool(re.match(pattern, email))
    
    def validate_phone(self, phone: str) -> bool:
        """验证手机号格式"""
        import re
        # 简化的中国手机号验证
        pattern = r'^1[3-9]\d{9}$'
        return bool(re.match(pattern, phone.replace('-', '').replace(' ', '')))
    
    def validate_url(self, url: str) -> bool:
        """验证URL格式"""
        import re
        pattern = r'^https?://[\w\.-]+\.[a-zA-Z]{2,}'
        return bool(re.match(pattern, url))


class TestDataManager:
    """测试数据管理器"""
    
    def __init__(self, data_dir: str = "test_data"):
        self.data_dir = Path(data_dir)
        self.data_dir.mkdir(exist_ok=True)
        
        # 创建子目录
        self.schemas_dir = self.data_dir / "schemas"
        self.generated_dir = self.data_dir / "generated"
        self.fixtures_dir = self.data_dir / "fixtures"
        self.temp_dir = self.data_dir / "temp"
        
        for dir_path in [self.schemas_dir, self.generated_dir, self.fixtures_dir, self.temp_dir]:
            dir_path.mkdir(exist_ok=True)
        
        # 初始化组件
        self.generator = DataGenerator()
        self.loader = DataLoader()
        self.saver = DataSaver()
        self.validator = DataValidator()
        self.logger = logging.getLogger(__name__)
        
        # 数据缓存
        self._data_cache = {}
        self._schema_cache = {}
    
    @allure.step("创建数据模式")
    def create_schema(self, schema: DataSchema) -> bool:
        """创建并保存数据模式"""
        try:
            schema_file = self.schemas_dir / f"{schema.name}.json"
            schema_data = {
                'name': schema.name,
                'description': schema.description,
                'version': schema.version,
                'fields': [
                    {
                        'name': field.name,
                        'data_type': field.data_type.value,
                        'required': field.required,
                        'default_value': field.default_value,
                        'min_length': field.min_length,
                        'max_length': field.max_length,
                        'min_value': field.min_value,
                        'max_value': field.max_value,
                        'pattern': field.pattern,
                        'choices': field.choices,
                        'faker_provider': field.faker_provider,
                        'description': field.description
                    } for field in schema.fields
                ]
            }
            
            with open(schema_file, 'w', encoding='utf-8') as f:
                json.dump(schema_data, f, ensure_ascii=False, indent=2)
            
            self._schema_cache[schema.name] = schema
            self.logger.info(f"数据模式已创建: {schema.name}")
            return True
            
        except Exception as e:
            self.logger.error(f"创建数据模式失败: {e}")
            return False
    
    def load_schema(self, schema_name: str) -> Optional[DataSchema]:
        """加载数据模式"""
        if schema_name in self._schema_cache:
            return self._schema_cache[schema_name]
        
        try:
            schema_file = self.schemas_dir / f"{schema_name}.json"
            if not schema_file.exists():
                self.logger.error(f"数据模式文件不存在: {schema_file}")
                return None
            
            with open(schema_file, 'r', encoding='utf-8') as f:
                schema_data = json.load(f)
            
            fields = []
            for field_data in schema_data['fields']:
                field = DataField(
                    name=field_data['name'],
                    data_type=DataType(field_data['data_type']),
                    required=field_data.get('required', True),
                    default_value=field_data.get('default_value'),
                    min_length=field_data.get('min_length'),
                    max_length=field_data.get('max_length'),
                    min_value=field_data.get('min_value'),
                    max_value=field_data.get('max_value'),
                    pattern=field_data.get('pattern'),
                    choices=field_data.get('choices'),
                    faker_provider=field_data.get('faker_provider'),
                    description=field_data.get('description', '')
                )
                fields.append(field)
            
            schema = DataSchema(
                name=schema_data['name'],
                fields=fields,
                description=schema_data.get('description', ''),
                version=schema_data.get('version', '1.0')
            )
            
            self._schema_cache[schema_name] = schema
            return schema
            
        except Exception as e:
            self.logger.error(f"加载数据模式失败: {e}")
            return None
    
    @allure.step("生成测试数据")
    def generate_data(self, schema_name: str, count: int = 10, 
                     save_format: DataSource = DataSource.JSON) -> Optional[str]:
        """生成测试数据"""
        schema = self.load_schema(schema_name)
        if not schema:
            return None
        
        try:
            # 生成数据
            data = self.generator.generate_by_schema(schema, count)
            
            # 保存数据
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            filename = f"{schema_name}_{timestamp}"
            
            if save_format == DataSource.JSON:
                file_path = self.generated_dir / f"{filename}.json"
                success = self.saver.save_to_json(data, str(file_path))
            elif save_format == DataSource.CSV:
                file_path = self.generated_dir / f"{filename}.csv"
                success = self.saver.save_to_csv(data, str(file_path))
            elif save_format == DataSource.YAML:
                file_path = self.generated_dir / f"{filename}.yaml"
                success = self.saver.save_to_yaml(data, str(file_path))
            elif save_format == DataSource.EXCEL:
                file_path = self.generated_dir / f"{filename}.xlsx"
                success = self.saver.save_to_excel(data, str(file_path))
            else:
                self.logger.error(f"不支持的保存格式: {save_format}")
                return None
            
            if success:
                self.logger.info(f"测试数据已生成: {file_path}")
                return str(file_path)
            else:
                return None
                
        except Exception as e:
            self.logger.error(f"生成测试数据失败: {e}")
            return None
    
    def load_test_data(self, file_path: str, cache_key: str = None) -> List[Dict[str, Any]]:
        """加载测试数据"""
        if cache_key and cache_key in self._data_cache:
            return self._data_cache[cache_key]
        
        file_path = Path(file_path)
        data = []
        
        if file_path.suffix.lower() == '.json':
            data = self.loader.load_from_json(str(file_path))
        elif file_path.suffix.lower() == '.csv':
            data = self.loader.load_from_csv(str(file_path))
        elif file_path.suffix.lower() in ['.yaml', '.yml']:
            data = self.loader.load_from_yaml(str(file_path))
        elif file_path.suffix.lower() in ['.xlsx', '.xls']:
            data = self.loader.load_from_excel(str(file_path))
        else:
            self.logger.error(f"不支持的文件格式: {file_path.suffix}")
        
        if cache_key and data:
            self._data_cache[cache_key] = data
        
        return data
    
    @allure.step("验证测试数据")
    def validate_test_data(self, data: List[Dict[str, Any]], schema_name: str) -> Dict[str, Any]:
        """验证测试数据"""
        schema = self.load_schema(schema_name)
        if not schema:
            return {'error': f'数据模式不存在: {schema_name}'}
        
        return self.validator.validate_data(data, schema)
    
    def cleanup_temp_data(self, older_than_days: int = 7):
        """清理临时数据"""
        try:
            cutoff_date = datetime.now() - timedelta(days=older_than_days)
            
            for file_path in self.temp_dir.glob('*'):
                if file_path.is_file():
                    file_time = datetime.fromtimestamp(file_path.stat().st_mtime)
                    if file_time < cutoff_date:
                        file_path.unlink()
                        self.logger.info(f"已删除临时文件: {file_path}")
            
            self.logger.info(f"临时数据清理完成")
            
        except Exception as e:
            self.logger.error(f"清理临时数据失败: {e}")
    
    def get_data_statistics(self) -> Dict[str, Any]:
        """获取数据统计信息"""
        stats = {
            'schemas': len(list(self.schemas_dir.glob('*.json'))),
            'generated_files': len(list(self.generated_dir.glob('*'))),
            'fixture_files': len(list(self.fixtures_dir.glob('*'))),
            'temp_files': len(list(self.temp_dir.glob('*'))),
            'cache_size': len(self._data_cache)
        }
        return stats


# 预定义的数据模式
def create_user_schema() -> DataSchema:
    """创建用户数据模式"""
    fields = [
        DataField('id', DataType.UUID, faker_provider='uuid4'),
        DataField('username', DataType.STRING, min_length=3, max_length=20, faker_provider='user_name'),
        DataField('email', DataType.EMAIL, faker_provider='email'),
        DataField('password', DataType.STRING, min_length=8, max_length=50),
        DataField('first_name', DataType.STRING, faker_provider='first_name'),
        DataField('last_name', DataType.STRING, faker_provider='last_name'),
        DataField('phone', DataType.PHONE, faker_provider='phone_number'),
        DataField('age', DataType.INTEGER, min_value=18, max_value=100),
        DataField('is_active', DataType.BOOLEAN),
        DataField('role', DataType.STRING, choices=['user', 'admin', 'moderator']),
        DataField('created_at', DataType.DATETIME, faker_provider='date_time_this_year')
    ]
    
    return DataSchema(
        name='user',
        fields=fields,
        description='用户数据模式',
        version='1.0'
    )


def create_product_schema() -> DataSchema:
    """创建产品数据模式"""
    fields = [
        DataField('id', DataType.UUID, faker_provider='uuid4'),
        DataField('name', DataType.STRING, min_length=5, max_length=100, faker_provider='catch_phrase'),
        DataField('description', DataType.STRING, max_length=500, faker_provider='text'),
        DataField('price', DataType.FLOAT, min_value=0.01, max_value=9999.99),
        DataField('category', DataType.STRING, choices=['电子产品', '服装', '家居', '图书', '运动', '美妆']),
        DataField('stock', DataType.INTEGER, min_value=0, max_value=1000),
        DataField('sku', DataType.STRING, faker_provider='ean13'),
        DataField('brand', DataType.STRING, faker_provider='company'),
        DataField('is_available', DataType.BOOLEAN),
        DataField('created_at', DataType.DATETIME, faker_provider='date_time_this_year')
    ]
    
    return DataSchema(
        name='product',
        fields=fields,
        description='产品数据模式',
        version='1.0'
    )


# 使用示例
if __name__ == "__main__":
    # 创建测试数据管理器
    manager = TestDataManager()
    
    # 创建用户数据模式
    user_schema = create_user_schema()
    manager.create_schema(user_schema)
    
    # 生成用户测试数据
    user_data_file = manager.generate_data('user', count=50, save_format=DataSource.JSON)
    print(f"用户数据文件: {user_data_file}")
    
    # 加载并验证数据
    if user_data_file:
        data = manager.load_test_data(user_data_file, cache_key='test_users')
        validation_result = manager.validate_test_data(data, 'user')
        print(f"验证结果: {validation_result}")
    
    # 获取统计信息
    stats = manager.get_data_statistics()
    print(f"数据统计: {stats}")