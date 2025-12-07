#!/usr/bin/env python3
"""
系统监控脚本
跨平台获取系统信息：CPU、内存、磁盘、系统信息等
返回JSON格式，包含时间戳
实时获取，无等待
支持rich表格日志输出
"""

import datetime
import os
import platform
import socket
import time
import uuid
from io import StringIO
from typing import Dict, Any, List

import psutil
from rich.console import Console
from rich.table import Table

from scripts.log.log import log

try:
    import GPUtil

    HAS_GPU = True
except ImportError:
    HAS_GPU = False
    log.warning("GPU监控不可用，请安装gputil: pip install gputil")


class SystemMonitor:
    """系统监控器"""

    def __init__(self):
        """初始化系统监控器"""
        log.info("系统监控器初始化完成")
        # 初始化CPU使用率计算（避免第一次调用返回0）
        psutil.cpu_percent(interval=None)

    def get_system_info(self) -> Dict[str, Any]:
        """获取系统基础信息"""
        try:
            boot_time = datetime.datetime.fromtimestamp(psutil.boot_time())

            info = {
                'platform': platform.system(),
                'platform_release': platform.release(),
                'platform_version': platform.version(),
                'architecture': platform.machine(),
                'processor': platform.processor(),
                'hostname': socket.gethostname(),
                'ip_address': self._get_ip_address(),
                'mac_address': self._get_mac_address(),
                'python_version': platform.python_version(),
                'boot_time': boot_time.strftime('%Y-%m-%d %H:%M:%S'),
                'boot_timestamp': int(psutil.boot_time())
            }
            return info
        except Exception as e:
            log.error(f"获取系统信息失败: {e}")
            return {'error': str(e)}

    def _get_ip_address(self) -> str:
        """获取IP地址"""
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            s.connect(("8.8.8.8", 80))
            ip = s.getsockname()[0]
            s.close()
            return ip
        except:
            return "127.0.0.1"

    def _get_mac_address(self) -> str:
        """获取MAC地址"""
        try:
            mac = ':'.join(['{:02x}'.format((uuid.getnode() >> elements) & 0xff)
                            for elements in range(0, 2 * 6, 2)][::-1])
            return mac
        except:
            return "00:00:00:00:00:00"

    def get_cpu_info(self) -> Dict[str, Any]:
        """获取CPU信息（无等待）"""
        try:
            # 使用interval=None获取瞬时CPU使用率
            cpu_percent = psutil.cpu_percent(interval=None, percpu=True)
            cpu_count_logical = psutil.cpu_count(logical=True)
            cpu_count_physical = psutil.cpu_count(logical=False)

            cpu_info = {
                'usage_per_core': cpu_percent,
                'usage_total': round(sum(cpu_percent) / len(cpu_percent), 2) if cpu_percent else 0,
                'count_logical': cpu_count_logical,
                'count_physical': cpu_count_physical,
                'load_average': self._get_load_average()
            }

            # 尝试获取CPU频率
            try:
                cpu_freq = psutil.cpu_freq()
                if cpu_freq:
                    cpu_info.update({
                        'frequency_current': round(cpu_freq.current, 2),
                        'frequency_max': round(cpu_freq.max, 2),
                        'frequency_min': round(cpu_freq.min, 2)
                    })
            except:
                pass

            return cpu_info
        except Exception as e:
            log.error(f"获取CPU信息失败: {e}")
            return {'error': str(e), 'usage_total': 0}

    def _get_load_average(self) -> List[float]:
        """获取系统负载（无等待）"""
        try:
            if platform.system() == 'Windows':
                return [0, 0, 0]  # Windows没有loadavg
            load_avg = list(os.getloadavg())
            return [round(x, 2) for x in load_avg]
        except:
            return [0, 0, 0]

    def get_memory_info(self) -> Dict[str, Any]:
        """获取内存信息（无等待）"""
        try:
            memory = psutil.virtual_memory()
            swap = psutil.swap_memory()

            memory_info = {
                'total': self._format_size(memory.total),
                'used': self._format_size(memory.used),
                'available': self._format_size(memory.available),
                'free': self._format_size(memory.free),
                'usage_percent': round(memory.percent, 2),
                'swap_total': self._format_size(swap.total),
                'swap_used': self._format_size(swap.used),
                'swap_free': self._format_size(swap.free),
                'swap_usage_percent': round(swap.percent, 2)
            }

            # 添加原始字节数用于计算
            memory_info.update({
                'total_bytes': memory.total,
                'used_bytes': memory.used,
                'available_bytes': memory.available,
                'free_bytes': memory.free
            })

            return memory_info
        except Exception as e:
            log.error(f"获取内存信息失败: {e}")
            return {'error': str(e), 'usage_percent': 0}

    def get_disk_info(self) -> Dict[str, Any]:
        """获取磁盘信息（无等待）"""
        try:
            disk_info = {}
            total_size = 0
            total_used = 0
            total_free = 0

            for partition in psutil.disk_partitions(all=False):
                try:
                    usage = psutil.disk_usage(partition.mountpoint)

                    partition_info = {
                        'device': partition.device,
                        'mountpoint': partition.mountpoint,
                        'fstype': partition.fstype,
                        'total': self._format_size(usage.total),
                        'used': self._format_size(usage.used),
                        'free': self._format_size(usage.free),
                        'usage_percent': round(usage.percent, 2)
                    }

                    disk_info[partition.mountpoint] = partition_info

                    # 统计总量
                    total_size += usage.total
                    total_used += usage.used
                    total_free += usage.free

                except (PermissionError, FileNotFoundError):
                    continue

            # 计算总体磁盘使用率
            overall_usage = (total_used / total_size * 100) if total_size > 0 else 0

            return {
                'partitions': disk_info,
                'overall': {
                    'total': self._format_size(total_size),
                    'used': self._format_size(total_used),
                    'free': self._format_size(total_free),
                    'usage_percent': round(overall_usage, 2),
                    'total_bytes': total_size,
                    'used_bytes': total_used,
                    'free_bytes': total_free
                }
            }
        except Exception as e:
            log.error(f"获取磁盘信息失败: {e}")
            return {'partitions': {}, 'overall': {'usage_percent': 0, 'error': str(e)}}

    def get_gpu_info(self) -> Dict[str, Any]:
        """获取GPU信息（如果可用，无等待）"""
        if not HAS_GPU:
            return {'available': False, 'message': 'GPU监控不可用'}

        try:
            gpus = GPUtil.getGPUs()
            if not gpus:
                return {'available': True, 'gpus': [], 'message': '未检测到GPU'}

            gpu_info = []
            total_load = 0
            total_memory_used = 0
            total_memory_total = 0

            for gpu in gpus:
                gpu_data = {
                    'id': gpu.id,
                    'name': gpu.name,
                    'load_percent': round(gpu.load * 100, 2),
                    'memory_used': self._format_size(gpu.memoryUsed * 1024 * 1024),
                    'memory_total': self._format_size(gpu.memoryTotal * 1024 * 1024),
                    'memory_free': self._format_size(gpu.memoryFree * 1024 * 1024),
                    'temperature': getattr(gpu, 'temperature', 'N/A')
                }

                gpu_info.append(gpu_data)
                total_load += gpu.load * 100
                total_memory_used += gpu.memoryUsed
                total_memory_total += gpu.memoryTotal

            avg_load = total_load / len(gpus) if gpus else 0
            avg_memory_usage = (total_memory_used / total_memory_total * 100) if total_memory_total > 0 else 0

            return {
                'available': True,
                'gpus': gpu_info,
                'summary': {
                    'gpu_count': len(gpus),
                    'avg_load_percent': round(avg_load, 2),
                    'avg_memory_usage_percent': round(avg_memory_usage, 2)
                }
            }
        except Exception as e:
            log.error(f"获取GPU信息失败: {e}")
            return {'available': False, 'error': str(e)}

    def get_uptime(self) -> Dict[str, Any]:
        """获取系统运行时间（无等待）"""
        try:
            boot_time = psutil.boot_time()
            uptime_seconds = time.time() - boot_time

            days = int(uptime_seconds // 86400)
            hours = int((uptime_seconds % 86400) // 3600)
            minutes = int((uptime_seconds % 3600) // 60)
            seconds = int(uptime_seconds % 60)

            return {
                'seconds': int(uptime_seconds),
                'formatted': f"{days}天{hours}小时{minutes}分{seconds}秒",
                'days': days,
                'hours': hours,
                'minutes': minutes,
                'seconds_total': seconds
            }
        except Exception as e:
            log.error(f"获取运行时间失败: {e}")
            return {'seconds': 0, 'formatted': '0秒', 'error': str(e)}

    def _format_size(self, size_bytes: int) -> str:
        """格式化字节大小为可读格式"""
        if size_bytes == 0:
            return "0 B"

        for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
            if size_bytes < 1024.0:
                return f"{size_bytes:.2f} {unit}"
            size_bytes /= 1024.0
        return f"{size_bytes:.2f} PB"

    def log_rich(self, title: str, data: dict):
        """渲染字典为 rich 表格日志"""
        table = Table(title=title)
        table.add_column("属性", width=20)
        table.add_column("值", width=30)

        for k, v in data.items():
            table.add_row(str(k), str(v))

        # 输出到控制台
        Console().print(table)

        # 输出到日志（纯文本格式）
        buffer = StringIO()
        console_file = Console(file=buffer, force_terminal=False, color_system=None)
        console_file.print(table)
        for line in buffer.getvalue().splitlines():
            log.info(line)

    def get_summary(self, as_json: bool = False) -> Dict[str, Any]:
        """获取系统信息摘要（无等待）"""
        current_time = datetime.datetime.now()

        try:
            system_info = self.get_system_info()
            cpu_info = self.get_cpu_info()
            memory_info = self.get_memory_info()
            disk_info = self.get_disk_info()
            gpu_info = self.get_gpu_info()
            uptime_info = self.get_uptime()

            summary = {
                'timestamp': current_time.strftime('%Y-%m-%d %H:%M:%S'),
                'timestamp_iso': current_time.isoformat(),
                'system': {
                    'platform': system_info.get('platform', 'Unknown'),
                    'hostname': system_info.get('hostname', 'Unknown'),
                    'ip_address': system_info.get('ip_address', 'Unknown')
                },
                'cpu': {
                    'usage_percent': cpu_info.get('usage_total', 0),
                    'core_count': cpu_info.get('count_logical', 0)
                },
                'memory': {
                    'usage_percent': memory_info.get('usage_percent', 0),
                    'used': memory_info.get('used', '0 B'),
                    'total': memory_info.get('total', '0 B')
                },
                'disk': {
                    'usage_percent': disk_info.get('overall', {}).get('usage_percent', 0),
                    'used': disk_info.get('overall', {}).get('used', '0 B'),
                    'total': disk_info.get('overall', {}).get('total', '0 B')
                },
                'uptime': uptime_info.get('formatted', '0秒')
            }

            # 如果有GPU信息，添加到摘要
            if gpu_info.get('available') and gpu_info.get('gpus'):
                gpu = gpu_info['gpus'][0]  # 取第一个GPU
                summary['gpu'] = {
                    'usage_percent': gpu.get('load_percent', 0),
                    'memory_used': gpu.get('memory_used', '0 B'),
                    'memory_total': gpu.get('memory_total', '0 B')
                }

            if not as_json:
                # 输出rich表格
                rich_data = {
                    '时间': summary['timestamp'],
                    '系统平台': summary['system']['platform'],
                    '主机名': summary['system']['hostname'],
                    'IP地址': summary['system']['ip_address'],
                    'CPU使用率': f"{summary['cpu']['usage_percent']}%",
                    'CPU核心数': summary['cpu']['core_count'],
                    '内存使用率': f"{summary['memory']['usage_percent']}%",
                    '内存使用量': f"{summary['memory']['used']}/{summary['memory']['total']}",
                    '磁盘使用率': f"{summary['disk']['usage_percent']}%",
                    '磁盘使用量': f"{summary['disk']['used']}/{summary['disk']['total']}",
                    '系统运行时间': summary['uptime']
                }
                if 'gpu' in summary:
                    rich_data['GPU使用率'] = f"{summary['gpu']['usage_percent']}%"
                    rich_data['GPU显存'] = f"{summary['gpu']['memory_used']}/{summary['gpu']['memory_total']}"

                self.log_rich("系统监控摘要", rich_data)

            return summary

        except Exception as e:
            log.error(f"获取系统摘要失败: {e}")
            result = {
                'timestamp': current_time.strftime('%Y-%m-%d %H:%M:%S'),
                'error': str(e)
            }
            if not as_json:
                self.log_rich("系统监控错误", {'错误': str(e)})
            return result

    def get_detailed_info(self, as_json: bool = False) -> Dict[str, Any]:
        """获取详细系统信息（无等待）"""
        current_time = datetime.datetime.now()

        try:
            detailed_info = {
                'timestamp': current_time.strftime('%Y-%m-%d %H:%M:%S'),
                'timestamp_iso': current_time.isoformat(),
                'system': self.get_system_info(),
                'cpu': self.get_cpu_info(),
                'memory': self.get_memory_info(),
                'disk': self.get_disk_info(),
                'gpu': self.get_gpu_info(),
                'uptime': self.get_uptime()
            }

            if not as_json:
                # 输出详细信息的rich表格
                system_info = detailed_info['system']
                cpu_info = detailed_info['cpu']
                memory_info = detailed_info['memory']
                disk_info = detailed_info['disk']
                uptime_info = detailed_info['uptime']

                # 系统信息表格
                sys_table_data = {
                    '平台': system_info.get('platform', 'Unknown'),
                    '版本': system_info.get('platform_version', 'Unknown'),
                    '架构': system_info.get('architecture', 'Unknown'),
                    '处理器': system_info.get('processor', 'Unknown')[:30] + '...',
                    '主机名': system_info.get('hostname', 'Unknown'),
                    'IP地址': system_info.get('ip_address', 'Unknown'),
                    '启动时间': system_info.get('boot_time', 'Unknown'),
                    'Python版本': system_info.get('python_version', 'Unknown')
                }
                self.log_rich("系统信息", sys_table_data)

                # CPU信息表格
                cpu_table_data = {
                    '总使用率': f"{cpu_info.get('usage_total', 0)}%",
                    '逻辑核心数': cpu_info.get('count_logical', 0),
                    '物理核心数': cpu_info.get('count_physical', 0),
                    '当前频率': f"{cpu_info.get('frequency_current', 'N/A')} MHz",
                    '最大频率': f"{cpu_info.get('frequency_max', 'N/A')} MHz"
                }
                self.log_rich("CPU信息", cpu_table_data)

                # 内存信息表格
                mem_table_data = {
                    '使用率': f"{memory_info.get('usage_percent', 0)}%",
                    '已用内存': memory_info.get('used', '0 B'),
                    '总内存': memory_info.get('total', '0 B'),
                    '可用内存': memory_info.get('available', '0 B'),
                    '交换分区使用率': f"{memory_info.get('swap_usage_percent', 0)}%"
                }
                self.log_rich("内存信息", mem_table_data)

                # 磁盘信息表格
                disk_overall = disk_info.get('overall', {})
                disk_table_data = {
                    '总使用率': f"{disk_overall.get('usage_percent', 0)}%",
                    '已用空间': disk_overall.get('used', '0 B'),
                    '总空间': disk_overall.get('total', '0 B'),
                    '可用空间': disk_overall.get('free', '0 B'),
                    '分区数量': len(disk_info.get('partitions', {}))
                }
                self.log_rich("磁盘信息", disk_table_data)

                # 运行时间表格
                uptime_table_data = {
                    '运行时间': uptime_info.get('formatted', '0秒'),
                    '总秒数': uptime_info.get('seconds', 0)
                }
                self.log_rich("系统运行时间", uptime_table_data)

                # GPU信息（如果有）
                if detailed_info['gpu'].get('available') and detailed_info['gpu'].get('gpus'):
                    gpu = detailed_info['gpu']['gpus'][0]
                    gpu_table_data = {
                        'GPU名称': gpu.get('name', 'Unknown'),
                        '使用率': f"{gpu.get('load_percent', 0)}%",
                        '显存使用': f"{gpu.get('memory_used', '0 B')}/{gpu.get('memory_total', '0 B')}",
                        '温度': f"{gpu.get('temperature', 'N/A')}°C"
                    }
                    self.log_rich("GPU信息", gpu_table_data)

            return detailed_info

        except Exception as e:
            log.error(f"获取详细系统信息失败: {e}")
            result = {
                'timestamp': current_time.strftime('%Y-%m-%d %H:%M:%S'),
                'error': str(e)
            }
            if not as_json:
                self.log_rich("系统监控错误", {'错误': str(e)})
            return result


# 快捷函数
def get_system_summary(as_json: bool = False) -> Dict[str, Any]:
    """
    获取系统信息摘要（无等待）

    参数:
        as_json: 是否只返回JSON，不输出rich表格

    返回:
        dict: 系统信息摘要，包含时间戳
    """
    monitor = SystemMonitor()
    return monitor.get_summary(as_json=as_json)


def get_system_detailed(as_json: bool = False) -> Dict[str, Any]:
    """
    获取详细系统信息（无等待）

    参数:
        as_json: 是否只返回JSON，不输出rich表格

    返回:
        dict: 详细系统信息，包含时间戳
    """
    monitor = SystemMonitor()
    return monitor.get_detailed_info(as_json=as_json)


def get_cpu_info(as_json: bool = False) -> Dict[str, Any]:
    """
    获取CPU信息（无等待）

    参数:
        as_json: 是否只返回JSON，不输出rich表格

    返回:
        dict: CPU信息，包含时间戳
    """
    monitor = SystemMonitor()
    current_time = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')

    cpu_info = monitor.get_cpu_info()
    cpu_info['timestamp'] = current_time
    cpu_info['timestamp_iso'] = datetime.datetime.now().isoformat()

    if not as_json:
        # 输出CPU信息的rich表格
        rich_data = {
            '时间': current_time,
            '总使用率': f"{cpu_info.get('usage_total', 0)}%",
            '逻辑核心数': cpu_info.get('count_logical', 0),
            '物理核心数': cpu_info.get('count_physical', 0),
            '当前频率': f"{cpu_info.get('frequency_current', 'N/A')} MHz",
            '负载平均值': str(cpu_info.get('load_average', [0, 0, 0]))
        }
        monitor.log_rich("CPU监控信息", rich_data)

    return cpu_info


def get_memory_info(as_json: bool = False) -> Dict[str, Any]:
    """
    获取内存信息（无等待）

    参数:
        as_json: 是否只返回JSON，不输出rich表格

    返回:
        dict: 内存信息，包含时间戳
    """
    monitor = SystemMonitor()
    current_time = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')

    memory_info = monitor.get_memory_info()
    memory_info['timestamp'] = current_time
    memory_info['timestamp_iso'] = datetime.datetime.now().isoformat()

    if not as_json:
        # 输出内存信息的rich表格
        rich_data = {
            '时间': current_time,
            '使用率': f"{memory_info.get('usage_percent', 0)}%",
            '已用内存': memory_info.get('used', '0 B'),
            '总内存': memory_info.get('total', '0 B'),
            '可用内存': memory_info.get('available', '0 B'),
            '交换分区使用率': f"{memory_info.get('swap_usage_percent', 0)}%"
        }
        monitor.log_rich("内存监控信息", rich_data)

    return memory_info


def get_disk_info(as_json: bool = False) -> Dict[str, Any]:
    """
    获取磁盘信息（无等待）

    参数:
        as_json: 是否只返回JSON，不输出rich表格

    返回:
        dict: 磁盘信息，包含时间戳
    """
    monitor = SystemMonitor()
    current_time = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')

    disk_info = monitor.get_disk_info()
    disk_info['timestamp'] = current_time
    disk_info['timestamp_iso'] = datetime.datetime.now().isoformat()

    if not as_json:
        # 输出磁盘信息的rich表格
        disk_overall = disk_info.get('overall', {})
        rich_data = {
            '时间': current_time,
            '总使用率': f"{disk_overall.get('usage_percent', 0)}%",
            '已用空间': disk_overall.get('used', '0 B'),
            '总空间': disk_overall.get('total', '0 B'),
            '可用空间': disk_overall.get('free', '0 B'),
            '分区数量': len(disk_info.get('partitions', {}))
        }
        monitor.log_rich("磁盘监控信息", rich_data)

    return disk_info


def get_gpu_info(as_json: bool = False) -> Dict[str, Any]:
    """
    获取GPU信息（无等待）

    参数:
        as_json: 是否只返回JSON，不输出rich表格

    返回:
        dict: GPU信息，包含时间戳
    """
    monitor = SystemMonitor()
    current_time = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')

    gpu_info = monitor.get_gpu_info()
    gpu_info['timestamp'] = current_time
    gpu_info['timestamp_iso'] = datetime.datetime.now().isoformat()

    if not as_json and gpu_info.get('available') and gpu_info.get('gpus'):
        # 输出GPU信息的rich表格
        gpu = gpu_info['gpus'][0]
        rich_data = {
            '时间': current_time,
            'GPU名称': gpu.get('name', 'Unknown'),
            '使用率': f"{gpu.get('load_percent', 0)}%",
            '显存使用': f"{gpu.get('memory_used', '0 B')}/{gpu.get('memory_total', '0 B')}",
            '温度': f"{gpu.get('temperature', 'N/A')}°C",
            'GPU数量': gpu_info.get('summary', {}).get('gpu_count', 0)
        }
        monitor.log_rich("GPU监控信息", rich_data)

    return gpu_info


def get_uptime(as_json: bool = False) -> Dict[str, Any]:
    """
    获取系统运行时间（无等待）

    参数:
        as_json: 是否只返回JSON，不输出rich表格

    返回:
        dict: 运行时间信息，包含时间戳
    """
    monitor = SystemMonitor()
    current_time = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')

    uptime_info = monitor.get_uptime()
    uptime_info['timestamp'] = current_time
    uptime_info['timestamp_iso'] = datetime.datetime.now().isoformat()

    if not as_json:
        # 输出运行时间的rich表格
        rich_data = {
            '时间': current_time,
            '运行时间': uptime_info.get('formatted', '0秒'),
            '总秒数': uptime_info.get('seconds', 0),
            '天数': uptime_info.get('days', 0),
            '小时数': uptime_info.get('hours', 0),
            '分钟数': uptime_info.get('minutes', 0)
        }
        monitor.log_rich("系统运行时间", rich_data)

    return uptime_info


if __name__ == "__main__":
    sys = get_system_summary()
    sys_more = get_system_detailed()
    disk = get_disk_info()
    log.info(f"系统信息：{sys}")
    log.info(f"系统详细信息：{sys_more}")
    log.info(f"磁盘详细信息：{disk}")
