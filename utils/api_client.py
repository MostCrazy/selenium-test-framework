#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
API客户端模块
提供HTTP请求、认证、响应验证等功能
"""

import json
import time
import logging
from datetime import datetime, timedelta
from typing import Dict, Any, Optional, List, Union
from enum import Enum
from dataclasses import dataclass, field
from urllib.parse import urljoin, urlparse

import requests
import allure
import jwt
from requests.auth import HTTPBasicAuth, HTTPDigestAuth
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry


class HTTPMethod(Enum):
    """HTTP方法枚举"""
    GET = "GET"
    POST = "POST"
    PUT = "PUT"
    DELETE = "DELETE"
    PATCH = "PATCH"
    HEAD = "HEAD"
    OPTIONS = "OPTIONS"


class AuthType(Enum):
    """认证类型枚举"""
    NONE = "none"
    BASIC = "basic"
    BEARER = "bearer"
    API_KEY = "api_key"
    DIGEST = "digest"
    OAUTH2 = "oauth2"
    JWT = "jwt"


@dataclass
class APIResponse:
    """API响应数据类"""
    status_code: int
    text: str
    headers: Dict[str, str]
    json_data: Optional[Dict[str, Any]] = None
    response_time: float = 0.0
    url: str = ""
    request_method: str = ""
    request_headers: Dict[str, str] = field(default_factory=dict)
    request_body: Optional[str] = None
    cookies: Dict[str, str] = field(default_factory=dict)
    encoding: str = "utf-8"
    
    def __post_init__(self):
        """初始化后处理"""
        if self.json_data is None and self.text:
            try:
                self.json_data = json.loads(self.text)
            except (json.JSONDecodeError, ValueError):
                pass
    
    @property
    def is_success(self) -> bool:
        """判断请求是否成功"""
        return 200 <= self.status_code < 300
    
    @property
    def is_client_error(self) -> bool:
        """判断是否为客户端错误"""
        return 400 <= self.status_code < 500
    
    @property
    def is_server_error(self) -> bool:
        """判断是否为服务器错误"""
        return 500 <= self.status_code < 600


@dataclass
class AuthConfig:
    """认证配置"""
    auth_type: AuthType = AuthType.NONE
    username: str = ""
    password: str = ""
    token: str = ""
    api_key: str = ""
    api_key_header: str = "X-API-Key"
    oauth2_url: str = ""
    client_id: str = ""
    client_secret: str = ""
    scope: str = ""
    jwt_secret: str = ""
    jwt_algorithm: str = "HS256"
    jwt_payload: Dict[str, Any] = field(default_factory=dict)


class APIClient:
    """API客户端类"""
    
    def __init__(self, base_url: str, auth_config: AuthConfig = None, 
                 timeout: int = 30, verify_ssl: bool = True,
                 retry_config: Dict[str, Any] = None):
        """
        初始化API客户端
        
        Args:
            base_url: 基础URL
            auth_config: 认证配置
            timeout: 请求超时时间
            verify_ssl: 是否验证SSL证书
            retry_config: 重试配置
        """
        self.base_url = base_url.rstrip('/')
        self.auth_config = auth_config or AuthConfig()
        self.timeout = timeout
        self.verify_ssl = verify_ssl
        self.logger = logging.getLogger(self.__class__.__name__)
        
        # 创建会话
        self.session = requests.Session()
        
        # 配置重试策略
        if retry_config:
            retry_strategy = Retry(
                total=retry_config.get('total', 3),
                status_forcelist=retry_config.get('status_forcelist', [429, 500, 502, 503, 504]),
                method_whitelist=retry_config.get('method_whitelist', ["HEAD", "GET", "OPTIONS"]),
                backoff_factor=retry_config.get('backoff_factor', 1)
            )
            adapter = HTTPAdapter(max_retries=retry_strategy)
            self.session.mount("http://", adapter)
            self.session.mount("https://", adapter)
        
        # 设置认证
        self._setup_auth()
    
    def _setup_auth(self):
        """设置认证"""
        if self.auth_config.auth_type == AuthType.BASIC:
            self.session.auth = HTTPBasicAuth(
                self.auth_config.username, 
                self.auth_config.password
            )
        elif self.auth_config.auth_type == AuthType.DIGEST:
            self.session.auth = HTTPDigestAuth(
                self.auth_config.username, 
                self.auth_config.password
            )
        elif self.auth_config.auth_type == AuthType.BEARER:
            self.session.headers.update({
                'Authorization': f'Bearer {self.auth_config.token}'
            })
        elif self.auth_config.auth_type == AuthType.API_KEY:
            self.session.headers.update({
                self.auth_config.api_key_header: self.auth_config.api_key
            })
        elif self.auth_config.auth_type == AuthType.JWT:
            token = self._generate_jwt_token()
            self.session.headers.update({
                'Authorization': f'Bearer {token}'
            })
    
    def _generate_jwt_token(self) -> str:
        """生成JWT令牌"""
        payload = self.auth_config.jwt_payload.copy()
        if 'exp' not in payload:
            payload['exp'] = datetime.utcnow() + timedelta(hours=1)
        
        return jwt.encode(
            payload, 
            self.auth_config.jwt_secret, 
            algorithm=self.auth_config.jwt_algorithm
        )
    
    def set_header(self, key: str, value: str):
        """设置请求头"""
        self.session.headers[key] = value
    
    def remove_header(self, key: str):
        """移除请求头"""
        self.session.headers.pop(key, None)
    
    def set_cookie(self, key: str, value: str):
        """设置Cookie"""
        self.session.cookies[key] = value
    
    def clear_cookies(self):
        """清除所有Cookie"""
        self.session.cookies.clear()
    
    def _build_url(self, endpoint: str) -> str:
        """构建完整URL"""
        if endpoint.startswith(('http://', 'https://')):
            return endpoint
        return urljoin(self.base_url + '/', endpoint.lstrip('/'))
    
    def _prepare_request_data(self, data: Any) -> tuple:
        """准备请求数据"""
        json_data = None
        request_body = None
        
        if data is not None:
            if isinstance(data, (dict, list)):
                json_data = data
                request_body = json.dumps(data, ensure_ascii=False)
                if 'Content-Type' not in self.session.headers:
                    self.session.headers['Content-Type'] = 'application/json'
            else:
                request_body = str(data)
        
        return json_data, request_body
    
    @allure.step("发送{method}请求: {endpoint}")
    def request(self, method: Union[HTTPMethod, str], endpoint: str, 
               params: Dict[str, Any] = None, data: Any = None,
               headers: Dict[str, str] = None, files: Dict[str, Any] = None,
               **kwargs) -> APIResponse:
        """发送HTTP请求"""
        
        # 转换方法类型
        if isinstance(method, HTTPMethod):
            method = method.value
        
        # 构建URL
        url = self._build_url(endpoint)
        
        # 准备请求头
        request_headers = self.session.headers.copy()
        if headers:
            request_headers.update(headers)
        
        # 准备请求数据
        json_data, request_body = self._prepare_request_data(data)
        
        # 记录请求信息
        self.logger.info(f"发送{method}请求: {url}")
        self.logger.debug(f"请求参数: {params}")
        self.logger.debug(f"请求头: {request_headers}")
        self.logger.debug(f"请求体: {request_body}")
        
        try:
            # 发送请求
            start_time = time.time()
            
            response = self.session.request(
                method=method,
                url=url,
                params=params,
                json=json_data if json_data is not None else None,
                data=data if json_data is None and files is None else None,
                headers=headers,
                files=files,
                timeout=self.timeout,
                verify=self.verify_ssl,
                **kwargs
            )
            
            response_time = time.time() - start_time
            
            # 创建响应对象
            api_response = APIResponse(
                status_code=response.status_code,
                text=response.text,
                headers=dict(response.headers),
                json_data=json_data,
                response_time=response_time,
                url=url,
                request_method=method,
                request_headers=dict(self.session.headers),
                request_body=request_body,
                cookies=dict(response.cookies),
                encoding=response.encoding or 'utf-8'
            )
            
            # 记录响应信息
            self.logger.info(f"响应状态: {response.status_code}")
            self.logger.info(f"响应时间: {response_time:.3f}s")
            self.logger.debug(f"响应头: {dict(response.headers)}")
            self.logger.debug(f"响应内容: {response.text[:500]}..." if len(response.text) > 500 else response.text)
            
            # Allure报告附件
            allure.attach(
                json.dumps({
                    'method': method,
                    'url': url,
                    'params': params,
                    'headers': headers,
                    'body': request_body
                }, ensure_ascii=False, indent=2),
                name="请求信息",
                attachment_type=allure.attachment_type.JSON
            )
            
            allure.attach(
                json.dumps({
                    'status_code': response.status_code,
                    'headers': dict(response.headers),
                    'response_time': response_time,
                    'body': response.text
                }, ensure_ascii=False, indent=2),
                name="响应信息",
                attachment_type=allure.attachment_type.JSON
            )
            
            return api_response
            
        except requests.exceptions.RequestException as e:
            self.logger.error(f"请求失败: {e}")
            raise
    
    def get(self, endpoint: str, params: Dict[str, Any] = None, 
           headers: Dict[str, str] = None, **kwargs) -> APIResponse:
        """发送GET请求"""
        return self.request(HTTPMethod.GET, endpoint, params=params, headers=headers, **kwargs)
    
    def post(self, endpoint: str, data: Any = None, params: Dict[str, Any] = None,
            headers: Dict[str, str] = None, files: Dict[str, Any] = None, **kwargs) -> APIResponse:
        """发送POST请求"""
        return self.request(HTTPMethod.POST, endpoint, params=params, data=data, 
                          headers=headers, files=files, **kwargs)
    
    def put(self, endpoint: str, data: Any = None, params: Dict[str, Any] = None,
           headers: Dict[str, str] = None, **kwargs) -> APIResponse:
        """发送PUT请求"""
        return self.request(HTTPMethod.PUT, endpoint, params=params, data=data, headers=headers, **kwargs)
    
    def delete(self, endpoint: str, params: Dict[str, Any] = None,
              headers: Dict[str, str] = None, **kwargs) -> APIResponse:
        """发送DELETE请求"""
        return self.request(HTTPMethod.DELETE, endpoint, params=params, headers=headers, **kwargs)
    
    def patch(self, endpoint: str, data: Any = None, params: Dict[str, Any] = None,
             headers: Dict[str, str] = None, **kwargs) -> APIResponse:
        """发送PATCH请求"""
        return self.request(HTTPMethod.PATCH, endpoint, params=params, data=data, headers=headers, **kwargs)
    
    def head(self, endpoint: str, params: Dict[str, Any] = None,
            headers: Dict[str, str] = None, **kwargs) -> APIResponse:
        """发送HEAD请求"""
        return self.request(HTTPMethod.HEAD, endpoint, params=params, headers=headers, **kwargs)
    
    def options(self, endpoint: str, params: Dict[str, Any] = None,
               headers: Dict[str, str] = None, **kwargs) -> APIResponse:
        """发送OPTIONS请求"""
        return self.request(HTTPMethod.OPTIONS, endpoint, params=params, headers=headers, **kwargs)


class APIValidator:
    """API响应验证器"""
    
    @staticmethod
    @allure.step("验证状态码: {expected_status}")
    def validate_status_code(response: APIResponse, expected_status: int):
        """验证状态码"""
        assert response.status_code == expected_status, \
            f"期望状态码 {expected_status}，实际状态码 {response.status_code}"
    
    @staticmethod
    @allure.step("验证响应时间小于: {max_time}s")
    def validate_response_time(response: APIResponse, max_time: float):
        """验证响应时间"""
        assert response.response_time <= max_time, \
            f"响应时间 {response.response_time:.3f}s 超过最大限制 {max_time}s"
    
    @staticmethod
    @allure.step("验证响应头包含: {header_name}")
    def validate_header_exists(response: APIResponse, header_name: str):
        """验证响应头存在"""
        assert header_name in response.headers, \
            f"响应头中缺少 {header_name}"
    
    @staticmethod
    @allure.step("验证响应头值: {header_name} = {expected_value}")
    def validate_header_value(response: APIResponse, header_name: str, expected_value: str):
        """验证响应头值"""
        actual_value = response.headers.get(header_name)
        assert actual_value == expected_value, \
            f"响应头 {header_name} 期望值 {expected_value}，实际值 {actual_value}"
    
    @staticmethod
    @allure.step("验证JSON字段存在: {field_path}")
    def validate_json_field_exists(response: APIResponse, field_path: str):
        """验证JSON字段存在"""
        assert response.json_data is not None, "响应不是有效的JSON格式"
        
        fields = field_path.split('.')
        current_data = response.json_data
        
        for field in fields:
            if isinstance(current_data, dict):
                assert field in current_data, f"JSON字段 {field_path} 不存在"
                current_data = current_data[field]
            elif isinstance(current_data, list) and field.isdigit():
                index = int(field)
                assert 0 <= index < len(current_data), f"JSON数组索引 {index} 超出范围"
                current_data = current_data[index]
            else:
                raise AssertionError(f"无法访问JSON字段 {field_path}")
    
    @staticmethod
    @allure.step("验证JSON字段值: {field_path} = {expected_value}")
    def validate_json_field_value(response: APIResponse, field_path: str, expected_value: Any):
        """验证JSON字段值"""
        APIValidator.validate_json_field_exists(response, field_path)
        
        fields = field_path.split('.')
        current_data = response.json_data
        
        for field in fields:
            if isinstance(current_data, dict):
                current_data = current_data[field]
            elif isinstance(current_data, list) and field.isdigit():
                current_data = current_data[int(field)]
        
        assert current_data == expected_value, \
            f"JSON字段 {field_path} 期望值 {expected_value}，实际值 {current_data}"
    
    @staticmethod
    @allure.step("验证JSON模式")
    def validate_json_schema(response: APIResponse, schema: Dict[str, Any]):
        """验证JSON模式"""
        try:
            import jsonschema
            jsonschema.validate(response.json_data, schema)
        except ImportError:
            raise ImportError("需要安装jsonschema库: pip install jsonschema")
        except jsonschema.ValidationError as e:
            raise AssertionError(f"JSON模式验证失败: {e.message}")
    
    @staticmethod
    @allure.step("验证响应包含文本: {text}")
    def validate_text_contains(response: APIResponse, text: str):
        """验证响应文本包含指定内容"""
        assert text in response.text, \
            f"响应文本中不包含 '{text}'"
    
    @staticmethod
    @allure.step("验证响应不包含文本: {text}")
    def validate_text_not_contains(response: APIResponse, text: str):
        """验证响应文本不包含指定内容"""
        assert text not in response.text, \
            f"响应文本中包含不应该存在的内容 '{text}'"


class APITestHelper:
    """API测试辅助类"""
    
    def __init__(self, client: APIClient):
        self.client = client
        self.validator = APIValidator()
    
    @allure.step("执行API测试用例")
    def execute_test_case(self, test_case: Dict[str, Any]) -> APIResponse:
        """执行API测试用例
        
        test_case格式:
        {
            "name": "测试用例名称",
            "method": "GET",
            "endpoint": "/api/users",
            "params": {"page": 1},
            "data": {"name": "test"},
            "headers": {"X-Custom": "value"},
            "expected_status": 200,
            "expected_response_time": 2.0,
            "validations": [
                {"type": "json_field_exists", "field": "data.users"},
                {"type": "json_field_value", "field": "status", "value": "success"}
            ]
        }
        """
        
        # 发送请求
        response = self.client.request(
            method=test_case.get('method', 'GET'),
            endpoint=test_case['endpoint'],
            params=test_case.get('params'),
            data=test_case.get('data'),
            headers=test_case.get('headers')
        )
        
        # 执行验证
        if 'expected_status' in test_case:
            self.validator.validate_status_code(response, test_case['expected_status'])
        
        if 'expected_response_time' in test_case:
            self.validator.validate_response_time(response, test_case['expected_response_time'])
        
        # 执行自定义验证
        validations = test_case.get('validations', [])
        for validation in validations:
            validation_type = validation['type']
            
            if validation_type == 'json_field_exists':
                self.validator.validate_json_field_exists(response, validation['field'])
            elif validation_type == 'json_field_value':
                self.validator.validate_json_field_value(response, validation['field'], validation['value'])
            elif validation_type == 'header_exists':
                self.validator.validate_header_exists(response, validation['header'])
            elif validation_type == 'header_value':
                self.validator.validate_header_value(response, validation['header'], validation['value'])
            elif validation_type == 'text_contains':
                self.validator.validate_text_contains(response, validation['text'])
            elif validation_type == 'text_not_contains':
                self.validator.validate_text_not_contains(response, validation['text'])
        
        return response
    
    def execute_test_suite(self, test_suite: List[Dict[str, Any]]) -> List[APIResponse]:
        """执行API测试套件"""
        responses = []
        
        for test_case in test_suite:
            try:
                response = self.execute_test_case(test_case)
                responses.append(response)
            except Exception as e:
                self.client.logger.error(f"测试用例 {test_case.get('name', 'Unknown')} 执行失败: {e}")
                raise
        
        return responses


# OAuth2认证辅助类
class OAuth2Helper:
    """OAuth2认证辅助类"""
    
    @staticmethod
    def get_access_token(auth_url: str, client_id: str, client_secret: str, 
                        scope: str = "", grant_type: str = "client_credentials") -> str:
        """获取访问令牌"""
        data = {
            'grant_type': grant_type,
            'client_id': client_id,
            'client_secret': client_secret
        }
        
        if scope:
            data['scope'] = scope
        
        response = requests.post(auth_url, data=data)
        response.raise_for_status()
        
        token_data = response.json()
        return token_data['access_token']
    
    @staticmethod
    def create_auth_config(auth_url: str, client_id: str, client_secret: str, 
                          scope: str = "") -> AuthConfig:
        """创建OAuth2认证配置"""
        token = OAuth2Helper.get_access_token(auth_url, client_id, client_secret, scope)
        
        return AuthConfig(
            auth_type=AuthType.BEARER,
            token=token,
            oauth2_url=auth_url,
            client_id=client_id,
            client_secret=client_secret,
            scope=scope
        )


# JWT令牌辅助类
class JWTHelper:
    """JWT令牌辅助类"""
    
    @staticmethod
    def create_token(payload: Dict[str, Any], secret: str, algorithm: str = "HS256", 
                    expires_in: int = 3600) -> str:
        """创建JWT令牌"""
        if expires_in > 0:
            payload['exp'] = datetime.utcnow() + timedelta(seconds=expires_in)
        
        return jwt.encode(payload, secret, algorithm=algorithm)
    
    @staticmethod
    def decode_token(token: str, secret: str, algorithms: List[str] = None) -> Dict[str, Any]:
        """解码JWT令牌"""
        if algorithms is None:
            algorithms = ["HS256"]
        
        return jwt.decode(token, secret, algorithms=algorithms)
    
    @staticmethod
    def is_token_expired(token: str) -> bool:
        """检查令牌是否过期"""
        try:
            payload = jwt.decode(token, options={"verify_signature": False})
            exp = payload.get('exp')
            if exp:
                return datetime.utcnow().timestamp() > exp
            return False
        except jwt.InvalidTokenError:
            return True