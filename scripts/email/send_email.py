import os
import smtplib
import time
from datetime import datetime
from email.header import Header
from email.mime.application import MIMEApplication
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from pathlib import Path
from typing import Optional, Union, List, Dict, Tuple

import yaml
from rich.console import Console
from rich.table import Table

# 引入日志系统
from scripts.log.log import log

console = Console()


class EmailSender:
    """通用邮件发送工具类（带 rich 日志 + as_json 支持）"""

    def __init__(self, config_path: Optional[str] = None):
        self.config_path = config_path
        self.config = self._load_config()
        if not self.config:
            log.warning("⚠️ 无法加载邮件配置，使用默认配置")
            self.config = {}

        # 默认配置 - 新配色方案
        self.default_config = {
            'theme_color': '#8ec5ff',
            'secondary_color': '#f4effb',
            'theme_gradient': ['#f4effb', '#8ec5ff'],
            'text_color': '#2c3e50',
            'accent_color': '#3498db',
            'admin_url': 'https://your-admin-domain.com',
            'site_name': '数据库备份管理系统',
            'logo_url': None,
            'footer_text': '系统自动通知'
        }

    # ------------------------
    # 配置文件加载
    # ------------------------
    def _load_config(self) -> dict:
        try:
            if self.config_path:
                config_path = Path(self.config_path)
            else:
                possible_paths = [
                    Path(__file__).parent.parent.parent / 'config.yaml',
                    Path(__file__).parent.parent / 'config.yaml',
                    Path(__file__).parent / 'config.yaml',
                    Path('config.yaml'),
                ]
                config_path = next((p for p in possible_paths if p.exists()), None)
                if not config_path:
                    log.warning("⚠️ 未找到邮件配置文件，使用默认配置")
                    return {}

            with open(config_path, 'r', encoding='utf-8') as f:
                cfg = yaml.safe_load(f)
                return cfg.get('email', {})
        except Exception as e:
            log.error(f"⚠️ 加载邮件配置失败: {e}")
            return {}

    def get_default_recipients(self) -> List[str]:
        """获取默认收件人列表"""
        return self.config.get('send_to', [])

    def update_config(self, **kwargs):
        """更新默认配置"""
        for k, v in kwargs.items():
            if k in self.default_config:
                self.default_config[k] = v

    # ------------------------
    # SMTP 连接
    # ------------------------
    def _create_connection(self):
        try:
            if self.config.get('use_ssl', True):
                smtp = smtplib.SMTP_SSL(
                    self.config.get('mail_host'),
                    self.config.get('port', 465),
                    timeout=10
                )
            else:
                smtp = smtplib.SMTP(
                    self.config.get('mail_host'),
                    self.config.get('port', 587),
                    timeout=10
                )
                smtp.starttls()
            smtp.login(
                self.config.get('send_by'),
                self.config.get('smtp_password')
            )
            return smtp
        except Exception as e:
            raise RuntimeError(f"SMTP连接失败: {e}")

    def _format_from_header(self, display_name, email_address):
        try:
            encoded_name = Header(display_name, 'utf-8').encode()
            return f'{encoded_name} <{email_address}>'
        except:
            return f'"{display_name}" <{email_address}>'

    # ------------------------
    # 发送邮件
    # ------------------------
    def send_email(self, to_email: Union[str, List[str]] = None,
                   subject: str = None,
                   content: str = None,
                   content_type: str = 'html',
                   attachments: Optional[List[Tuple[str, Union[str, bytes]]]] = None,
                   cc_emails: Optional[List[str]] = None,
                   bcc_emails: Optional[List[str]] = None,
                   use_default_recipients: bool = False,
                   as_json: bool = True,
                   **kwargs) -> Optional[Dict]:
        """
        发送邮件（支持 rich 表格日志 + as_json）
        """
        start_time = time.time()
        result_info = {
            'to': to_email,
            'cc': cc_emails,
            'bcc': bcc_emails,
            'subject': subject,
            'attachments': [f[0] for f in attachments] if attachments else [],
            'status': 'failed',
            'error': None,
            'duration': None
        }
        try:
            # 确定收件人
            if use_default_recipients and not to_email:
                recipients_list = self.get_default_recipients()
                if not recipients_list:
                    raise ValueError("未找到默认收件人列表(send_to)")
            elif not to_email:
                raise ValueError("必须指定收件人或设置use_default_recipients=True")
            else:
                recipients_list = to_email

            # 合并默认配置
            email_config = {**self.default_config, **kwargs}

            # 构建邮件对象
            message = MIMEMultipart()
            from_email = self.config.get('send_by')
            message['From'] = self._format_from_header(email_config.get('site_name', '系统通知'), from_email)

            # 收件人
            if isinstance(recipients_list, list):
                message['To'] = ', '.join(recipients_list)
                recipients = recipients_list.copy()
            else:
                message['To'] = recipients_list
                recipients = [recipients_list]

            # CC / BCC
            if cc_emails:
                if isinstance(cc_emails, list):
                    message['Cc'] = ', '.join(cc_emails)
                    recipients.extend(cc_emails)
                else:
                    message['Cc'] = cc_emails
                    recipients.append(cc_emails)
            if bcc_emails:
                if isinstance(bcc_emails, list):
                    recipients.extend(bcc_emails)
                else:
                    recipients.append(bcc_emails)

            # 主题 & 时间
            message['Subject'] = Header(subject, 'utf-8').encode()
            message['Date'] = time.strftime('%a, %d %b %Y %H:%M:%S %z')

            # 邮件正文
            message.attach(MIMEText(content, content_type, 'utf-8'))

            # 附件
            if attachments:
                for filename, file_content_or_path in attachments:
                    self._add_attachment(message, filename, file_content_or_path)

            # 发送
            smtp = self._create_connection()
            smtp.sendmail(from_email, recipients, message.as_string())
            smtp.quit()

            duration = round(time.time() - start_time, 2)
            result_info.update({'status': 'success', 'duration': f"{duration}s"})

            # rich 表格输出
            table = Table(title=f"📧 邮件发送结果: {subject}")
            table.add_column("字段")
            table.add_column("值")
            for k, v in result_info.items():
                table.add_row(str(k), str(v))
            self.log_rich(table)
            log.info(f"邮件发送完成: {subject} -> {recipients}")

            return result_info if as_json else None

        except Exception as e:
            result_info['error'] = str(e)
            # rich 表格输出
            table = Table(title=f"📧 邮件发送失败: {subject}")
            table.add_column("字段")
            table.add_column("值")
            for k, v in result_info.items():
                table.add_row(str(k), str(v))
            self.log_rich(table)
            log.error(f"邮件发送失败: {subject} -> {to_email}: {e}")
            return result_info if as_json else None

    # ------------------------
    # 添加附件
    # ------------------------
    def _add_attachment(self, message, filename, file_content_or_path):
        try:
            if isinstance(file_content_or_path, (str, Path)) and os.path.exists(file_content_or_path):
                with open(file_content_or_path, 'rb') as f:
                    file_content = f.read()
            else:
                file_content = file_content_or_path

            attachment = MIMEApplication(file_content)
            attachment.add_header('Content-Disposition', 'attachment',
                                  filename=Header(filename, 'utf-8').encode())
            message.attach(attachment)
            log.debug(f"📎 附件添加成功: {filename}")
        except Exception as e:
            log.warning(f"⚠️ 附件添加失败 {filename}: {e}")

    # ------------------------
    # 备份通知 / 错误通知 / 自定义通知
    # ------------------------
    def send_backup_notification(self, to_email=None, backup_type=None, backup_info=None,
                                 file_size=None, duration=None, use_default_recipients=False,
                                 as_json=True, **kwargs):
        title_map = {'database': '数据库备份', 'files': '文件备份', 'full': '完整备份'}
        subject = f"💾 {self.default_config.get('site_name')} - {title_map.get(backup_type, '数据备份')}完成通知"
        content = self._create_backup_html(backup_type, backup_info, file_size, duration,
                                           {**self.default_config, **kwargs})
        return self.send_email(to_email, subject, content, 'html',
                               use_default_recipients=use_default_recipients, as_json=as_json, **kwargs)

    def send_error_notification(self, to_email=None, error_type=None, error_message=None,
                                error_details=None, solution=None, use_default_recipients=False,
                                as_json=True, **kwargs):
        subject = f"🚨 {self.default_config.get('site_name')} - {error_type}错误通知"
        content = self._create_error_html(error_type, error_message, error_details, solution,
                                          {**self.default_config, **kwargs})
        return self.send_email(to_email, subject, content, 'html',
                               use_default_recipients=use_default_recipients, as_json=as_json, **kwargs)

    def send_custom_notification(self, to_email=None, notification_type=None, title=None,
                                 message=None, details=None, priority='normal', use_default_recipients=False,
                                 as_json=True, **kwargs):
        subject = f"{title}"
        content = self._create_custom_notification_html(notification_type, title, message, details, priority,
                                                        {**self.default_config, **kwargs})
        return self.send_email(to_email, subject, content, 'html',
                               use_default_recipients=use_default_recipients, as_json=as_json, **kwargs)

    # ------------------------
    # HTML 构建函数
    # ------------------------
    def _create_backup_html(self, backup_type, backup_info, file_size, duration, config):
        """创建备份通知邮件的HTML内容"""
        current_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        theme_color = config.get('theme_color', '#8ec5ff')
        secondary_color = config.get('secondary_color', '#f4effb')
        theme_gradient = config.get('theme_gradient', ['#f4effb', '#8ec5ff'])
        text_color = config.get('text_color', '#2c3e50')

        type_icons = {'database': '🗄️', 'files': '📁', 'full': '💾'}
        icon = type_icons.get(backup_type, '💾')

        backup_details = self._format_backup_details(backup_info, file_size, duration)

        return f"""<!DOCTYPE html>
    <html>
    <head>
    <meta charset="UTF-8">
    <title>{config.get('site_name')} - 备份通知</title>
    <style>
    body {{ font-family: 'Helvetica Neue', Arial, 'PingFang SC', 'Microsoft YaHei', sans-serif;
           background: linear-gradient(135deg, {theme_gradient[0]}, {theme_gradient[1]});
           margin: 0; padding: 20px; min-height: 100vh; color: {text_color}; }}
    .container {{ max-width: 600px; margin: 0 auto; background: white; border-radius: 15px;
                box-shadow: 0 10px 30px rgba(142, 197, 255, 0.3); overflow: hidden; }}
    .header {{ background: linear-gradient(135deg, {theme_gradient[0]}, {theme_gradient[1]});
              color: white; padding: 30px; text-align: center; }}
    .header h1 {{ margin: 0 0 10px 0; font-size: 28px; font-weight: 300; }}
    .content {{ padding: 40px; line-height: 1.6; }}
    .notification-card {{ background: {secondary_color}; border-left: 4px solid {theme_color};
                        padding: 25px; margin: 25px 0; border-radius: 10px; }}
    .stats-grid {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(150px, 1fr));
                  gap: 15px; margin: 20px 0; }}
    .stat-item {{ background: white; padding: 15px; border-radius: 8px; text-align: center;
                 box-shadow: 0 2px 5px rgba(0,0,0,0.1); }}
    .action-btn {{ display: inline-block; background: {theme_color}; color: white;
                  padding: 12px 30px; text-decoration: none; border-radius: 25px; margin: 20px 0;
                  font-weight: 500; transition: all 0.3s ease; }}
    .action-btn:hover {{ background: {config.get('accent_color', '#3498db')};
                        transform: translateY(-2px);
                        box-shadow: 0 5px 15px rgba(142, 197, 255, 0.4); }}
    </style>
    </head>
    <body>
    <div class="container">
    <div class="header">
    <h1>{icon} 备份完成通知</h1>
    <p>{config.get('site_name')} • 系统自动提醒</p>
    </div>
    <div class="content">
    <div class="notification-card">
    <h2 style="margin: 0 0 15px 0; color: {theme_color};">{icon} {backup_type.upper()}备份已完成</h2>
    <p style="margin: 0 0 10px 0;">系统已成功完成{backup_type}备份操作。</p>
    <p style="margin: 0;"><strong>⏰ 完成时间:</strong> {current_time}</p>
    </div>
    <div class="stats-grid">
    <div class="stat-item">
    <div style="font-size: 24px; color: {theme_color};">{icon}</div>
    <div><strong>备份类型</strong></div>
    <div>{backup_type}</div>
    </div>
    {f'<div class="stat-item"><div style="font-size: 24px; color: {theme_color};">📊</div><div><strong>文件大小</strong></div><div>{file_size}</div></div>' if file_size else ''}
    {f'<div class="stat-item"><div style="font-size: 24px; color: {theme_color};">⏱️</div><div><strong>耗时</strong></div><div>{duration}</div></div>' if duration else ''}
    </div>
    <h3 style="color: {theme_color}; margin-bottom: 15px;">📋 备份详情</h3>
    <div style="background: #f8f9fa; padding: 15px; border-radius: 8px; margin: 15px 0;">
    {backup_details}
    </div>
    <a href="{config.get('admin_url', '#')}" class="action-btn">🔍 查看备份详情</a>
    </div>
    </div>
    </body>
    </html>"""

    def _create_error_html(self, error_type, error_message, error_details, solution, config):
        """创建错误通知邮件的HTML内容"""
        current_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        theme_color = '#e74c3c'
        secondary_color = config.get('secondary_color', '#f4effb')

        return f"""<!DOCTYPE html>
    <html>
    <head>
    <meta charset="UTF-8">
    <title>{config.get('site_name')} - 错误通知</title>
    <style>
    body {{ font-family: 'Helvetica Neue', Arial, sans-serif; background: #f8f9fa; margin: 0; padding: 20px; }}
    .container {{ max-width: 600px; margin: 0 auto; background: white; border-radius: 15px; box-shadow: 0 5px 15px rgba(0,0,0,0.1); overflow: hidden; }}
    .header {{ background: {theme_color}; color: white; padding: 30px; text-align: center; }}
    .content {{ padding: 30px; }}
    .error-card {{ background: #fee; border-left: 4px solid {theme_color}; padding: 20px; margin: 20px 0; border-radius: 8px; }}
    </style>
    </head>
    <body>
    <div class="container">
    <div class="header">
    <h1>🚨 系统错误通知</h1>
    <p>{config.get('site_name')}</p>
    </div>
    <div class="content">
    <div class="error-card">
    <h3 style="color: {theme_color}; margin-top: 0;">{error_type}</h3>
    <p><strong>错误信息:</strong> {error_message}</p>
    <p><strong>发生时间:</strong> {current_time}</p>
    {f'<p><strong>解决方案:</strong> {solution}</p>' if solution else ''}
    </div>
    {f'<div style="background: #f8f9fa; padding: 15px; border-radius: 5px; margin: 15px 0;"><strong>错误详情:</strong><br>{error_details}</div>' if error_details else ''}
    </div>
    </div>
    </body>
    </html>"""

    def _create_custom_notification_html(self, notification_type, title, message, details, priority, config):
        """创建自定义通知邮件的HTML内容"""
        current_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

        type_config = {
            'success': {'icon': '✅', 'color': '#27ae60'},
            'warning': {'icon': '⚠️', 'color': '#f39c12'},
            'error': {'icon': '❌', 'color': '#e74c3c'},
            'info': {'icon': 'ℹ️', 'color': config.get('theme_color', '#8ec5ff')}
        }
        notify_config = type_config.get(notification_type, type_config['info'])

        return f"""<!DOCTYPE html>
    <html>
    <head>
    <meta charset="UTF-8">
    <title>{config.get('site_name')} - {title}</title>
    </head>
    <body style="font-family: Arial, sans-serif; background: #f4f4f4; padding: 20px;">
    <div style="max-width: 600px; margin: 0 auto; background: white; border-radius: 10px; box-shadow: 0 2px 10px rgba(0,0,0,0.1);">
    <div style="background: {notify_config['color']}; color: white; padding: 20px; border-radius: 10px 10px 0 0; text-align: center;">
    <h1 style="margin: 0;">{notify_config['icon']} {title}</h1>
    </div>
    <div style="padding: 30px;">
    <p>{message}</p>
    <p><small>时间: {current_time} | 优先级: {priority}</small></p>
    {f'<div style="background: #f8f9fa; padding: 15px; border-radius: 5px; margin-top: 15px;"><strong>详细信息:</strong><br>{details}</div>' if details else ''}
    </div>
    </div>
    </body>
    </html>"""

    def _format_backup_details(self, backup_info, file_size, duration):
        """格式化备份详情"""
        if isinstance(backup_info, dict):
            details = [f"<strong>{key}:</strong> {value}" for key, value in backup_info.items()]
            return '<br>'.join(details)
        return str(backup_info)

    # ===================== rich 表格日志方法 =====================
    def log_rich(self, renderable):
        """渲染 rich 表格并写入日志和控制台"""
        from io import StringIO
        from rich.console import Console

        # 渲染到 buffer
        buffer = StringIO()
        console_file = Console(file=buffer, force_terminal=False, color_system=None)
        console_file.print(renderable)
        output_str = buffer.getvalue()

        # 写入日志
        for line in output_str.splitlines():
            log.info(line)

        # 控制台输出彩色表格
        console_out = Console()
        console_out.print(renderable)


# ------------------------
# 全局实例 & 快捷函数
# ------------------------
email_sender = EmailSender()


def send_backup_email(*args, **kwargs):
    return email_sender.send_backup_notification(*args, **kwargs)


def send_error_email(*args, **kwargs):
    return email_sender.send_error_notification(*args, **kwargs)


def send_custom_email(*args, **kwargs):
    return email_sender.send_custom_notification(*args, **kwargs)


if __name__ == "__main__":
    # 测试邮箱
    to_test_email = ["ljw3024705530@163.com"]
    backup_file_path = Path(
        r'E:\Py_Project\automatic-database-backup\backup\zaoliangwebsite\20251206_041155\zaoliangwebsite_20251206_041155.tar.gz')

    # 测试 1：备份通知邮件
    backup_result = send_backup_email(
        to_email=to_test_email,
        backup_type='database',
        backup_info={'表数量': 12, '记录数': 1500, '大小': '3500条记录'},
        file_size='15MB',
        duration='00:02:30',
        attachments=[(backup_file_path.name, backup_file_path)],
        use_default_recipients=False,
        as_json=True
    )
    print("备份通知邮件发送结果:", backup_result)

    # 测试 2：错误通知邮件
    error_result = send_error_email(
        to_email=to_test_email,
        error_type='数据库错误',
        error_message='连接超时',
        error_details='尝试连接数据库3次均失败',
        solution='请检查数据库服务是否启动',
        use_default_recipients=False,
        as_json=True
    )
    print("错误通知邮件发送结果:", error_result)

    # 测试 3：自定义通知邮件
    custom_result = send_custom_email(
        to_email=to_test_email,
        notification_type='info',
        title='测试自定义通知',
        message='这是一条自定义通知邮件，用于测试 EmailSender 封装',
        details='邮件测试详情信息',
        priority='high',
        use_default_recipients=False,
        as_json=True
    )
    print("自定义通知邮件发送结果:", custom_result)
