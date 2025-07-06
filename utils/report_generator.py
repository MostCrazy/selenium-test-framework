#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
测试报告生成器
支持生成多种格式的测试报告
"""

import os
import json
import xml.etree.ElementTree as ET
from pathlib import Path
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional
import sqlite3
from dataclasses import dataclass, asdict

from .logger_setup import get_logger
from .config_manager import get_config_manager

# 获取日志器
test_logger = get_logger(__name__)


@dataclass
class TestResult:
    """测试结果数据类"""
    test_name: str
    status: str  # passed, failed, skipped, error
    duration: float
    start_time: str
    end_time: str
    error_message: str = ""
    error_type: str = ""
    test_file: str = ""
    test_class: str = ""
    test_method: str = ""
    browser: str = ""
    environment: str = ""
    screenshot_path: str = ""
    video_path: str = ""
    logs: List[str] = None
    
    def __post_init__(self):
        if self.logs is None:
            self.logs = []


@dataclass
class TestSuite:
    """测试套件数据类"""
    name: str
    tests: List[TestResult]
    start_time: str
    end_time: str
    duration: float
    total: int = 0
    passed: int = 0
    failed: int = 0
    skipped: int = 0
    errors: int = 0
    
    def __post_init__(self):
        self.total = len(self.tests)
        self.passed = len([t for t in self.tests if t.status == 'passed'])
        self.failed = len([t for t in self.tests if t.status == 'failed'])
        self.skipped = len([t for t in self.tests if t.status == 'skipped'])
        self.errors = len([t for t in self.tests if t.status == 'error'])


class ReportGenerator:
    """报告生成器类"""
    
    def __init__(self, reports_dir: str = "reports"):
        """
        初始化报告生成器
        
        Args:
            reports_dir: 报告目录
        """
        self.reports_dir = Path(reports_dir)
        self.reports_dir.mkdir(exist_ok=True)
        
        # 创建子目录
        self.json_dir = self.reports_dir / "json"
        self.html_dir = self.reports_dir / "html"
        self.xml_dir = self.reports_dir / "xml"
        self.db_dir = self.reports_dir / "database"
        
        for dir_path in [self.json_dir, self.html_dir, self.xml_dir, self.db_dir]:
            dir_path.mkdir(exist_ok=True)
        
        # 数据库文件
        self.db_file = self.db_dir / "test_results.db"
        self._init_database()
    
    def _init_database(self):
        """初始化数据库"""
        try:
            with sqlite3.connect(self.db_file) as conn:
                cursor = conn.cursor()
                
                # 创建测试套件表
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS test_suites (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        name TEXT NOT NULL,
                        start_time TEXT NOT NULL,
                        end_time TEXT NOT NULL,
                        duration REAL NOT NULL,
                        total INTEGER NOT NULL,
                        passed INTEGER NOT NULL,
                        failed INTEGER NOT NULL,
                        skipped INTEGER NOT NULL,
                        errors INTEGER NOT NULL,
                        created_at TEXT DEFAULT CURRENT_TIMESTAMP
                    )
                """)
                
                # 创建测试结果表
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS test_results (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        suite_id INTEGER,
                        test_name TEXT NOT NULL,
                        status TEXT NOT NULL,
                        duration REAL NOT NULL,
                        start_time TEXT NOT NULL,
                        end_time TEXT NOT NULL,
                        error_message TEXT,
                        error_type TEXT,
                        test_file TEXT,
                        test_class TEXT,
                        test_method TEXT,
                        browser TEXT,
                        environment TEXT,
                        screenshot_path TEXT,
                        video_path TEXT,
                        logs TEXT,
                        created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                        FOREIGN KEY (suite_id) REFERENCES test_suites (id)
                    )
                """)
                
                conn.commit()
                test_logger.debug("数据库初始化完成")
                
        except Exception as e:
            test_logger.error(f"数据库初始化失败: {str(e)}")
    
    def parse_allure_results(self, allure_results_dir: str) -> TestSuite:
        """
        解析Allure结果文件
        
        Args:
            allure_results_dir: Allure结果目录
            
        Returns:
            TestSuite: 测试套件对象
        """
        results_dir = Path(allure_results_dir)
        if not results_dir.exists():
            test_logger.warning(f"Allure结果目录不存在: {allure_results_dir}")
            return TestSuite("Empty", [], "", "", 0.0)
        
        tests = []
        start_times = []
        end_times = []
        
        try:
            # 解析结果文件
            for result_file in results_dir.glob("*-result.json"):
                with open(result_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                
                # 提取测试信息
                test_name = data.get('name', 'Unknown')
                status = data.get('status', 'unknown').lower()
                
                # 时间信息
                start_time = data.get('start', 0)
                stop_time = data.get('stop', 0)
                duration = (stop_time - start_time) / 1000.0 if stop_time > start_time else 0.0
                
                start_dt = datetime.fromtimestamp(start_time / 1000) if start_time else datetime.now()
                end_dt = datetime.fromtimestamp(stop_time / 1000) if stop_time else datetime.now()
                
                start_times.append(start_dt)
                end_times.append(end_dt)
                
                # 错误信息
                error_message = ""
                error_type = ""
                if 'statusDetails' in data:
                    error_message = data['statusDetails'].get('message', '')
                    error_type = data['statusDetails'].get('trace', '')
                
                # 标签信息
                labels = {label['name']: label['value'] for label in data.get('labels', [])}
                
                # 附件信息
                attachments = data.get('attachments', [])
                screenshot_path = ""
                video_path = ""
                
                for attachment in attachments:
                    if 'screenshot' in attachment.get('name', '').lower():
                        screenshot_path = attachment.get('source', '')
                    elif 'video' in attachment.get('name', '').lower():
                        video_path = attachment.get('source', '')
                
                # 创建测试结果
                test_result = TestResult(
                    test_name=test_name,
                    status=status,
                    duration=duration,
                    start_time=start_dt.strftime('%Y-%m-%d %H:%M:%S'),
                    end_time=end_dt.strftime('%Y-%m-%d %H:%M:%S'),
                    error_message=error_message,
                    error_type=error_type,
                    test_file=labels.get('suite', ''),
                    test_class=labels.get('parentSuite', ''),
                    test_method=labels.get('subSuite', ''),
                    browser=labels.get('browser', ''),
                    environment=labels.get('environment', ''),
                    screenshot_path=screenshot_path,
                    video_path=video_path
                )
                
                tests.append(test_result)
            
            # 计算套件时间
            if start_times and end_times:
                suite_start = min(start_times)
                suite_end = max(end_times)
                suite_duration = (suite_end - suite_start).total_seconds()
            else:
                suite_start = suite_end = datetime.now()
                suite_duration = 0.0
            
            # 创建测试套件
            test_suite = TestSuite(
                name="Allure Test Suite",
                tests=tests,
                start_time=suite_start.strftime('%Y-%m-%d %H:%M:%S'),
                end_time=suite_end.strftime('%Y-%m-%d %H:%M:%S'),
                duration=suite_duration
            )
            
            test_logger.info(f"解析Allure结果完成: {len(tests)}个测试用例")
            return test_suite
            
        except Exception as e:
            test_logger.error(f"解析Allure结果失败: {str(e)}")
            return TestSuite("Error", [], "", "", 0.0)
    
    def parse_junit_xml(self, xml_file: str) -> TestSuite:
        """
        解析JUnit XML文件
        
        Args:
            xml_file: XML文件路径
            
        Returns:
            TestSuite: 测试套件对象
        """
        try:
            tree = ET.parse(xml_file)
            root = tree.getroot()
            
            tests = []
            
            # 解析测试用例
            for testcase in root.findall('.//testcase'):
                test_name = testcase.get('name', 'Unknown')
                classname = testcase.get('classname', '')
                time_str = testcase.get('time', '0')
                duration = float(time_str) if time_str else 0.0
                
                # 确定状态
                status = 'passed'
                error_message = ""
                error_type = ""
                
                if testcase.find('failure') is not None:
                    status = 'failed'
                    failure = testcase.find('failure')
                    error_message = failure.get('message', '')
                    error_type = failure.get('type', '')
                elif testcase.find('error') is not None:
                    status = 'error'
                    error = testcase.find('error')
                    error_message = error.get('message', '')
                    error_type = error.get('type', '')
                elif testcase.find('skipped') is not None:
                    status = 'skipped'
                
                # 创建测试结果
                now = datetime.now()
                test_result = TestResult(
                    test_name=test_name,
                    status=status,
                    duration=duration,
                    start_time=now.strftime('%Y-%m-%d %H:%M:%S'),
                    end_time=(now + timedelta(seconds=duration)).strftime('%Y-%m-%d %H:%M:%S'),
                    error_message=error_message,
                    error_type=error_type,
                    test_class=classname
                )
                
                tests.append(test_result)
            
            # 套件信息
            suite_name = root.get('name', 'JUnit Test Suite')
            timestamp = root.get('timestamp', datetime.now().isoformat())
            
            # 创建测试套件
            total_duration = sum(test.duration for test in tests)
            start_time = datetime.now()
            end_time = start_time + timedelta(seconds=total_duration)
            
            test_suite = TestSuite(
                name=suite_name,
                tests=tests,
                start_time=start_time.strftime('%Y-%m-%d %H:%M:%S'),
                end_time=end_time.strftime('%Y-%m-%d %H:%M:%S'),
                duration=total_duration
            )
            
            test_logger.info(f"解析JUnit XML完成: {len(tests)}个测试用例")
            return test_suite
            
        except Exception as e:
            test_logger.error(f"解析JUnit XML失败: {str(e)}")
            return TestSuite("Error", [], "", "", 0.0)
    
    def save_to_database(self, test_suite: TestSuite) -> int:
        """
        保存测试结果到数据库
        
        Args:
            test_suite: 测试套件对象
            
        Returns:
            int: 套件ID
        """
        try:
            with sqlite3.connect(self.db_file) as conn:
                cursor = conn.cursor()
                
                # 插入测试套件
                cursor.execute("""
                    INSERT INTO test_suites 
                    (name, start_time, end_time, duration, total, passed, failed, skipped, errors)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    test_suite.name,
                    test_suite.start_time,
                    test_suite.end_time,
                    test_suite.duration,
                    test_suite.total,
                    test_suite.passed,
                    test_suite.failed,
                    test_suite.skipped,
                    test_suite.errors
                ))
                
                suite_id = cursor.lastrowid
                
                # 插入测试结果
                for test in test_suite.tests:
                    cursor.execute("""
                        INSERT INTO test_results 
                        (suite_id, test_name, status, duration, start_time, end_time, 
                         error_message, error_type, test_file, test_class, test_method,
                         browser, environment, screenshot_path, video_path, logs)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """, (
                        suite_id,
                        test.test_name,
                        test.status,
                        test.duration,
                        test.start_time,
                        test.end_time,
                        test.error_message,
                        test.error_type,
                        test.test_file,
                        test.test_class,
                        test.test_method,
                        test.browser,
                        test.environment,
                        test.screenshot_path,
                        test.video_path,
                        json.dumps(test.logs)
                    ))
                
                conn.commit()
                test_logger.info(f"测试结果已保存到数据库，套件ID: {suite_id}")
                return suite_id
                
        except Exception as e:
            test_logger.error(f"保存到数据库失败: {str(e)}")
            return -1
    
    def generate_json_report(self, test_suite: TestSuite, filename: str = None) -> str:
        """
        生成JSON格式报告
        
        Args:
            test_suite: 测试套件对象
            filename: 文件名
            
        Returns:
            str: 报告文件路径
        """
        try:
            if not filename:
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                filename = f"test_report_{timestamp}.json"
            
            report_file = self.json_dir / filename
            
            # 转换为字典
            report_data = {
                'suite': asdict(test_suite),
                'summary': {
                    'total': test_suite.total,
                    'passed': test_suite.passed,
                    'failed': test_suite.failed,
                    'skipped': test_suite.skipped,
                    'errors': test_suite.errors,
                    'pass_rate': (test_suite.passed / test_suite.total * 100) if test_suite.total > 0 else 0,
                    'duration': test_suite.duration
                },
                'generated_at': datetime.now().isoformat()
            }
            
            # 写入文件
            with open(report_file, 'w', encoding='utf-8') as f:
                json.dump(report_data, f, ensure_ascii=False, indent=2)
            
            test_logger.info(f"JSON报告生成完成: {report_file}")
            return str(report_file)
            
        except Exception as e:
            test_logger.error(f"生成JSON报告失败: {str(e)}")
            return ""
    
    def generate_html_report(self, test_suite: TestSuite, filename: str = None) -> str:
        """
        生成HTML格式报告
        
        Args:
            test_suite: 测试套件对象
            filename: 文件名
            
        Returns:
            str: 报告文件路径
        """
        try:
            if not filename:
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                filename = f"test_report_{timestamp}.html"
            
            report_file = self.html_dir / filename
            
            # 计算统计信息
            pass_rate = (test_suite.passed / test_suite.total * 100) if test_suite.total > 0 else 0
            
            # 生成测试用例表格
            test_rows = ""
            for i, test in enumerate(test_suite.tests, 1):
                status_class = f"status-{test.status}"
                status_icon = {
                    'passed': '✅',
                    'failed': '❌',
                    'skipped': '⏭️',
                    'error': '💥'
                }.get(test.status, '❓')
                
                error_cell = ""
                if test.error_message:
                    error_cell = f'<div class="error-message" title="{test.error_message}">{test.error_message[:100]}...</div>'
                
                test_rows += f"""
                <tr class="{status_class}">
                    <td>{i}</td>
                    <td>{test.test_name}</td>
                    <td><span class="status-badge {status_class}">{status_icon} {test.status.upper()}</span></td>
                    <td>{test.duration:.2f}s</td>
                    <td>{test.start_time}</td>
                    <td>{error_cell}</td>
                </tr>
                """
            
            # HTML模板
            html_content = f"""
            <!DOCTYPE html>
            <html lang="zh-CN">
            <head>
                <meta charset="UTF-8">
                <meta name="viewport" content="width=device-width, initial-scale=1.0">
                <title>自动化测试报告 - {test_suite.name}</title>
                <style>
                    * {{
                        margin: 0;
                        padding: 0;
                        box-sizing: border-box;
                    }}
                    body {{
                        font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
                        line-height: 1.6;
                        color: #333;
                        background: #f8f9fa;
                    }}
                    .container {{
                        max-width: 1200px;
                        margin: 0 auto;
                        padding: 20px;
                    }}
                    .header {{
                        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                        color: white;
                        padding: 30px;
                        border-radius: 10px;
                        text-align: center;
                        margin-bottom: 30px;
                        box-shadow: 0 4px 6px rgba(0,0,0,0.1);
                    }}
                    .header h1 {{
                        font-size: 2.5em;
                        margin-bottom: 10px;
                    }}
                    .summary {{
                        display: grid;
                        grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
                        gap: 20px;
                        margin-bottom: 30px;
                    }}
                    .summary-card {{
                        background: white;
                        padding: 20px;
                        border-radius: 10px;
                        text-align: center;
                        box-shadow: 0 2px 4px rgba(0,0,0,0.1);
                        border-left: 4px solid #007bff;
                    }}
                    .summary-card.passed {{ border-left-color: #28a745; }}
                    .summary-card.failed {{ border-left-color: #dc3545; }}
                    .summary-card.skipped {{ border-left-color: #ffc107; }}
                    .summary-card.errors {{ border-left-color: #fd7e14; }}
                    .summary-number {{
                        font-size: 2.5em;
                        font-weight: bold;
                        margin-bottom: 5px;
                    }}
                    .summary-label {{
                        color: #6c757d;
                        font-size: 0.9em;
                    }}
                    .progress-section {{
                        background: white;
                        padding: 25px;
                        border-radius: 10px;
                        margin-bottom: 30px;
                        box-shadow: 0 2px 4px rgba(0,0,0,0.1);
                    }}
                    .progress-bar {{
                        background: #e9ecef;
                        border-radius: 10px;
                        height: 25px;
                        overflow: hidden;
                        margin: 15px 0;
                    }}
                    .progress-fill {{
                        background: linear-gradient(90deg, #28a745, #20c997);
                        height: 100%;
                        border-radius: 10px;
                        width: {pass_rate}%;
                        transition: width 0.3s ease;
                    }}
                    .tests-table {{
                        background: white;
                        border-radius: 10px;
                        overflow: hidden;
                        box-shadow: 0 2px 4px rgba(0,0,0,0.1);
                    }}
                    .table-header {{
                        background: #495057;
                        color: white;
                        padding: 20px;
                    }}
                    table {{
                        width: 100%;
                        border-collapse: collapse;
                    }}
                    th, td {{
                        padding: 12px;
                        text-align: left;
                        border-bottom: 1px solid #dee2e6;
                    }}
                    th {{
                        background: #f8f9fa;
                        font-weight: 600;
                        color: #495057;
                    }}
                    .status-badge {{
                        padding: 4px 8px;
                        border-radius: 15px;
                        font-size: 0.8em;
                        font-weight: bold;
                    }}
                    .status-passed {{
                        background: #d4edda;
                        color: #155724;
                    }}
                    .status-failed {{
                        background: #f8d7da;
                        color: #721c24;
                    }}
                    .status-skipped {{
                        background: #fff3cd;
                        color: #856404;
                    }}
                    .status-error {{
                        background: #f5c6cb;
                        color: #721c24;
                    }}
                    .error-message {{
                        color: #dc3545;
                        font-size: 0.9em;
                        max-width: 300px;
                        overflow: hidden;
                        text-overflow: ellipsis;
                        white-space: nowrap;
                        cursor: help;
                    }}
                    .footer {{
                        text-align: center;
                        color: #6c757d;
                        margin-top: 30px;
                        padding: 20px;
                    }}
                    @media (max-width: 768px) {{
                        .container {{ padding: 10px; }}
                        .header {{ padding: 20px; }}
                        .header h1 {{ font-size: 2em; }}
                        .summary {{ grid-template-columns: repeat(2, 1fr); }}
                        table {{ font-size: 0.9em; }}
                    }}
                </style>
            </head>
            <body>
                <div class="container">
                    <div class="header">
                        <h1>🚀 自动化测试报告</h1>
                        <p>{test_suite.name}</p>
                        <p>执行时间: {test_suite.start_time} - {test_suite.end_time}</p>
                    </div>
                    
                    <div class="summary">
                        <div class="summary-card">
                            <div class="summary-number">{test_suite.total}</div>
                            <div class="summary-label">总计</div>
                        </div>
                        <div class="summary-card passed">
                            <div class="summary-number">{test_suite.passed}</div>
                            <div class="summary-label">通过</div>
                        </div>
                        <div class="summary-card failed">
                            <div class="summary-number">{test_suite.failed}</div>
                            <div class="summary-label">失败</div>
                        </div>
                        <div class="summary-card skipped">
                            <div class="summary-number">{test_suite.skipped}</div>
                            <div class="summary-label">跳过</div>
                        </div>
                        <div class="summary-card errors">
                            <div class="summary-number">{test_suite.errors}</div>
                            <div class="summary-label">错误</div>
                        </div>
                    </div>
                    
                    <div class="progress-section">
                        <h3>通过率: {pass_rate:.1f}%</h3>
                        <div class="progress-bar">
                            <div class="progress-fill"></div>
                        </div>
                        <p>执行时长: {test_suite.duration:.2f} 秒</p>
                    </div>
                    
                    <div class="tests-table">
                        <div class="table-header">
                            <h3>📋 测试用例详情</h3>
                        </div>
                        <table>
                            <thead>
                                <tr>
                                    <th>#</th>
                                    <th>测试用例</th>
                                    <th>状态</th>
                                    <th>耗时</th>
                                    <th>开始时间</th>
                                    <th>错误信息</th>
                                </tr>
                            </thead>
                            <tbody>
                                {test_rows}
                            </tbody>
                        </table>
                    </div>
                    
                    <div class="footer">
                        <p>报告生成时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</p>
                        <p>由自动化测试框架生成</p>
                    </div>
                </div>
            </body>
            </html>
            """
            
            # 写入文件
            with open(report_file, 'w', encoding='utf-8') as f:
                f.write(html_content)
            
            test_logger.info(f"HTML报告生成完成: {report_file}")
            return str(report_file)
            
        except Exception as e:
            test_logger.error(f"生成HTML报告失败: {str(e)}")
            return ""
    
    def get_test_history(self, days: int = 30) -> List[Dict[str, Any]]:
        """
        获取测试历史数据
        
        Args:
            days: 查询天数
            
        Returns:
            List[Dict]: 历史数据列表
        """
        try:
            with sqlite3.connect(self.db_file) as conn:
                cursor = conn.cursor()
                
                # 查询最近的测试套件
                cursor.execute("""
                    SELECT * FROM test_suites 
                    WHERE created_at >= datetime('now', '-{} days')
                    ORDER BY created_at DESC
                """.format(days))
                
                columns = [desc[0] for desc in cursor.description]
                results = []
                
                for row in cursor.fetchall():
                    results.append(dict(zip(columns, row)))
                
                test_logger.info(f"获取到{len(results)}条历史记录")
                return results
                
        except Exception as e:
            test_logger.error(f"获取测试历史失败: {str(e)}")
            return []
    
    def generate_trend_report(self, days: int = 30) -> str:
        """
        生成趋势报告
        
        Args:
            days: 分析天数
            
        Returns:
            str: 报告文件路径
        """
        try:
            history_data = self.get_test_history(days)
            
            if not history_data:
                test_logger.warning("没有历史数据，无法生成趋势报告")
                return ""
            
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            report_file = self.html_dir / f"trend_report_{timestamp}.html"
            
            # 准备图表数据
            dates = []
            pass_rates = []
            totals = []
            
            for record in reversed(history_data[-30:]):  # 最近30条记录
                date = record['created_at'][:10]  # 只取日期部分
                pass_rate = (record['passed'] / record['total'] * 100) if record['total'] > 0 else 0
                
                dates.append(date)
                pass_rates.append(pass_rate)
                totals.append(record['total'])
            
            # 生成HTML内容（简化版，实际项目中可以使用Chart.js等图表库）
            html_content = f"""
            <!DOCTYPE html>
            <html lang="zh-CN">
            <head>
                <meta charset="UTF-8">
                <meta name="viewport" content="width=device-width, initial-scale=1.0">
                <title>测试趋势报告</title>
                <style>
                    body {{
                        font-family: Arial, sans-serif;
                        margin: 20px;
                        background: #f8f9fa;
                    }}
                    .container {{
                        max-width: 1000px;
                        margin: 0 auto;
                        background: white;
                        padding: 30px;
                        border-radius: 10px;
                        box-shadow: 0 2px 4px rgba(0,0,0,0.1);
                    }}
                    .header {{
                        text-align: center;
                        margin-bottom: 30px;
                        padding-bottom: 20px;
                        border-bottom: 2px solid #e9ecef;
                    }}
                    .stats {{
                        display: grid;
                        grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
                        gap: 20px;
                        margin-bottom: 30px;
                    }}
                    .stat-card {{
                        background: #f8f9fa;
                        padding: 20px;
                        border-radius: 8px;
                        text-align: center;
                    }}
                    .stat-number {{
                        font-size: 2em;
                        font-weight: bold;
                        color: #495057;
                    }}
                    .history-table {{
                        width: 100%;
                        border-collapse: collapse;
                        margin-top: 20px;
                    }}
                    .history-table th,
                    .history-table td {{
                        padding: 12px;
                        text-align: left;
                        border-bottom: 1px solid #dee2e6;
                    }}
                    .history-table th {{
                        background: #f8f9fa;
                        font-weight: 600;
                    }}
                </style>
            </head>
            <body>
                <div class="container">
                    <div class="header">
                        <h1>📈 测试趋势报告</h1>
                        <p>最近 {days} 天的测试执行趋势</p>
                    </div>
                    
                    <div class="stats">
                        <div class="stat-card">
                            <div class="stat-number">{len(history_data)}</div>
                            <div>总执行次数</div>
                        </div>
                        <div class="stat-card">
                            <div class="stat-number">{sum(r['total'] for r in history_data)}</div>
                            <div>总测试用例</div>
                        </div>
                        <div class="stat-card">
                            <div class="stat-number">{sum(r['passed'] for r in history_data)}</div>
                            <div>总通过数</div>
                        </div>
                        <div class="stat-card">
                            <div class="stat-number">{sum(r['failed'] for r in history_data)}</div>
                            <div>总失败数</div>
                        </div>
                    </div>
                    
                    <h3>📋 执行历史</h3>
                    <table class="history-table">
                        <thead>
                            <tr>
                                <th>日期</th>
                                <th>套件名称</th>
                                <th>总计</th>
                                <th>通过</th>
                                <th>失败</th>
                                <th>跳过</th>
                                <th>通过率</th>
                                <th>耗时</th>
                            </tr>
                        </thead>
                        <tbody>
            """
            
            for record in history_data:
                pass_rate = (record['passed'] / record['total'] * 100) if record['total'] > 0 else 0
                html_content += f"""
                            <tr>
                                <td>{record['created_at'][:16]}</td>
                                <td>{record['name']}</td>
                                <td>{record['total']}</td>
                                <td>{record['passed']}</td>
                                <td>{record['failed']}</td>
                                <td>{record['skipped']}</td>
                                <td>{pass_rate:.1f}%</td>
                                <td>{record['duration']:.1f}s</td>
                            </tr>
                """
            
            html_content += """
                        </tbody>
                    </table>
                    
                    <div style="margin-top: 30px; text-align: center; color: #6c757d;">
                        <p>报告生成时间: {}</p>
                    </div>
                </div>
            </body>
            </html>
            """.format(datetime.now().strftime('%Y-%m-%d %H:%M:%S'))
            
            # 写入文件
            with open(report_file, 'w', encoding='utf-8') as f:
                f.write(html_content)
            
            test_logger.info(f"趋势报告生成完成: {report_file}")
            return str(report_file)
            
        except Exception as e:
            test_logger.error(f"生成趋势报告失败: {str(e)}")
            return ""


# 便捷函数
def generate_reports_from_allure(allure_results_dir: str, 
                                reports_dir: str = "reports") -> Dict[str, str]:
    """
    从Allure结果生成所有格式的报告
    
    Args:
        allure_results_dir: Allure结果目录
        reports_dir: 报告输出目录
        
    Returns:
        Dict[str, str]: 生成的报告文件路径字典
    """
    generator = ReportGenerator(reports_dir)
    
    # 解析Allure结果
    test_suite = generator.parse_allure_results(allure_results_dir)
    
    if test_suite.total == 0:
        test_logger.warning("没有找到测试结果")
        return {}
    
    # 生成各种格式的报告
    reports = {}
    
    # JSON报告
    json_file = generator.generate_json_report(test_suite)
    if json_file:
        reports['json'] = json_file
    
    # HTML报告
    html_file = generator.generate_html_report(test_suite)
    if html_file:
        reports['html'] = html_file
    
    # 保存到数据库
    suite_id = generator.save_to_database(test_suite)
    if suite_id > 0:
        reports['database_id'] = suite_id
    
    return reports


if __name__ == "__main__":
    # 测试报告生成
    generator = ReportGenerator()
    
    # 创建测试数据
    test_results = [
        TestResult(
            test_name="test_login_success",
            status="passed",
            duration=2.5,
            start_time="2024-01-15 10:00:00",
            end_time="2024-01-15 10:00:02"
        ),
        TestResult(
            test_name="test_login_invalid",
            status="failed",
            duration=1.8,
            start_time="2024-01-15 10:00:03",
            end_time="2024-01-15 10:00:05",
            error_message="Invalid credentials"
        )
    ]
    
    test_suite = TestSuite(
        name="Login Tests",
        tests=test_results,
        start_time="2024-01-15 10:00:00",
        end_time="2024-01-15 10:00:05",
        duration=5.0
    )
    
    # 生成报告
    json_file = generator.generate_json_report(test_suite)
    html_file = generator.generate_html_report(test_suite)
    suite_id = generator.save_to_database(test_suite)
    
    print(f"JSON报告: {json_file}")
    print(f"HTML报告: {html_file}")
    print(f"数据库ID: {suite_id}")