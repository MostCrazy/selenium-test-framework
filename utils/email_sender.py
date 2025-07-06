#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
邮件发送工具
支持HTML格式的测试报告邮件发送
"""

import os
import smtplib
import mimetypes
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.mime.base import MIMEBase
from email import encoders
from email.utils import formataddr
from pathlib import Path
from datetime import datetime
from typing import List, Optional, Dict, Any

from .logger import test_logger
from .config_reader import get_config


class EmailSender:
    """邮件发送器类"""
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """
        初始化邮件发送器
        
        Args:
            config: 邮件配置字典
        """
        self.config = config or get_config('email', {})
        self.smtp_server = self.config.get('smtp_server', 'smtp.gmail.com')
        self.smtp_port = self.config.get('smtp_port', 587)
        self.username = self.config.get('username', '')
        self.password = self.config.get('password', '')
        self.use_tls = self.config.get('use_tls', True)
        self.sender_name = self.config.get('sender_name', '自动化测试系统')
        
        # 默认收件人
        self.default_recipients = self.config.get('default_recipients', [])
        
        # 验证配置
        if not self.username or not self.password:
            test_logger.warning("邮件配置不完整，请检查用户名和密码")
    
    def send_test_report(self, 
                        recipients: List[str],
                        test_results: Dict[str, Any],
                        report_files: List[str] = None,
                        subject_prefix: str = "自动化测试报告") -> bool:
        """
        发送测试报告邮件
        
        Args:
            recipients: 收件人列表
            test_results: 测试结果字典
            report_files: 报告文件路径列表
            subject_prefix: 邮件主题前缀
            
        Returns:
            bool: 发送是否成功
        """
        try:
            # 生成邮件主题
            timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            status = "✅ 成功" if test_results.get('success', False) else "❌ 失败"
            subject = f"{subject_prefix} - {status} ({timestamp})"
            
            # 生成邮件内容
            html_content = self._generate_report_html(test_results)
            
            # 发送邮件
            return self.send_email(
                recipients=recipients,
                subject=subject,
                html_content=html_content,
                attachments=report_files or []
            )
            
        except Exception as e:
            test_logger.error(f"发送测试报告邮件失败: {str(e)}")
            return False
    
    def send_email(self,
                  recipients: List[str],
                  subject: str,
                  text_content: str = None,
                  html_content: str = None,
                  attachments: List[str] = None,
                  cc: List[str] = None,
                  bcc: List[str] = None) -> bool:
        """
        发送邮件
        
        Args:
            recipients: 收件人列表
            subject: 邮件主题
            text_content: 纯文本内容
            html_content: HTML内容
            attachments: 附件文件路径列表
            cc: 抄送列表
            bcc: 密送列表
            
        Returns:
            bool: 发送是否成功
        """
        try:
            # 验证配置
            if not self.username or not self.password:
                test_logger.error("邮件配置不完整")
                return False
            
            # 创建邮件对象
            msg = MIMEMultipart('alternative')
            msg['From'] = formataddr((self.sender_name, self.username))
            msg['To'] = ', '.join(recipients)
            msg['Subject'] = subject
            
            if cc:
                msg['Cc'] = ', '.join(cc)
            
            # 添加邮件内容
            if text_content:
                text_part = MIMEText(text_content, 'plain', 'utf-8')
                msg.attach(text_part)
            
            if html_content:
                html_part = MIMEText(html_content, 'html', 'utf-8')
                msg.attach(html_part)
            
            # 添加附件
            if attachments:
                for file_path in attachments:
                    if os.path.exists(file_path):
                        self._add_attachment(msg, file_path)
                    else:
                        test_logger.warning(f"附件文件不存在: {file_path}")
            
            # 准备收件人列表
            all_recipients = recipients.copy()
            if cc:
                all_recipients.extend(cc)
            if bcc:
                all_recipients.extend(bcc)
            
            # 发送邮件
            with smtplib.SMTP(self.smtp_server, self.smtp_port) as server:
                if self.use_tls:
                    server.starttls()
                
                server.login(self.username, self.password)
                server.send_message(msg, to_addrs=all_recipients)
            
            test_logger.info(f"邮件发送成功: {', '.join(recipients)}")
            return True
            
        except Exception as e:
            test_logger.error(f"邮件发送失败: {str(e)}")
            return False
    
    def _add_attachment(self, msg: MIMEMultipart, file_path: str):
        """
        添加附件到邮件
        
        Args:
            msg: 邮件对象
            file_path: 文件路径
        """
        try:
            file_path = Path(file_path)
            
            # 获取文件类型
            ctype, encoding = mimetypes.guess_type(str(file_path))
            if ctype is None or encoding is not None:
                ctype = 'application/octet-stream'
            
            maintype, subtype = ctype.split('/', 1)
            
            # 读取文件内容
            with open(file_path, 'rb') as fp:
                attachment = MIMEBase(maintype, subtype)
                attachment.set_payload(fp.read())
            
            # 编码附件
            encoders.encode_base64(attachment)
            
            # 设置附件头信息
            attachment.add_header(
                'Content-Disposition',
                f'attachment; filename="{file_path.name}"'
            )
            
            msg.attach(attachment)
            test_logger.debug(f"添加附件: {file_path.name}")
            
        except Exception as e:
            test_logger.error(f"添加附件失败 {file_path}: {str(e)}")
    
    def _generate_report_html(self, test_results: Dict[str, Any]) -> str:
        """
        生成测试报告HTML内容
        
        Args:
            test_results: 测试结果字典
            
        Returns:
            str: HTML内容
        """
        # 获取测试统计信息
        total = test_results.get('total', 0)
        passed = test_results.get('passed', 0)
        failed = test_results.get('failed', 0)
        skipped = test_results.get('skipped', 0)
        errors = test_results.get('errors', 0)
        
        # 计算通过率
        pass_rate = (passed / total * 100) if total > 0 else 0
        
        # 获取其他信息
        duration = test_results.get('duration', '未知')
        start_time = test_results.get('start_time', '未知')
        end_time = test_results.get('end_time', '未知')
        environment = test_results.get('environment', '未知')
        browser = test_results.get('browser', '未知')
        
        # 状态颜色
        status_color = "#28a745" if test_results.get('success', False) else "#dc3545"
        status_text = "成功" if test_results.get('success', False) else "失败"
        
        html_content = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <meta charset="UTF-8">
            <title>自动化测试报告</title>
            <style>
                body {{
                    font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
                    line-height: 1.6;
                    color: #333;
                    max-width: 800px;
                    margin: 0 auto;
                    padding: 20px;
                    background-color: #f8f9fa;
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
                    margin: 0;
                    font-size: 2.5em;
                    font-weight: 300;
                }}
                .status {{
                    display: inline-block;
                    padding: 8px 16px;
                    border-radius: 20px;
                    color: white;
                    font-weight: bold;
                    margin-top: 10px;
                    background-color: {status_color};
                }}
                .summary {{
                    background: white;
                    padding: 25px;
                    border-radius: 10px;
                    margin-bottom: 25px;
                    box-shadow: 0 2px 4px rgba(0,0,0,0.1);
                }}
                .summary h2 {{
                    color: #495057;
                    border-bottom: 2px solid #e9ecef;
                    padding-bottom: 10px;
                    margin-bottom: 20px;
                }}
                .stats {{
                    display: grid;
                    grid-template-columns: repeat(auto-fit, minmax(150px, 1fr));
                    gap: 15px;
                    margin-bottom: 20px;
                }}
                .stat-card {{
                    background: #f8f9fa;
                    padding: 15px;
                    border-radius: 8px;
                    text-align: center;
                    border-left: 4px solid #007bff;
                }}
                .stat-card.passed {{ border-left-color: #28a745; }}
                .stat-card.failed {{ border-left-color: #dc3545; }}
                .stat-card.skipped {{ border-left-color: #ffc107; }}
                .stat-card.errors {{ border-left-color: #fd7e14; }}
                .stat-number {{
                    font-size: 2em;
                    font-weight: bold;
                    color: #495057;
                }}
                .stat-label {{
                    color: #6c757d;
                    font-size: 0.9em;
                    margin-top: 5px;
                }}
                .progress-bar {{
                    background: #e9ecef;
                    border-radius: 10px;
                    height: 20px;
                    overflow: hidden;
                    margin: 15px 0;
                }}
                .progress-fill {{
                    background: linear-gradient(90deg, #28a745, #20c997);
                    height: 100%;
                    border-radius: 10px;
                    transition: width 0.3s ease;
                    width: {pass_rate}%;
                }}
                .info-grid {{
                    display: grid;
                    grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
                    gap: 15px;
                }}
                .info-item {{
                    display: flex;
                    justify-content: space-between;
                    padding: 10px 0;
                    border-bottom: 1px solid #e9ecef;
                }}
                .info-label {{
                    font-weight: 600;
                    color: #495057;
                }}
                .info-value {{
                    color: #6c757d;
                }}
                .links {{
                    background: white;
                    padding: 25px;
                    border-radius: 10px;
                    margin-bottom: 25px;
                    box-shadow: 0 2px 4px rgba(0,0,0,0.1);
                }}
                .links h2 {{
                    color: #495057;
                    border-bottom: 2px solid #e9ecef;
                    padding-bottom: 10px;
                    margin-bottom: 20px;
                }}
                .link-grid {{
                    display: grid;
                    grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
                    gap: 15px;
                }}
                .link-card {{
                    background: #f8f9fa;
                    padding: 15px;
                    border-radius: 8px;
                    text-align: center;
                    transition: transform 0.2s ease;
                }}
                .link-card:hover {{
                    transform: translateY(-2px);
                    box-shadow: 0 4px 8px rgba(0,0,0,0.1);
                }}
                .link-card a {{
                    color: #007bff;
                    text-decoration: none;
                    font-weight: 600;
                }}
                .link-card a:hover {{
                    color: #0056b3;
                }}
                .footer {{
                    text-align: center;
                    color: #6c757d;
                    margin-top: 30px;
                    padding-top: 20px;
                    border-top: 1px solid #e9ecef;
                }}
                @media (max-width: 600px) {{
                    body {{ padding: 10px; }}
                    .header {{ padding: 20px; }}
                    .header h1 {{ font-size: 2em; }}
                    .stats {{ grid-template-columns: repeat(2, 1fr); }}
                }}
            </style>
        </head>
        <body>
            <div class="header">
                <h1>🚀 自动化测试报告</h1>
                <div class="status">{status_text}</div>
            </div>
            
            <div class="summary">
                <h2>📊 测试统计</h2>
                <div class="stats">
                    <div class="stat-card">
                        <div class="stat-number">{total}</div>
                        <div class="stat-label">总计</div>
                    </div>
                    <div class="stat-card passed">
                        <div class="stat-number">{passed}</div>
                        <div class="stat-label">通过</div>
                    </div>
                    <div class="stat-card failed">
                        <div class="stat-number">{failed}</div>
                        <div class="stat-label">失败</div>
                    </div>
                    <div class="stat-card skipped">
                        <div class="stat-number">{skipped}</div>
                        <div class="stat-label">跳过</div>
                    </div>
                    <div class="stat-card errors">
                        <div class="stat-number">{errors}</div>
                        <div class="stat-label">错误</div>
                    </div>
                </div>
                
                <div>
                    <strong>通过率: {pass_rate:.1f}%</strong>
                    <div class="progress-bar">
                        <div class="progress-fill"></div>
                    </div>
                </div>
            </div>
            
            <div class="summary">
                <h2>ℹ️ 执行信息</h2>
                <div class="info-grid">
                    <div class="info-item">
                        <span class="info-label">开始时间:</span>
                        <span class="info-value">{start_time}</span>
                    </div>
                    <div class="info-item">
                        <span class="info-label">结束时间:</span>
                        <span class="info-value">{end_time}</span>
                    </div>
                    <div class="info-item">
                        <span class="info-label">执行时长:</span>
                        <span class="info-value">{duration}</span>
                    </div>
                    <div class="info-item">
                        <span class="info-label">测试环境:</span>
                        <span class="info-value">{environment}</span>
                    </div>
                    <div class="info-item">
                        <span class="info-label">浏览器:</span>
                        <span class="info-value">{browser}</span>
                    </div>
                </div>
            </div>
            
            <div class="links">
                <h2>🔗 相关链接</h2>
                <div class="link-grid">
                    <div class="link-card">
                        <a href="#">📈 Allure报告</a>
                        <div style="font-size: 0.8em; color: #6c757d; margin-top: 5px;">详细测试报告</div>
                    </div>
                    <div class="link-card">
                        <a href="#">📄 HTML报告</a>
                        <div style="font-size: 0.8em; color: #6c757d; margin-top: 5px;">简化版报告</div>
                    </div>
                    <div class="link-card">
                        <a href="#">🔧 Jenkins构建</a>
                        <div style="font-size: 0.8em; color: #6c757d; margin-top: 5px;">构建详情</div>
                    </div>
                    <div class="link-card">
                        <a href="#">📝 控制台日志</a>
                        <div style="font-size: 0.8em; color: #6c757d; margin-top: 5px;">执行日志</div>
                    </div>
                </div>
            </div>
            
            <div class="footer">
                <p>此邮件由自动化测试系统自动发送，请勿回复。</p>
                <p>如有问题，请联系测试团队。</p>
            </div>
        </body>
        </html>
        """
        
        return html_content
    
    def send_failure_alert(self, 
                          recipients: List[str],
                          error_details: Dict[str, Any],
                          subject_prefix: str = "测试执行失败警告") -> bool:
        """
        发送失败警告邮件
        
        Args:
            recipients: 收件人列表
            error_details: 错误详情字典
            subject_prefix: 邮件主题前缀
            
        Returns:
            bool: 发送是否成功
        """
        try:
            timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            subject = f"{subject_prefix} ({timestamp})"
            
            html_content = self._generate_failure_html(error_details)
            
            return self.send_email(
                recipients=recipients,
                subject=subject,
                html_content=html_content
            )
            
        except Exception as e:
            test_logger.error(f"发送失败警告邮件失败: {str(e)}")
            return False
    
    def _generate_failure_html(self, error_details: Dict[str, Any]) -> str:
        """
        生成失败警告HTML内容
        
        Args:
            error_details: 错误详情字典
            
        Returns:
            str: HTML内容
        """
        error_message = error_details.get('message', '未知错误')
        error_type = error_details.get('type', '系统错误')
        timestamp = error_details.get('timestamp', datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
        
        html_content = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <meta charset="UTF-8">
            <title>测试执行失败警告</title>
            <style>
                body {{
                    font-family: Arial, sans-serif;
                    line-height: 1.6;
                    color: #333;
                    max-width: 600px;
                    margin: 0 auto;
                    padding: 20px;
                }}
                .alert {{
                    background: #f8d7da;
                    border: 1px solid #f5c6cb;
                    color: #721c24;
                    padding: 20px;
                    border-radius: 5px;
                    margin-bottom: 20px;
                }}
                .alert h2 {{
                    margin-top: 0;
                    color: #721c24;
                }}
                .error-details {{
                    background: #f8f9fa;
                    padding: 15px;
                    border-radius: 5px;
                    border-left: 4px solid #dc3545;
                }}
                .footer {{
                    margin-top: 30px;
                    padding-top: 20px;
                    border-top: 1px solid #dee2e6;
                    color: #6c757d;
                    font-size: 0.9em;
                }}
            </style>
        </head>
        <body>
            <div class="alert">
                <h2>⚠️ 测试执行失败警告</h2>
                <p>自动化测试执行过程中发生错误，请及时处理。</p>
            </div>
            
            <div class="error-details">
                <h3>错误详情</h3>
                <p><strong>错误类型:</strong> {error_type}</p>
                <p><strong>发生时间:</strong> {timestamp}</p>
                <p><strong>错误信息:</strong></p>
                <pre>{error_message}</pre>
            </div>
            
            <div class="footer">
                <p>此邮件由自动化测试系统自动发送，请勿回复。</p>
                <p>请及时查看Jenkins构建日志了解详细信息。</p>
            </div>
        </body>
        </html>
        """
        
        return html_content


# 便捷函数
def send_test_report_email(recipients: List[str], 
                          test_results: Dict[str, Any],
                          report_files: List[str] = None) -> bool:
    """
    发送测试报告邮件的便捷函数
    
    Args:
        recipients: 收件人列表
        test_results: 测试结果字典
        report_files: 报告文件路径列表
        
    Returns:
        bool: 发送是否成功
    """
    sender = EmailSender()
    return sender.send_test_report(recipients, test_results, report_files)


def send_failure_alert_email(recipients: List[str], 
                            error_details: Dict[str, Any]) -> bool:
    """
    发送失败警告邮件的便捷函数
    
    Args:
        recipients: 收件人列表
        error_details: 错误详情字典
        
    Returns:
        bool: 发送是否成功
    """
    sender = EmailSender()
    return sender.send_failure_alert(recipients, error_details)


if __name__ == "__main__":
    # 测试邮件发送
    test_results = {
        'success': True,
        'total': 10,
        'passed': 8,
        'failed': 1,
        'skipped': 1,
        'errors': 0,
        'duration': '2分30秒',
        'start_time': '2024-01-15 10:00:00',
        'end_time': '2024-01-15 10:02:30',
        'environment': 'test',
        'browser': 'chrome'
    }
    
    sender = EmailSender()
    success = sender.send_test_report(
        recipients=['test@example.com'],
        test_results=test_results
    )
    
    print(f"邮件发送{'成功' if success else '失败'}")