#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
性能监控工具
提供页面性能、资源监控、响应时间分析等功能
"""

import time
import psutil
import logging
import json
import statistics
from typing import Dict, List, Any, Optional, Callable, Union
from dataclasses import dataclass, field
from enum import Enum
from datetime import datetime, timedelta
from contextlib import contextmanager
import threading
import allure
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
import requests


class PerformanceMetricType(Enum):
    """性能指标类型"""
    RESPONSE_TIME = "response_time"
    PAGE_LOAD_TIME = "page_load_time"
    FIRST_CONTENTFUL_PAINT = "first_contentful_paint"
    LARGEST_CONTENTFUL_PAINT = "largest_contentful_paint"
    CUMULATIVE_LAYOUT_SHIFT = "cumulative_layout_shift"
    FIRST_INPUT_DELAY = "first_input_delay"
    TIME_TO_INTERACTIVE = "time_to_interactive"
    MEMORY_USAGE = "memory_usage"
    CPU_USAGE = "cpu_usage"
    NETWORK_USAGE = "network_usage"
    RESOURCE_COUNT = "resource_count"
    ERROR_RATE = "error_rate"


class AlertLevel(Enum):
    """告警级别"""
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"


@dataclass
class PerformanceMetric:
    """性能指标"""
    name: str
    value: float
    unit: str
    timestamp: datetime
    metric_type: PerformanceMetricType
    tags: Dict[str, str] = field(default_factory=dict)
    threshold: Optional[float] = None
    
    def is_within_threshold(self) -> bool:
        """检查是否在阈值范围内"""
        if self.threshold is None:
            return True
        return self.value <= self.threshold
    
    def get_alert_level(self) -> AlertLevel:
        """获取告警级别"""
        if self.threshold is None:
            return AlertLevel.INFO
        
        ratio = self.value / self.threshold
        if ratio <= 0.8:
            return AlertLevel.INFO
        elif ratio <= 1.0:
            return AlertLevel.WARNING
        elif ratio <= 1.5:
            return AlertLevel.ERROR
        else:
            return AlertLevel.CRITICAL


@dataclass
class PerformanceReport:
    """性能报告"""
    test_name: str
    start_time: datetime
    end_time: datetime
    metrics: List[PerformanceMetric]
    summary: Dict[str, Any] = field(default_factory=dict)
    alerts: List[Dict[str, Any]] = field(default_factory=list)
    
    @property
    def duration(self) -> timedelta:
        """测试持续时间"""
        return self.end_time - self.start_time
    
    def get_metrics_by_type(self, metric_type: PerformanceMetricType) -> List[PerformanceMetric]:
        """按类型获取指标"""
        return [m for m in self.metrics if m.metric_type == metric_type]
    
    def get_metric_statistics(self, metric_type: PerformanceMetricType) -> Dict[str, float]:
        """获取指标统计信息"""
        metrics = self.get_metrics_by_type(metric_type)
        if not metrics:
            return {}
        
        values = [m.value for m in metrics]
        return {
            'count': len(values),
            'min': min(values),
            'max': max(values),
            'mean': statistics.mean(values),
            'median': statistics.median(values),
            'std_dev': statistics.stdev(values) if len(values) > 1 else 0,
            'p95': self._percentile(values, 95),
            'p99': self._percentile(values, 99)
        }
    
    @staticmethod
    def _percentile(values: List[float], percentile: int) -> float:
        """计算百分位数"""
        sorted_values = sorted(values)
        index = (percentile / 100) * (len(sorted_values) - 1)
        if index.is_integer():
            return sorted_values[int(index)]
        else:
            lower = sorted_values[int(index)]
            upper = sorted_values[int(index) + 1]
            return lower + (upper - lower) * (index - int(index))
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            'test_name': self.test_name,
            'start_time': self.start_time.isoformat(),
            'end_time': self.end_time.isoformat(),
            'duration_seconds': self.duration.total_seconds(),
            'metrics_count': len(self.metrics),
            'summary': self.summary,
            'alerts_count': len(self.alerts),
            'metrics': [{
                'name': m.name,
                'value': m.value,
                'unit': m.unit,
                'type': m.metric_type.value,
                'timestamp': m.timestamp.isoformat(),
                'tags': m.tags,
                'threshold': m.threshold,
                'alert_level': m.get_alert_level().value
            } for m in self.metrics]
        }


class SystemMonitor:
    """系统资源监控器"""
    
    def __init__(self, interval: float = 1.0):
        self.interval = interval
        self.monitoring = False
        self.metrics = []
        self.monitor_thread = None
        self.logger = logging.getLogger(__name__)
    
    def start_monitoring(self):
        """开始监控"""
        if self.monitoring:
            return
        
        self.monitoring = True
        self.metrics.clear()
        self.monitor_thread = threading.Thread(target=self._monitor_loop)
        self.monitor_thread.daemon = True
        self.monitor_thread.start()
        self.logger.info("系统监控已启动")
    
    def stop_monitoring(self) -> List[PerformanceMetric]:
        """停止监控并返回指标"""
        if not self.monitoring:
            return []
        
        self.monitoring = False
        if self.monitor_thread:
            self.monitor_thread.join(timeout=5)
        
        self.logger.info(f"系统监控已停止，收集了 {len(self.metrics)} 个指标")
        return self.metrics.copy()
    
    def _monitor_loop(self):
        """监控循环"""
        while self.monitoring:
            try:
                timestamp = datetime.now()
                
                # CPU使用率
                cpu_percent = psutil.cpu_percent(interval=None)
                self.metrics.append(PerformanceMetric(
                    name="CPU使用率",
                    value=cpu_percent,
                    unit="%",
                    timestamp=timestamp,
                    metric_type=PerformanceMetricType.CPU_USAGE,
                    threshold=80.0
                ))
                
                # 内存使用率
                memory = psutil.virtual_memory()
                self.metrics.append(PerformanceMetric(
                    name="内存使用率",
                    value=memory.percent,
                    unit="%",
                    timestamp=timestamp,
                    metric_type=PerformanceMetricType.MEMORY_USAGE,
                    threshold=85.0
                ))
                
                # 网络IO
                network = psutil.net_io_counters()
                self.metrics.append(PerformanceMetric(
                    name="网络发送字节",
                    value=network.bytes_sent,
                    unit="bytes",
                    timestamp=timestamp,
                    metric_type=PerformanceMetricType.NETWORK_USAGE
                ))
                
                self.metrics.append(PerformanceMetric(
                    name="网络接收字节",
                    value=network.bytes_recv,
                    unit="bytes",
                    timestamp=timestamp,
                    metric_type=PerformanceMetricType.NETWORK_USAGE
                ))
                
                time.sleep(self.interval)
                
            except Exception as e:
                self.logger.error(f"系统监控错误: {e}")
                time.sleep(self.interval)


class WebPerformanceMonitor:
    """Web性能监控器"""
    
    def __init__(self, driver: webdriver.Remote):
        self.driver = driver
        self.logger = logging.getLogger(__name__)
    
    @allure.step("获取页面性能指标")
    def get_page_performance_metrics(self) -> List[PerformanceMetric]:
        """获取页面性能指标"""
        metrics = []
        timestamp = datetime.now()
        
        try:
            # 获取导航时间
            navigation_timing = self.driver.execute_script("""
                return window.performance.timing;
            """)
            
            if navigation_timing:
                # 页面加载时间
                load_time = navigation_timing['loadEventEnd'] - navigation_timing['navigationStart']
                if load_time > 0:
                    metrics.append(PerformanceMetric(
                        name="页面加载时间",
                        value=load_time,
                        unit="ms",
                        timestamp=timestamp,
                        metric_type=PerformanceMetricType.PAGE_LOAD_TIME,
                        threshold=3000.0
                    ))
                
                # DOM内容加载时间
                dom_content_loaded = navigation_timing['domContentLoadedEventEnd'] - navigation_timing['navigationStart']
                if dom_content_loaded > 0:
                    metrics.append(PerformanceMetric(
                        name="DOM内容加载时间",
                        value=dom_content_loaded,
                        unit="ms",
                        timestamp=timestamp,
                        metric_type=PerformanceMetricType.PAGE_LOAD_TIME,
                        threshold=2000.0
                    ))
            
            # 获取Paint时间
            paint_timing = self.driver.execute_script("""
                const paintEntries = performance.getEntriesByType('paint');
                const result = {};
                paintEntries.forEach(entry => {
                    result[entry.name] = entry.startTime;
                });
                return result;
            """)
            
            if paint_timing:
                # 首次内容绘制
                if 'first-contentful-paint' in paint_timing:
                    metrics.append(PerformanceMetric(
                        name="首次内容绘制",
                        value=paint_timing['first-contentful-paint'],
                        unit="ms",
                        timestamp=timestamp,
                        metric_type=PerformanceMetricType.FIRST_CONTENTFUL_PAINT,
                        threshold=1500.0
                    ))
            
            # 获取资源信息
            resources = self.driver.execute_script("""
                return performance.getEntriesByType('resource').map(entry => ({
                    name: entry.name,
                    duration: entry.duration,
                    size: entry.transferSize || 0,
                    type: entry.initiatorType
                }));
            """)
            
            if resources:
                # 资源数量
                metrics.append(PerformanceMetric(
                    name="资源总数",
                    value=len(resources),
                    unit="个",
                    timestamp=timestamp,
                    metric_type=PerformanceMetricType.RESOURCE_COUNT,
                    threshold=100.0
                ))
                
                # 资源总大小
                total_size = sum(r.get('size', 0) for r in resources)
                metrics.append(PerformanceMetric(
                    name="资源总大小",
                    value=total_size,
                    unit="bytes",
                    timestamp=timestamp,
                    metric_type=PerformanceMetricType.NETWORK_USAGE,
                    threshold=5 * 1024 * 1024  # 5MB
                ))
                
                # 平均资源加载时间
                durations = [r.get('duration', 0) for r in resources if r.get('duration', 0) > 0]
                if durations:
                    avg_duration = statistics.mean(durations)
                    metrics.append(PerformanceMetric(
                        name="平均资源加载时间",
                        value=avg_duration,
                        unit="ms",
                        timestamp=timestamp,
                        metric_type=PerformanceMetricType.RESPONSE_TIME,
                        threshold=500.0
                    ))
            
            # 获取内存使用情况（如果支持）
            try:
                memory_info = self.driver.execute_script("""
                    if (window.performance && window.performance.memory) {
                        return {
                            usedJSHeapSize: window.performance.memory.usedJSHeapSize,
                            totalJSHeapSize: window.performance.memory.totalJSHeapSize,
                            jsHeapSizeLimit: window.performance.memory.jsHeapSizeLimit
                        };
                    }
                    return null;
                """)
                
                if memory_info:
                    metrics.append(PerformanceMetric(
                        name="JS堆内存使用",
                        value=memory_info['usedJSHeapSize'],
                        unit="bytes",
                        timestamp=timestamp,
                        metric_type=PerformanceMetricType.MEMORY_USAGE,
                        threshold=50 * 1024 * 1024  # 50MB
                    ))
            except Exception:
                pass  # 某些浏览器不支持memory API
            
        except Exception as e:
            self.logger.error(f"获取页面性能指标失败: {e}")
        
        return metrics
    
    @allure.step("获取Core Web Vitals指标")
    def get_core_web_vitals(self) -> List[PerformanceMetric]:
        """获取Core Web Vitals指标"""
        metrics = []
        timestamp = datetime.now()
        
        try:
            # 使用Web Vitals库获取指标（需要页面加载该库）
            vitals_script = """
                return new Promise((resolve) => {
                    const vitals = {};
                    
                    // LCP - Largest Contentful Paint
                    if (window.PerformanceObserver) {
                        new PerformanceObserver((entryList) => {
                            const entries = entryList.getEntries();
                            const lastEntry = entries[entries.length - 1];
                            vitals.lcp = lastEntry.startTime;
                        }).observe({entryTypes: ['largest-contentful-paint']});
                        
                        // FID - First Input Delay
                        new PerformanceObserver((entryList) => {
                            const entries = entryList.getEntries();
                            entries.forEach(entry => {
                                vitals.fid = entry.processingStart - entry.startTime;
                            });
                        }).observe({entryTypes: ['first-input']});
                        
                        // CLS - Cumulative Layout Shift
                        let clsValue = 0;
                        new PerformanceObserver((entryList) => {
                            for (const entry of entryList.getEntries()) {
                                if (!entry.hadRecentInput) {
                                    clsValue += entry.value;
                                }
                            }
                            vitals.cls = clsValue;
                        }).observe({entryTypes: ['layout-shift']});
                    }
                    
                    // 等待一段时间收集指标
                    setTimeout(() => resolve(vitals), 2000);
                });
            """
            
            vitals = self.driver.execute_async_script(vitals_script)
            
            if vitals:
                # Largest Contentful Paint
                if 'lcp' in vitals:
                    metrics.append(PerformanceMetric(
                        name="最大内容绘制",
                        value=vitals['lcp'],
                        unit="ms",
                        timestamp=timestamp,
                        metric_type=PerformanceMetricType.LARGEST_CONTENTFUL_PAINT,
                        threshold=2500.0
                    ))
                
                # First Input Delay
                if 'fid' in vitals:
                    metrics.append(PerformanceMetric(
                        name="首次输入延迟",
                        value=vitals['fid'],
                        unit="ms",
                        timestamp=timestamp,
                        metric_type=PerformanceMetricType.FIRST_INPUT_DELAY,
                        threshold=100.0
                    ))
                
                # Cumulative Layout Shift
                if 'cls' in vitals:
                    metrics.append(PerformanceMetric(
                        name="累积布局偏移",
                        value=vitals['cls'],
                        unit="score",
                        timestamp=timestamp,
                        metric_type=PerformanceMetricType.CUMULATIVE_LAYOUT_SHIFT,
                        threshold=0.1
                    ))
            
        except Exception as e:
            self.logger.error(f"获取Core Web Vitals指标失败: {e}")
        
        return metrics


class APIPerformanceMonitor:
    """API性能监控器"""
    
    def __init__(self):
        self.logger = logging.getLogger(__name__)
    
    @allure.step("监控API响应时间")
    def monitor_api_response_time(self, url: str, method: str = 'GET', 
                                 headers: Dict[str, str] = None, 
                                 data: Any = None, 
                                 timeout: int = 30) -> PerformanceMetric:
        """监控API响应时间"""
        start_time = time.time()
        timestamp = datetime.now()
        
        try:
            response = requests.request(
                method=method,
                url=url,
                headers=headers,
                json=data if isinstance(data, dict) else None,
                data=data if not isinstance(data, dict) else None,
                timeout=timeout
            )
            
            response_time = (time.time() - start_time) * 1000  # 转换为毫秒
            
            return PerformanceMetric(
                name=f"API响应时间 - {method} {url}",
                value=response_time,
                unit="ms",
                timestamp=timestamp,
                metric_type=PerformanceMetricType.RESPONSE_TIME,
                tags={
                    'url': url,
                    'method': method,
                    'status_code': str(response.status_code)
                },
                threshold=2000.0
            )
            
        except Exception as e:
            response_time = (time.time() - start_time) * 1000
            self.logger.error(f"API请求失败: {e}")
            
            return PerformanceMetric(
                name=f"API响应时间 - {method} {url}",
                value=response_time,
                unit="ms",
                timestamp=timestamp,
                metric_type=PerformanceMetricType.RESPONSE_TIME,
                tags={
                    'url': url,
                    'method': method,
                    'error': str(e)
                },
                threshold=2000.0
            )


class PerformanceTestRunner:
    """性能测试运行器"""
    
    def __init__(self, test_name: str):
        self.test_name = test_name
        self.start_time = None
        self.end_time = None
        self.metrics = []
        self.system_monitor = SystemMonitor()
        self.logger = logging.getLogger(__name__)
    
    def start_test(self):
        """开始性能测试"""
        self.start_time = datetime.now()
        self.metrics.clear()
        self.system_monitor.start_monitoring()
        self.logger.info(f"性能测试开始: {self.test_name}")
    
    def add_metric(self, metric: PerformanceMetric):
        """添加性能指标"""
        self.metrics.append(metric)
    
    def add_metrics(self, metrics: List[PerformanceMetric]):
        """批量添加性能指标"""
        self.metrics.extend(metrics)
    
    @contextmanager
    def measure_operation(self, operation_name: str, threshold: float = None):
        """测量操作耗时"""
        start_time = time.time()
        timestamp = datetime.now()
        
        try:
            yield
        finally:
            duration = (time.time() - start_time) * 1000  # 转换为毫秒
            
            metric = PerformanceMetric(
                name=f"操作耗时 - {operation_name}",
                value=duration,
                unit="ms",
                timestamp=timestamp,
                metric_type=PerformanceMetricType.RESPONSE_TIME,
                threshold=threshold
            )
            
            self.add_metric(metric)
    
    def end_test(self) -> PerformanceReport:
        """结束性能测试并生成报告"""
        self.end_time = datetime.now()
        
        # 停止系统监控并收集指标
        system_metrics = self.system_monitor.stop_monitoring()
        self.metrics.extend(system_metrics)
        
        # 生成报告
        report = PerformanceReport(
            test_name=self.test_name,
            start_time=self.start_time,
            end_time=self.end_time,
            metrics=self.metrics
        )
        
        # 生成摘要
        report.summary = self._generate_summary(report)
        
        # 生成告警
        report.alerts = self._generate_alerts(report)
        
        self.logger.info(f"性能测试结束: {self.test_name}，收集了 {len(self.metrics)} 个指标")
        
        # 附加到Allure报告
        self._attach_to_allure(report)
        
        return report
    
    def _generate_summary(self, report: PerformanceReport) -> Dict[str, Any]:
        """生成性能摘要"""
        summary = {
            'test_duration_seconds': report.duration.total_seconds(),
            'total_metrics': len(report.metrics),
            'metric_types': {}
        }
        
        # 按类型统计指标
        for metric_type in PerformanceMetricType:
            stats = report.get_metric_statistics(metric_type)
            if stats:
                summary['metric_types'][metric_type.value] = stats
        
        return summary
    
    def _generate_alerts(self, report: PerformanceReport) -> List[Dict[str, Any]]:
        """生成性能告警"""
        alerts = []
        
        for metric in report.metrics:
            if not metric.is_within_threshold():
                alert = {
                    'metric_name': metric.name,
                    'value': metric.value,
                    'threshold': metric.threshold,
                    'unit': metric.unit,
                    'level': metric.get_alert_level().value,
                    'timestamp': metric.timestamp.isoformat(),
                    'tags': metric.tags
                }
                alerts.append(alert)
        
        return alerts
    
    def _attach_to_allure(self, report: PerformanceReport):
        """附加到Allure报告"""
        # 附加性能报告
        allure.attach(
            json.dumps(report.to_dict(), ensure_ascii=False, indent=2),
            name="性能测试报告",
            attachment_type=allure.attachment_type.JSON
        )
        
        # 附加告警信息
        if report.alerts:
            allure.attach(
                json.dumps(report.alerts, ensure_ascii=False, indent=2),
                name="性能告警",
                attachment_type=allure.attachment_type.JSON
            )


class PerformanceThresholds:
    """性能阈值配置"""
    
    # 默认阈值配置
    DEFAULT_THRESHOLDS = {
        PerformanceMetricType.PAGE_LOAD_TIME: 3000,  # 3秒
        PerformanceMetricType.FIRST_CONTENTFUL_PAINT: 1500,  # 1.5秒
        PerformanceMetricType.LARGEST_CONTENTFUL_PAINT: 2500,  # 2.5秒
        PerformanceMetricType.FIRST_INPUT_DELAY: 100,  # 100毫秒
        PerformanceMetricType.CUMULATIVE_LAYOUT_SHIFT: 0.1,  # 0.1分
        PerformanceMetricType.TIME_TO_INTERACTIVE: 3800,  # 3.8秒
        PerformanceMetricType.RESPONSE_TIME: 2000,  # 2秒
        PerformanceMetricType.CPU_USAGE: 80,  # 80%
        PerformanceMetricType.MEMORY_USAGE: 85,  # 85%
        PerformanceMetricType.RESOURCE_COUNT: 100,  # 100个资源
        PerformanceMetricType.ERROR_RATE: 5,  # 5%错误率
    }
    
    def __init__(self, custom_thresholds: Dict[PerformanceMetricType, float] = None):
        self.thresholds = self.DEFAULT_THRESHOLDS.copy()
        if custom_thresholds:
            self.thresholds.update(custom_thresholds)
    
    def get_threshold(self, metric_type: PerformanceMetricType) -> Optional[float]:
        """获取指标阈值"""
        return self.thresholds.get(metric_type)
    
    def set_threshold(self, metric_type: PerformanceMetricType, threshold: float):
        """设置指标阈值"""
        self.thresholds[metric_type] = threshold
    
    def apply_to_metric(self, metric: PerformanceMetric) -> PerformanceMetric:
        """应用阈值到指标"""
        if metric.threshold is None:
            metric.threshold = self.get_threshold(metric.metric_type)
        return metric


class PerformanceAnalyzer:
    """性能分析器"""
    
    @staticmethod
    def analyze_trends(reports: List[PerformanceReport], 
                      metric_type: PerformanceMetricType) -> Dict[str, Any]:
        """分析性能趋势"""
        if not reports:
            return {}
        
        trend_data = []
        for report in reports:
            stats = report.get_metric_statistics(metric_type)
            if stats:
                trend_data.append({
                    'timestamp': report.start_time.isoformat(),
                    'mean': stats['mean'],
                    'p95': stats['p95'],
                    'max': stats['max']
                })
        
        if not trend_data:
            return {}
        
        # 计算趋势
        means = [d['mean'] for d in trend_data]
        p95s = [d['p95'] for d in trend_data]
        
        return {
            'metric_type': metric_type.value,
            'data_points': len(trend_data),
            'trend_data': trend_data,
            'mean_trend': {
                'first': means[0],
                'last': means[-1],
                'change_percent': ((means[-1] - means[0]) / means[0] * 100) if means[0] != 0 else 0,
                'average': statistics.mean(means)
            },
            'p95_trend': {
                'first': p95s[0],
                'last': p95s[-1],
                'change_percent': ((p95s[-1] - p95s[0]) / p95s[0] * 100) if p95s[0] != 0 else 0,
                'average': statistics.mean(p95s)
            }
        }
    
    @staticmethod
    def compare_reports(baseline_report: PerformanceReport, 
                       current_report: PerformanceReport) -> Dict[str, Any]:
        """比较两个性能报告"""
        comparison = {
            'baseline': baseline_report.test_name,
            'current': current_report.test_name,
            'comparisons': {}
        }
        
        for metric_type in PerformanceMetricType:
            baseline_stats = baseline_report.get_metric_statistics(metric_type)
            current_stats = current_report.get_metric_statistics(metric_type)
            
            if baseline_stats and current_stats:
                comparison['comparisons'][metric_type.value] = {
                    'baseline_mean': baseline_stats['mean'],
                    'current_mean': current_stats['mean'],
                    'change_percent': ((current_stats['mean'] - baseline_stats['mean']) / baseline_stats['mean'] * 100) if baseline_stats['mean'] != 0 else 0,
                    'baseline_p95': baseline_stats['p95'],
                    'current_p95': current_stats['p95'],
                    'p95_change_percent': ((current_stats['p95'] - baseline_stats['p95']) / baseline_stats['p95'] * 100) if baseline_stats['p95'] != 0 else 0
                }
        
        return comparison
    
    @staticmethod
    def identify_bottlenecks(report: PerformanceReport) -> List[Dict[str, Any]]:
        """识别性能瓶颈"""
        bottlenecks = []
        
        # 检查超过阈值的指标
        for metric in report.metrics:
            if not metric.is_within_threshold() and metric.get_alert_level() in [AlertLevel.ERROR, AlertLevel.CRITICAL]:
                bottlenecks.append({
                    'metric_name': metric.name,
                    'value': metric.value,
                    'threshold': metric.threshold,
                    'severity': metric.get_alert_level().value,
                    'impact': 'high' if metric.get_alert_level() == AlertLevel.CRITICAL else 'medium'
                })
        
        # 按严重程度排序
        bottlenecks.sort(key=lambda x: (x['severity'] == 'critical', x['value'] / x['threshold'] if x['threshold'] else 0), reverse=True)
        
        return bottlenecks


# 性能测试装饰器
def performance_test(test_name: str = None, thresholds: Dict[PerformanceMetricType, float] = None):
    """性能测试装饰器"""
    def decorator(func):
        def wrapper(*args, **kwargs):
            name = test_name or func.__name__
            runner = PerformanceTestRunner(name)
            
            # 设置阈值
            if thresholds:
                threshold_config = PerformanceThresholds(thresholds)
            else:
                threshold_config = PerformanceThresholds()
            
            runner.start_test()
            
            try:
                # 执行测试函数
                result = func(*args, **kwargs)
                
                # 如果测试函数返回指标，添加到runner中
                if isinstance(result, list) and all(isinstance(m, PerformanceMetric) for m in result):
                    for metric in result:
                        threshold_config.apply_to_metric(metric)
                    runner.add_metrics(result)
                elif isinstance(result, PerformanceMetric):
                    threshold_config.apply_to_metric(result)
                    runner.add_metric(result)
                
                return result
                
            finally:
                # 生成性能报告
                report = runner.end_test()
                
                # 检查是否有严重的性能问题
                critical_alerts = [a for a in report.alerts if a['level'] == 'critical']
                if critical_alerts:
                    raise AssertionError(f"检测到严重性能问题: {len(critical_alerts)} 个关键告警")
        
        return wrapper
    return decorator