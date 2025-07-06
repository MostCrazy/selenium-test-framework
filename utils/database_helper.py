#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
数据库测试辅助工具
提供数据库连接、查询、数据验证等功能
"""

import sqlite3
import pymysql
import psycopg2
import logging
import time
from typing import Dict, List, Any, Optional, Union, Tuple
from dataclasses import dataclass, field
from enum import Enum
from contextlib import contextmanager
import allure
from urllib.parse import urlparse
import json
from datetime import datetime, date
import decimal


class DatabaseType(Enum):
    """数据库类型枚举"""
    SQLITE = "sqlite"
    MYSQL = "mysql"
    POSTGRESQL = "postgresql"
    ORACLE = "oracle"
    SQLSERVER = "sqlserver"


@dataclass
class DatabaseConfig:
    """数据库配置"""
    db_type: DatabaseType
    host: str = "localhost"
    port: int = 3306
    database: str = ""
    username: str = ""
    password: str = ""
    charset: str = "utf8mb4"
    autocommit: bool = True
    connect_timeout: int = 10
    read_timeout: int = 30
    write_timeout: int = 30
    ssl_disabled: bool = False
    extra_params: Dict[str, Any] = field(default_factory=dict)
    
    @classmethod
    def from_url(cls, url: str) -> 'DatabaseConfig':
        """从URL创建数据库配置
        
        支持格式:
        - sqlite:///path/to/database.db
        - mysql://user:password@host:port/database
        - postgresql://user:password@host:port/database
        """
        parsed = urlparse(url)
        
        if parsed.scheme == 'sqlite':
            return cls(
                db_type=DatabaseType.SQLITE,
                database=parsed.path
            )
        elif parsed.scheme == 'mysql':
            return cls(
                db_type=DatabaseType.MYSQL,
                host=parsed.hostname or 'localhost',
                port=parsed.port or 3306,
                database=parsed.path.lstrip('/'),
                username=parsed.username or '',
                password=parsed.password or ''
            )
        elif parsed.scheme == 'postgresql':
            return cls(
                db_type=DatabaseType.POSTGRESQL,
                host=parsed.hostname or 'localhost',
                port=parsed.port or 5432,
                database=parsed.path.lstrip('/'),
                username=parsed.username or '',
                password=parsed.password or ''
            )
        else:
            raise ValueError(f"不支持的数据库类型: {parsed.scheme}")


@dataclass
class QueryResult:
    """查询结果"""
    rows: List[Dict[str, Any]]
    row_count: int
    columns: List[str]
    execution_time: float
    sql: str
    params: Optional[Tuple] = None
    
    def get_first_row(self) -> Optional[Dict[str, Any]]:
        """获取第一行数据"""
        return self.rows[0] if self.rows else None
    
    def get_column_values(self, column: str) -> List[Any]:
        """获取指定列的所有值"""
        return [row.get(column) for row in self.rows]
    
    def to_dict_list(self) -> List[Dict[str, Any]]:
        """转换为字典列表"""
        return self.rows
    
    def to_json(self) -> str:
        """转换为JSON字符串"""
        return json.dumps(self.rows, default=self._json_serializer, ensure_ascii=False, indent=2)
    
    @staticmethod
    def _json_serializer(obj):
        """JSON序列化器"""
        if isinstance(obj, (datetime, date)):
            return obj.isoformat()
        elif isinstance(obj, decimal.Decimal):
            return float(obj)
        raise TypeError(f"Object of type {type(obj)} is not JSON serializable")


class DatabaseHelper:
    """数据库测试辅助类"""
    
    def __init__(self, config: DatabaseConfig):
        self.config = config
        self.connection = None
        self.logger = logging.getLogger(__name__)
    
    def connect(self):
        """连接数据库"""
        try:
            if self.config.db_type == DatabaseType.SQLITE:
                self.connection = sqlite3.connect(
                    self.config.database,
                    timeout=self.config.connect_timeout
                )
                self.connection.row_factory = sqlite3.Row
            
            elif self.config.db_type == DatabaseType.MYSQL:
                self.connection = pymysql.connect(
                    host=self.config.host,
                    port=self.config.port,
                    user=self.config.username,
                    password=self.config.password,
                    database=self.config.database,
                    charset=self.config.charset,
                    autocommit=self.config.autocommit,
                    connect_timeout=self.config.connect_timeout,
                    read_timeout=self.config.read_timeout,
                    write_timeout=self.config.write_timeout,
                    **self.config.extra_params
                )
            
            elif self.config.db_type == DatabaseType.POSTGRESQL:
                conn_params = {
                    'host': self.config.host,
                    'port': self.config.port,
                    'user': self.config.username,
                    'password': self.config.password,
                    'database': self.config.database,
                    'connect_timeout': self.config.connect_timeout,
                    **self.config.extra_params
                }
                self.connection = psycopg2.connect(**conn_params)
                if self.config.autocommit:
                    self.connection.autocommit = True
            
            else:
                raise ValueError(f"不支持的数据库类型: {self.config.db_type}")
            
            self.logger.info(f"成功连接到数据库: {self.config.db_type.value}")
            
        except Exception as e:
            self.logger.error(f"数据库连接失败: {e}")
            raise
    
    def disconnect(self):
        """断开数据库连接"""
        if self.connection:
            self.connection.close()
            self.connection = None
            self.logger.info("数据库连接已断开")
    
    @contextmanager
    def get_cursor(self):
        """获取数据库游标"""
        if not self.connection:
            self.connect()
        
        cursor = self.connection.cursor()
        try:
            yield cursor
        finally:
            cursor.close()
    
    @allure.step("执行SQL查询: {sql}")
    def execute_query(self, sql: str, params: Tuple = None) -> QueryResult:
        """执行查询SQL"""
        start_time = time.time()
        
        with self.get_cursor() as cursor:
            try:
                if params:
                    cursor.execute(sql, params)
                else:
                    cursor.execute(sql)
                
                # 获取列名
                if self.config.db_type == DatabaseType.SQLITE:
                    columns = [description[0] for description in cursor.description] if cursor.description else []
                    rows = [dict(row) for row in cursor.fetchall()]
                elif self.config.db_type == DatabaseType.MYSQL:
                    columns = [desc[0] for desc in cursor.description] if cursor.description else []
                    rows = [dict(zip(columns, row)) for row in cursor.fetchall()]
                elif self.config.db_type == DatabaseType.POSTGRESQL:
                    columns = [desc[0] for desc in cursor.description] if cursor.description else []
                    rows = [dict(zip(columns, row)) for row in cursor.fetchall()]
                else:
                    columns = []
                    rows = []
                
                execution_time = time.time() - start_time
                
                result = QueryResult(
                    rows=rows,
                    row_count=len(rows),
                    columns=columns,
                    execution_time=execution_time,
                    sql=sql,
                    params=params
                )
                
                self.logger.info(f"查询执行成功，返回 {result.row_count} 行数据，耗时 {execution_time:.3f}s")
                
                # Allure报告附件
                allure.attach(
                    json.dumps({
                        'sql': sql,
                        'params': params,
                        'row_count': result.row_count,
                        'execution_time': execution_time,
                        'columns': columns
                    }, ensure_ascii=False, indent=2),
                    name="SQL查询信息",
                    attachment_type=allure.attachment_type.JSON
                )
                
                if result.row_count <= 100:  # 只附加少量数据
                    allure.attach(
                        result.to_json(),
                        name="查询结果",
                        attachment_type=allure.attachment_type.JSON
                    )
                
                return result
                
            except Exception as e:
                execution_time = time.time() - start_time
                self.logger.error(f"SQL查询失败: {e}，耗时 {execution_time:.3f}s")
                raise
    
    @allure.step("执行SQL命令: {sql}")
    def execute_command(self, sql: str, params: Tuple = None) -> int:
        """执行非查询SQL（INSERT, UPDATE, DELETE等）"""
        start_time = time.time()
        
        with self.get_cursor() as cursor:
            try:
                if params:
                    cursor.execute(sql, params)
                else:
                    cursor.execute(sql)
                
                affected_rows = cursor.rowcount
                
                if not self.config.autocommit:
                    self.connection.commit()
                
                execution_time = time.time() - start_time
                
                self.logger.info(f"SQL命令执行成功，影响 {affected_rows} 行，耗时 {execution_time:.3f}s")
                
                # Allure报告附件
                allure.attach(
                    json.dumps({
                        'sql': sql,
                        'params': params,
                        'affected_rows': affected_rows,
                        'execution_time': execution_time
                    }, ensure_ascii=False, indent=2),
                    name="SQL命令信息",
                    attachment_type=allure.attachment_type.JSON
                )
                
                return affected_rows
                
            except Exception as e:
                execution_time = time.time() - start_time
                self.logger.error(f"SQL命令执行失败: {e}，耗时 {execution_time:.3f}s")
                if not self.config.autocommit:
                    self.connection.rollback()
                raise
    
    def execute_script(self, script: str) -> List[QueryResult]:
        """执行SQL脚本（多条SQL语句）"""
        statements = [stmt.strip() for stmt in script.split(';') if stmt.strip()]
        results = []
        
        for statement in statements:
            if statement.upper().startswith(('SELECT', 'SHOW', 'DESCRIBE', 'EXPLAIN')):
                result = self.execute_query(statement)
                results.append(result)
            else:
                affected_rows = self.execute_command(statement)
                # 为非查询语句创建一个简单的结果对象
                result = QueryResult(
                    rows=[],
                    row_count=affected_rows,
                    columns=[],
                    execution_time=0,
                    sql=statement
                )
                results.append(result)
        
        return results
    
    def table_exists(self, table_name: str) -> bool:
        """检查表是否存在"""
        if self.config.db_type == DatabaseType.SQLITE:
            sql = "SELECT name FROM sqlite_master WHERE type='table' AND name=?"
            params = (table_name,)
        elif self.config.db_type == DatabaseType.MYSQL:
            sql = "SELECT TABLE_NAME FROM information_schema.TABLES WHERE TABLE_SCHEMA=%s AND TABLE_NAME=%s"
            params = (self.config.database, table_name)
        elif self.config.db_type == DatabaseType.POSTGRESQL:
            sql = "SELECT tablename FROM pg_tables WHERE schemaname='public' AND tablename=%s"
            params = (table_name,)
        else:
            raise ValueError(f"不支持的数据库类型: {self.config.db_type}")
        
        result = self.execute_query(sql, params)
        return result.row_count > 0
    
    def get_table_columns(self, table_name: str) -> List[Dict[str, Any]]:
        """获取表的列信息"""
        if self.config.db_type == DatabaseType.SQLITE:
            sql = f"PRAGMA table_info({table_name})"
            result = self.execute_query(sql)
            return [{
                'column_name': row['name'],
                'data_type': row['type'],
                'is_nullable': not row['notnull'],
                'default_value': row['dflt_value']
            } for row in result.rows]
        
        elif self.config.db_type == DatabaseType.MYSQL:
            sql = """
            SELECT COLUMN_NAME as column_name, DATA_TYPE as data_type, 
                   IS_NULLABLE as is_nullable, COLUMN_DEFAULT as default_value
            FROM information_schema.COLUMNS 
            WHERE TABLE_SCHEMA=%s AND TABLE_NAME=%s
            ORDER BY ORDINAL_POSITION
            """
            result = self.execute_query(sql, (self.config.database, table_name))
            return [{
                'column_name': row['column_name'],
                'data_type': row['data_type'],
                'is_nullable': row['is_nullable'] == 'YES',
                'default_value': row['default_value']
            } for row in result.rows]
        
        elif self.config.db_type == DatabaseType.POSTGRESQL:
            sql = """
            SELECT column_name, data_type, is_nullable, column_default as default_value
            FROM information_schema.columns 
            WHERE table_schema='public' AND table_name=%s
            ORDER BY ordinal_position
            """
            result = self.execute_query(sql, (table_name,))
            return [{
                'column_name': row['column_name'],
                'data_type': row['data_type'],
                'is_nullable': row['is_nullable'] == 'YES',
                'default_value': row['default_value']
            } for row in result.rows]
        
        else:
            raise ValueError(f"不支持的数据库类型: {self.config.db_type}")
    
    def get_row_count(self, table_name: str, where_clause: str = "") -> int:
        """获取表的行数"""
        sql = f"SELECT COUNT(*) as count FROM {table_name}"
        if where_clause:
            sql += f" WHERE {where_clause}"
        
        result = self.execute_query(sql)
        return result.get_first_row()['count']
    
    def truncate_table(self, table_name: str):
        """清空表数据"""
        if self.config.db_type == DatabaseType.SQLITE:
            sql = f"DELETE FROM {table_name}"
        else:
            sql = f"TRUNCATE TABLE {table_name}"
        
        self.execute_command(sql)
    
    def insert_test_data(self, table_name: str, data: List[Dict[str, Any]]) -> int:
        """插入测试数据"""
        if not data:
            return 0
        
        columns = list(data[0].keys())
        placeholders = ', '.join(['?' if self.config.db_type == DatabaseType.SQLITE else '%s'] * len(columns))
        
        sql = f"INSERT INTO {table_name} ({', '.join(columns)}) VALUES ({placeholders})"
        
        total_affected = 0
        for row in data:
            values = tuple(row[col] for col in columns)
            affected = self.execute_command(sql, values)
            total_affected += affected
        
        return total_affected
    
    def backup_table(self, table_name: str, backup_table_name: str = None) -> str:
        """备份表数据"""
        if not backup_table_name:
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            backup_table_name = f"{table_name}_backup_{timestamp}"
        
        sql = f"CREATE TABLE {backup_table_name} AS SELECT * FROM {table_name}"
        self.execute_command(sql)
        
        return backup_table_name
    
    def restore_table(self, table_name: str, backup_table_name: str):
        """从备份恢复表数据"""
        # 清空原表
        self.truncate_table(table_name)
        
        # 从备份表复制数据
        sql = f"INSERT INTO {table_name} SELECT * FROM {backup_table_name}"
        self.execute_command(sql)


class DatabaseValidator:
    """数据库验证器"""
    
    def __init__(self, db_helper: DatabaseHelper):
        self.db_helper = db_helper
    
    @allure.step("验证表存在: {table_name}")
    def validate_table_exists(self, table_name: str):
        """验证表存在"""
        assert self.db_helper.table_exists(table_name), f"表 {table_name} 不存在"
    
    @allure.step("验证表不存在: {table_name}")
    def validate_table_not_exists(self, table_name: str):
        """验证表不存在"""
        assert not self.db_helper.table_exists(table_name), f"表 {table_name} 不应该存在"
    
    @allure.step("验证行数: {table_name} = {expected_count}")
    def validate_row_count(self, table_name: str, expected_count: int, where_clause: str = ""):
        """验证表行数"""
        actual_count = self.db_helper.get_row_count(table_name, where_clause)
        assert actual_count == expected_count, \
            f"表 {table_name} 期望行数 {expected_count}，实际行数 {actual_count}"
    
    @allure.step("验证行数大于: {table_name} > {min_count}")
    def validate_row_count_greater_than(self, table_name: str, min_count: int, where_clause: str = ""):
        """验证表行数大于指定值"""
        actual_count = self.db_helper.get_row_count(table_name, where_clause)
        assert actual_count > min_count, \
            f"表 {table_name} 行数 {actual_count} 应该大于 {min_count}"
    
    @allure.step("验证行数小于: {table_name} < {max_count}")
    def validate_row_count_less_than(self, table_name: str, max_count: int, where_clause: str = ""):
        """验证表行数小于指定值"""
        actual_count = self.db_helper.get_row_count(table_name, where_clause)
        assert actual_count < max_count, \
            f"表 {table_name} 行数 {actual_count} 应该小于 {max_count}"
    
    @allure.step("验证数据存在: {sql}")
    def validate_data_exists(self, sql: str, params: Tuple = None):
        """验证数据存在"""
        result = self.db_helper.execute_query(sql, params)
        assert result.row_count > 0, f"查询 '{sql}' 没有返回任何数据"
    
    @allure.step("验证数据不存在: {sql}")
    def validate_data_not_exists(self, sql: str, params: Tuple = None):
        """验证数据不存在"""
        result = self.db_helper.execute_query(sql, params)
        assert result.row_count == 0, f"查询 '{sql}' 返回了不应该存在的数据"
    
    @allure.step("验证字段值: {field} = {expected_value}")
    def validate_field_value(self, sql: str, field: str, expected_value: Any, params: Tuple = None):
        """验证字段值"""
        result = self.db_helper.execute_query(sql, params)
        assert result.row_count > 0, f"查询 '{sql}' 没有返回任何数据"
        
        first_row = result.get_first_row()
        actual_value = first_row.get(field)
        assert actual_value == expected_value, \
            f"字段 {field} 期望值 {expected_value}，实际值 {actual_value}"
    
    @allure.step("验证字段值包含: {field} contains {expected_text}")
    def validate_field_contains(self, sql: str, field: str, expected_text: str, params: Tuple = None):
        """验证字段值包含指定文本"""
        result = self.db_helper.execute_query(sql, params)
        assert result.row_count > 0, f"查询 '{sql}' 没有返回任何数据"
        
        first_row = result.get_first_row()
        actual_value = str(first_row.get(field, ''))
        assert expected_text in actual_value, \
            f"字段 {field} 值 '{actual_value}' 不包含 '{expected_text}'"
    
    @allure.step("验证字段值不为空: {field}")
    def validate_field_not_null(self, sql: str, field: str, params: Tuple = None):
        """验证字段值不为空"""
        result = self.db_helper.execute_query(sql, params)
        assert result.row_count > 0, f"查询 '{sql}' 没有返回任何数据"
        
        first_row = result.get_first_row()
        actual_value = first_row.get(field)
        assert actual_value is not None, f"字段 {field} 的值不应该为NULL"
        assert str(actual_value).strip() != '', f"字段 {field} 的值不应该为空字符串"


class DatabaseTestHelper:
    """数据库测试辅助类"""
    
    def __init__(self, config: DatabaseConfig):
        self.db_helper = DatabaseHelper(config)
        self.validator = DatabaseValidator(self.db_helper)
        self.backups = {}  # 存储备份表名
    
    def setup(self):
        """测试前置设置"""
        self.db_helper.connect()
    
    def teardown(self):
        """测试后置清理"""
        # 清理备份表
        for backup_table in self.backups.values():
            try:
                self.db_helper.execute_command(f"DROP TABLE IF EXISTS {backup_table}")
            except Exception:
                pass
        
        self.db_helper.disconnect()
    
    def backup_and_restore_context(self, table_name: str):
        """备份和恢复上下文管理器"""
        class BackupRestoreContext:
            def __init__(self, helper, table):
                self.helper = helper
                self.table = table
                self.backup_table = None
            
            def __enter__(self):
                self.backup_table = self.helper.db_helper.backup_table(self.table)
                self.helper.backups[self.table] = self.backup_table
                return self
            
            def __exit__(self, exc_type, exc_val, exc_tb):
                if self.backup_table:
                    self.helper.db_helper.restore_table(self.table, self.backup_table)
        
        return BackupRestoreContext(self, table_name)
    
    def execute_test_scenario(self, scenario: Dict[str, Any]):
        """执行数据库测试场景
        
        scenario格式:
        {
            "name": "测试场景名称",
            "setup_sql": ["INSERT INTO users ...", "UPDATE ..."],
            "test_sql": "SELECT * FROM users WHERE id = 1",
            "validations": [
                {"type": "row_count", "table": "users", "expected": 1},
                {"type": "field_value", "sql": "SELECT name FROM users WHERE id=1", "field": "name", "value": "test"}
            ],
            "cleanup_sql": ["DELETE FROM users WHERE id = 1"]
        }
        """
        
        try:
            # 执行设置SQL
            setup_sqls = scenario.get('setup_sql', [])
            for sql in setup_sqls:
                self.db_helper.execute_command(sql)
            
            # 执行测试SQL
            test_sql = scenario.get('test_sql')
            if test_sql:
                result = self.db_helper.execute_query(test_sql)
            
            # 执行验证
            validations = scenario.get('validations', [])
            for validation in validations:
                validation_type = validation['type']
                
                if validation_type == 'row_count':
                    self.validator.validate_row_count(
                        validation['table'], 
                        validation['expected'],
                        validation.get('where', '')
                    )
                elif validation_type == 'data_exists':
                    self.validator.validate_data_exists(
                        validation['sql'],
                        validation.get('params')
                    )
                elif validation_type == 'data_not_exists':
                    self.validator.validate_data_not_exists(
                        validation['sql'],
                        validation.get('params')
                    )
                elif validation_type == 'field_value':
                    self.validator.validate_field_value(
                        validation['sql'],
                        validation['field'],
                        validation['value'],
                        validation.get('params')
                    )
                elif validation_type == 'field_not_null':
                    self.validator.validate_field_not_null(
                        validation['sql'],
                        validation['field'],
                        validation.get('params')
                    )
        
        finally:
            # 执行清理SQL
            cleanup_sqls = scenario.get('cleanup_sql', [])
            for sql in cleanup_sqls:
                try:
                    self.db_helper.execute_command(sql)
                except Exception as e:
                    self.db_helper.logger.warning(f"清理SQL执行失败: {e}")


# 数据库连接池
class DatabasePool:
    """数据库连接池"""
    
    def __init__(self, config: DatabaseConfig, pool_size: int = 5):
        self.config = config
        self.pool_size = pool_size
        self.connections = []
        self.available_connections = []
        self.logger = logging.getLogger(__name__)
        
        # 初始化连接池
        self._initialize_pool()
    
    def _initialize_pool(self):
        """初始化连接池"""
        for _ in range(self.pool_size):
            helper = DatabaseHelper(self.config)
            helper.connect()
            self.connections.append(helper)
            self.available_connections.append(helper)
    
    @contextmanager
    def get_connection(self) -> DatabaseHelper:
        """从连接池获取连接"""
        if not self.available_connections:
            raise RuntimeError("连接池中没有可用连接")
        
        connection = self.available_connections.pop()
        try:
            yield connection
        finally:
            self.available_connections.append(connection)
    
    def close_all(self):
        """关闭所有连接"""
        for connection in self.connections:
            connection.disconnect()
        self.connections.clear()
        self.available_connections.clear()


# 数据库迁移辅助类
class DatabaseMigration:
    """数据库迁移辅助类"""
    
    def __init__(self, db_helper: DatabaseHelper):
        self.db_helper = db_helper
        self.migration_table = 'schema_migrations'
        self._ensure_migration_table()
    
    def _ensure_migration_table(self):
        """确保迁移表存在"""
        if not self.db_helper.table_exists(self.migration_table):
            sql = f"""
            CREATE TABLE {self.migration_table} (
                version VARCHAR(255) PRIMARY KEY,
                applied_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
            """
            self.db_helper.execute_command(sql)
    
    def apply_migration(self, version: str, sql: str):
        """应用迁移"""
        # 检查是否已应用
        check_sql = f"SELECT version FROM {self.migration_table} WHERE version = ?"
        if self.db_helper.config.db_type != DatabaseType.SQLITE:
            check_sql = check_sql.replace('?', '%s')
        
        result = self.db_helper.execute_query(check_sql, (version,))
        if result.row_count > 0:
            self.db_helper.logger.info(f"迁移 {version} 已经应用过")
            return
        
        # 应用迁移
        self.db_helper.execute_command(sql)
        
        # 记录迁移
        insert_sql = f"INSERT INTO {self.migration_table} (version) VALUES (?)"
        if self.db_helper.config.db_type != DatabaseType.SQLITE:
            insert_sql = insert_sql.replace('?', '%s')
        
        self.db_helper.execute_command(insert_sql, (version,))
        self.db_helper.logger.info(f"迁移 {version} 应用成功")
    
    def get_applied_migrations(self) -> List[str]:
        """获取已应用的迁移"""
        sql = f"SELECT version FROM {self.migration_table} ORDER BY applied_at"
        result = self.db_helper.execute_query(sql)
        return [row['version'] for row in result.rows]