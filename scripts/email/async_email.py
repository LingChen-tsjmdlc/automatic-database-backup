import logging
import queue
import sys
import threading
import time
import traceback
from pathlib import Path
from typing import Dict, Optional, Tuple, List, Union

from scripts.log.log import log

# 添加项目根目录到Python路径
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

try:
    from scripts.email.send_email import EmailSender
except ImportError:
    # 如果导入失败，尝试相对导入
    try:
        from .send_email import EmailSender
    except ImportError:
        log.error("无法导入EmailSender类，请检查send_email.py文件路径")
        raise ImportError("无法导入EmailSender类，请检查send_email.py文件路径")


class AsyncEmailSender:
    """异步邮件发送器"""

    def __init__(self, config_path: Optional[str] = None, max_workers: int = 3, max_retries: int = 3):
        """
        初始化异步邮件发送器

        参数:
            config_path: 配置文件路径
            max_workers: 最大工作线程数
            max_retries: 最大重试次数
        """
        self.email_sender = EmailSender(config_path)
        self.email_queue = queue.Queue()
        self.is_running = False
        self.worker_threads = []
        self.max_workers = max_workers
        self.max_retries = max_retries
        self.sent_count = 0
        self.failed_count = 0
        self.lock = threading.Lock()

        # 启动工作线程
        self.start_workers()

    def start_workers(self):
        """启动工作线程池"""
        if not self.is_running:
            self.is_running = True
            for i in range(self.max_workers):
                thread = threading.Thread(
                    target=self._process_queue,
                    daemon=True,
                    name=f"EmailWorker-{i + 1}"
                )
                thread.start()
                self.worker_threads.append(thread)
            log.info(f"✅ 异步邮件发送器已启动，{self.max_workers}个工作线程运行中")

    def stop_workers(self, wait: bool = True, timeout: int = 30):
        """停止工作线程

        参数:
            wait: 是否等待队列处理完成
            timeout: 等待超时时间（秒）
        """
        if not self.is_running:
            return

        self.is_running = False

        if wait:
            # 发送停止信号给所有工作线程
            for _ in range(self.max_workers):
                self.email_queue.put(None)

            # 等待线程结束
            for i, thread in enumerate(self.worker_threads):
                thread.join(timeout=timeout)
                if thread.is_alive():
                    log.warning(f"⚠️ 工作线程 {i + 1} 未在超时时间内停止")
                else:
                    log.info(f"✅ 工作线程 {i + 1} 已停止")

        self.worker_threads.clear()
        log.info("🛑 异步邮件发送器已停止")

    def _process_queue(self):
        """工作线程处理邮件队列"""
        thread_name = threading.current_thread().name

        while self.is_running:
            try:
                # 等待邮件任务，最多等待2秒
                email_task = self.email_queue.get(timeout=2)
                if email_task is None:  # 停止信号
                    break

                task_type, args, kwargs, retry_count = email_task

                try:
                    success, message = self._execute_email_task(task_type, args, kwargs)

                    if success:
                        with self.lock:
                            self.sent_count += 1
                        log.info(f"✅ {thread_name} 邮件发送成功: {self._get_task_description(task_type, args)}")
                    else:
                        # 重试逻辑
                        if retry_count < self.max_retries:
                            log.warning(
                                f"🔄 {thread_name} 邮件发送失败，准备重试 ({retry_count + 1}/{self.max_retries}): {message}")
                            self._retry_task(task_type, args, kwargs, retry_count + 1)
                        else:
                            with self.lock:
                                self.failed_count += 1
                            log.error(
                                f"❌ {thread_name} 邮件发送失败，已达最大重试次数: {self._get_task_description(task_type, args)} - {message}")

                except Exception as e:
                    log.error(f"❌ {thread_name} 邮件任务执行异常: {str(e)}")
                    traceback.print_exc()

                finally:
                    self.email_queue.task_done()

            except queue.Empty:
                continue
            except Exception as e:
                log.error(f"❌ {thread_name} 队列处理异常: {str(e)}")
                time.sleep(1)  # 避免频繁错误

    def _execute_email_task(self, task_type: str, args: tuple, kwargs: dict) -> Tuple[bool, str]:
        """执行具体的邮件发送任务"""
        try:
            # 调试信息：检查附件参数
            if task_type == 'direct' and len(args) > 4 and args[4]:  # attachments参数位置
                log.info(f"🔍 调试 - 附件参数: {args[4]}")
                # 检查附件文件是否存在
                attachments = args[4]
                if attachments:
                    for attachment in attachments:
                        if isinstance(attachment, (tuple, list)) and len(attachment) >= 2:
                            file_path = attachment[1]
                            if isinstance(file_path, str) and Path(file_path).exists():
                                log.info(f"✅ 附件文件存在: {file_path}")
                            else:
                                log.warning(f"⚠️ 附件文件不存在或路径无效: {file_path}")

            # 执行邮件发送任务
            if task_type == 'backup':
                result = self.email_sender.send_backup_notification(*args, **kwargs)
            elif task_type == 'error':
                result = self.email_sender.send_error_notification(*args, **kwargs)
            elif task_type == 'custom':
                result = self.email_sender.send_custom_notification(*args, **kwargs)
            elif task_type == 'direct':
                result = self.email_sender.send_email(*args, **kwargs)
            else:
                return False, f"未知的任务类型: {task_type}"

            # 根据EmailSender的返回值格式进行处理
            if isinstance(result, dict):
                # 如果返回字典，检查状态字段
                status = result.get('status', 'failed')
                if status == 'success':
                    return True, "邮件发送成功"
                else:
                    error_msg = result.get('error', '未知错误')
                    return False, f"邮件发送失败: {error_msg}"
            elif isinstance(result, tuple) and len(result) == 2:
                # 如果返回元组，直接使用
                return result
            elif result is None:
                # 如果返回None，认为是成功
                return True, "邮件发送成功"
            else:
                # 其他情况
                log.warning(f"⚠️ 未知的返回值格式: {type(result)}")
                return True, "邮件发送完成（未知返回值格式）"

        except Exception as e:
            error_msg = f"任务执行异常: {str(e)}"
            log.error(f"❌ {error_msg}")
            traceback.print_exc()
            return False, error_msg

    def _retry_task(self, task_type: str, args: tuple, kwargs: dict, retry_count: int):
        """重试任务"""
        # 添加延迟后重新加入队列
        delay = min(2 ** retry_count, 60)  # 指数退避，最大60秒
        threading.Timer(delay, lambda: self.email_queue.put((task_type, args, kwargs, retry_count))).start()

    def _get_task_description(self, task_type: str, args: tuple) -> str:
        """获取任务描述"""
        if task_type == 'backup' and len(args) > 0:
            return f"备份通知 -> {args[0]}"
        elif task_type == 'error' and len(args) > 0:
            return f"错误通知 -> {args[0]}"
        elif task_type == 'custom' and len(args) > 0:
            return f"自定义通知 -> {args[0]}"
        elif task_type == 'direct' and len(args) > 0:
            subject = args[1] if len(args) > 1 else "Unknown"
            attachments_count = len(args[4]) if len(args) > 4 and args[4] else 0
            return f"直接发送 -> {args[0]} - {subject} [附件: {attachments_count}个]"
        else:
            return f"{task_type}任务"

    def send_backup_notification_async(self, to_email=None, backup_type=None, backup_info=None,
                                       file_size=None, duration=None, use_default_recipients=False,
                                       attachments: Optional[List[Tuple[str, Union[str, bytes]]]] = None, **kwargs):
        """异步发送备份通知邮件"""
        try:
            # 确保attachments参数正确传递
            task_args = (to_email, backup_type, backup_info, file_size, duration, use_default_recipients)
            if attachments is not None:
                # 将attachments添加到kwargs中，因为EmailSender的备份方法不支持attachments参数
                kwargs['attachments'] = attachments

            task = ('backup', task_args, kwargs, 0)
            self.email_queue.put(task)
            attachments_info = f" [附件: {len(attachments) if attachments else 0}个]" if attachments else ""
            log.info(
                f"📧 备份通知邮件任务已加入队列: {self._get_task_description('backup', (to_email,))}{attachments_info}")
            return True, "邮件任务已加入队列"
        except Exception as e:
            log.error(f"❌ 备份通知邮件任务加入队列失败: {str(e)}")
            return False, str(e)

    def send_error_notification_async(self, to_email=None, error_type=None, error_message=None,
                                      error_details=None, solution=None, use_default_recipients=False,
                                      attachments: Optional[List[Tuple[str, Union[str, bytes]]]] = None, **kwargs):
        """异步发送错误通知邮件"""
        try:
            task_args = (to_email, error_type, error_message, error_details, solution, use_default_recipients)
            if attachments is not None:
                kwargs['attachments'] = attachments

            task = ('error', task_args, kwargs, 0)
            self.email_queue.put(task)
            attachments_info = f" [附件: {len(attachments) if attachments else 0}个]" if attachments else ""
            log.info(
                f"📧 错误通知邮件任务已加入队列: {self._get_task_description('error', (to_email,))}{attachments_info}")
            return True, "邮件任务已加入队列"
        except Exception as e:
            log.error(f"❌ 错误通知邮件任务加入队列失败: {str(e)}")
            return False, str(e)

    def send_custom_notification_async(self, to_email=None, notification_type=None, title=None,
                                       message=None, details=None, priority='normal', use_default_recipients=False,
                                       attachments: Optional[List[Tuple[str, Union[str, bytes]]]] = None, **kwargs):
        """异步发送自定义通知邮件"""
        try:
            task_args = (to_email, notification_type, title, message, details, priority, use_default_recipients)
            if attachments is not None:
                kwargs['attachments'] = attachments

            task = ('custom', task_args, kwargs, 0)
            self.email_queue.put(task)
            attachments_info = f" [附件: {len(attachments) if attachments else 0}个]" if attachments else ""
            log.info(
                f"📧 自定义通知邮件任务已加入队列: {self._get_task_description('custom', (to_email,))}{attachments_info}")
            return True, "邮件任务已加入队列"
        except Exception as e:
            log.error(f"❌ 自定义通知邮件任务加入队列失败: {str(e)}")
            return False, str(e)

    def send_email_async(self, to_email=None, subject=None, content=None, content_type='html',
                         attachments: Optional[List[Tuple[str, Union[str, bytes]]]] = None,
                         cc_emails=None, bcc_emails=None, use_default_recipients=False, **kwargs):
        """异步发送自定义邮件"""
        try:
            # 修正参数顺序，确保与EmailSender.send_email方法匹配
            task_args = (
            to_email, subject, content, content_type, attachments, cc_emails, bcc_emails, use_default_recipients)
            task = ('direct', task_args, kwargs, 0)
            self.email_queue.put(task)
            attachments_info = f" [附件: {len(attachments) if attachments else 0}个]" if attachments else ""
            log.info(
                f"📧 直接邮件任务已加入队列: {self._get_task_description('direct', (to_email, subject))}{attachments_info}")
            return True, "邮件任务已加入队列"
        except Exception as e:
            log.error(f"❌ 直接邮件任务加入队列失败: {str(e)}")
            return False, str(e)

    def get_queue_size(self) -> int:
        """获取队列中待处理的邮件数量"""
        return self.email_queue.qsize()

    def get_stats(self) -> Dict[str, int]:
        """获取统计信息"""
        with self.lock:
            return {
                'queue_size': self.get_queue_size(),
                'sent_count': self.sent_count,
                'failed_count': self.failed_count,
                'total_processed': self.sent_count + self.failed_count,
                'active_workers': sum(1 for thread in self.worker_threads if thread.is_alive())
            }

    def wait_until_empty(self, timeout: Optional[int] = None) -> bool:
        """等待直到队列为空

        参数:
            timeout: 超时时间（秒），None表示无限等待

        返回:
            bool: 是否在超时前队列已空
        """
        try:
            if timeout is None:
                self.email_queue.join()
                return True
            else:
                # 实现带超时的等待
                start_time = time.time()
                while self.get_queue_size() > 0:
                    if time.time() - start_time > timeout:
                        return False
                    time.sleep(0.1)
                return True
        except Exception as e:
            log.error(f"❌ 等待队列为空时发生错误: {str(e)}")
            return False

    def is_active(self) -> bool:
        """检查发送器是否在运行"""
        return self.is_running and any(thread.is_alive() for thread in self.worker_threads)


# 全局异步邮件发送器实例
_async_email_sender: Optional[AsyncEmailSender] = None


def get_async_email_sender(config_path: Optional[str] = None) -> AsyncEmailSender:
    """获取全局异步邮件发送器实例（单例模式）"""
    global _async_email_sender
    if _async_email_sender is None:
        _async_email_sender = AsyncEmailSender(config_path)
    return _async_email_sender


def shutdown_async_email_sender(wait: bool = True, timeout: int = 30):
    """关闭全局异步邮件发送器"""
    global _async_email_sender
    if _async_email_sender is not None:
        _async_email_sender.stop_workers(wait, timeout)
        _async_email_sender = None


# 快捷函数
def send_backup_notification_async(to_email=None, backup_type=None, backup_info=None,
                                   file_size=None, duration=None, use_default_recipients=True,
                                   attachments: Optional[List[Tuple[str, Union[str, bytes]]]] = None, **kwargs):
    """
    异步发送备份通知邮件

    参数:
        - to_email: 收件人邮箱，如果为None则使用配置中的默认收件人
        - backup_type: 备份类型，如 'full'、'incremental'、'database' 等
        - backup_info: 备份信息字典，包含备份详情
        - file_size: 备份文件大小
        - duration: 备份耗时
        - use_default_recipients: 是否使用配置中的默认收件人列表 (默认为 True)
        - attachments: 附件列表，格式为 [(文件名, 文件路径或文件内容), ...]
        - **kwargs: 其他参数

    返回:
        - tuple: (成功状态, 消息)
    """
    sender = get_async_email_sender()
    return sender.send_backup_notification_async(to_email, backup_type, backup_info, file_size,
                                                 duration, use_default_recipients, attachments, **kwargs)


def send_error_notification_async(to_email=None, error_type=None, error_message=None,
                                  error_details=None, solution=None, use_default_recipients=True,
                                  attachments: Optional[List[Tuple[str, Union[str, bytes]]]] = None, **kwargs):
    """
    异步发送错误通知邮件

    参数:
        - to_email: 收件人邮箱，如果为None则使用配置中的默认收件人
        - error_type: 错误类型，如'backup_failed'、'database_error'等
        - error_message: 错误消息
        - error_details: 错误详情
        - solution: 解决方案建议
        - use_default_recipients: 是否使用配置中的默认收件人列表 (默认为 True)
        - attachments: 附件列表，格式为 [(文件名, 文件路径或文件内容), ...]
        - **kwargs: 其他参数

    返回:
        - tuple: (成功状态, 消息)
    """
    sender = get_async_email_sender()
    return sender.send_error_notification_async(to_email, error_type, error_message,
                                                error_details, solution, use_default_recipients, attachments, **kwargs)


def send_custom_notification_async(to_email=None, notification_type=None, title=None,
                                   message=None, details=None, priority='normal', use_default_recipients=True,
                                   attachments: Optional[List[Tuple[str, Union[str, bytes]]]] = None, **kwargs):
    """
    异步发送自定义通知邮件

    参数:
        - to_email: 收件人邮箱，如果为None则使用配置中的默认收件人
        - notification_type: 通知类型，用于邮件模板选择
        - title: 邮件标题
        - message: 邮件正文内容
        - details: 详细内容，可以是字典或字符串
        - priority: 优先级，'low'、'normal'、'high'
        - use_default_recipients: 是否使用配置中的默认收件人列表 (默认为 True)
        - attachments: 附件列表，格式为 [(文件名, 文件路径或文件内容), ...]
        - **kwargs: 其他参数

    返回:
        - tuple: (成功状态, 消息)
    """
    sender = get_async_email_sender()
    return sender.send_custom_notification_async(to_email, notification_type, title,
                                                 message, details, priority, use_default_recipients, attachments,
                                                 **kwargs)


def send_email_async(to_email=None, subject=None, content=None, content_type='html',
                     attachments: Optional[List[Tuple[str, Union[str, bytes]]]] = None,
                     cc_emails=None, bcc_emails=None, use_default_recipients=True, **kwargs):
    """
    异步发送自定义邮件

    参数:
        - to_email: 收件人邮箱，可以是字符串或列表
        - subject: 邮件主题
        - content: 邮件内容
        - content_type: 内容类型，'html'或'plain'
        - attachments: 附件列表，格式为 [(文件名, 文件路径或文件内容), ...]
        - cc_emails: 抄送邮箱列表
        - bcc_emails: 密送邮箱列表
        - use_default_recipients: 是否使用配置中的默认收件人列表 (默认为 True)
        - **kwargs: 其他参数

    返回:
        - tuple: (成功状态, 消息)
    """
    sender = get_async_email_sender()
    return sender.send_email_async(to_email, subject, content, content_type, attachments,
                                   cc_emails, bcc_emails, use_default_recipients, **kwargs)


def get_email_queue_stats() -> Dict[str, int]:
    """
    获取邮件队列统计信息

    返回:
        - dict: 队列统计信息，包含待发送、发送中、成功、失败等数量
    """
    sender = get_async_email_sender()
    return sender.get_stats()


# 测试函数
def test_async_email_system_with_attachments():   
    """测试异步邮件系统（带附件）"""
    import json

    try:
        sender = get_async_email_sender()
        print("✅ 异步邮件发送器初始化成功")

        # 显示初始统计
        stats = sender.get_stats()
        print(f"📊 初始统计: {json.dumps(stats, indent=2)}")

        # 创建测试附件文件
        test_attachment_path = Path("test_attachment.txt")
        try:
            with open(test_attachment_path, "w", encoding="utf-8") as f:
                f.write("这是一个测试附件文件内容\n用于测试邮件附件功能")
            print(f"✅ 创建测试附件文件: {test_attachment_path}")
        except Exception as e:
            print(f"⚠️ 无法创建测试附件文件: {e}")
            test_attachment_path = None

        # 测试发送带附件的邮件任务
        test_tasks = [
            {
                'function': send_backup_notification_async,
                'args': (None, 'database', {'status': 'success'}, '100MB', '30s', True),
                'attachments': [('backup_report.txt', str(test_attachment_path))] if test_attachment_path else None,
                'description': '备份通知测试（带附件）'
            },
            {
                'function': send_error_notification_async,
                'args': (None, '连接错误', '数据库连接失败', 'Timeout', '检查服务状态', True),
                'attachments': [('error_log.txt', str(test_attachment_path))] if test_attachment_path else None,
                'description': '错误通知测试（带附件）'
            },
            {
                'function': send_email_async,
                'args': (
                    None,
                    '测试带附件邮件',
                    '<h1>这是一封测试邮件</h1><p>包含附件测试</p>',
                    'html',
                    [('test_file.txt', str(test_attachment_path))] if test_attachment_path else None,
                    None, None, True
                ),
                'description': '直接邮件测试（带附件）'
            }
        ]

        # 发送测试任务
        for i, task in enumerate(test_tasks, 1):
            # 如果有附件，添加到参数中
            kwargs = {}
            if task.get('attachments'):
                kwargs['attachments'] = task['attachments']

            success, message = task['function'](*task['args'], **kwargs)
            if success:
                print(f"✅ 测试任务 {i} 已加入队列: {task['description']}")
            else:
                print(f"❌ 测试任务 {i} 加入队列失败: {message}")

        # 等待任务处理完成
        print("⏳ 等待邮件任务处理...")
        if sender.wait_until_empty(timeout=30):
            print("✅ 所有邮件任务处理完成")
        else:
            print("⚠️ 邮件任务处理超时")

        # 显示最终统计
        final_stats = sender.get_stats()
        print(f"📊 最终统计: {json.dumps(final_stats, indent=2)}")

        # 清理测试文件
        if test_attachment_path and test_attachment_path.exists():
            test_attachment_path.unlink()
            print(f"✅ 清理测试附件文件: {test_attachment_path}")

        # 关闭发送器
        shutdown_async_email_sender()
        print("✅ 异步邮件系统测试完成")

    except Exception as e:
        print(f"❌ 异步邮件系统测试失败: {e}")
        traceback.print_exc()


if __name__ == '__main__':
    # 设置日志格式
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )

    test_async_email_system_with_attachments()