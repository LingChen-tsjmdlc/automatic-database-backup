#!/usr/bin/env python3
"""
数据库备份工具（模块化版 + 日志系统 + rich 表格）
支持多数据库备份，每个表单独备份为SQL文件，然后打包压缩
配置全部从 config.yaml 中读取
日志输出使用 scripts/log/log.py
"""

import shutil
import subprocess
import tarfile
import time
from datetime import datetime
from io import StringIO
from pathlib import Path
from typing import List, Optional

import yaml
from rich.console import Console
from rich.table import Table

# 引入日志系统
from scripts.log.log import log


class DatabaseBackup:
    """数据库备份工具类（日志系统 + rich 表格）"""

    def __init__(self, config_path: Optional[str] = None):
        # 自动寻找配置文件
        self.config_path = Path(config_path) if config_path else (
                Path(__file__).parent.parent.parent / "config.yaml"
        )
        self.config = self._load_config()
        self.backup_path = Path(self.config.get('backup_path', './backup')).resolve()
        self.mysql_config = self.config.get('mysql', {})

        self.backup_path.mkdir(parents=True, exist_ok=True)
        self._check_mysql_commands()

        log.info(f"备份目录: {self.backup_path}, 数据库数量: {len(self.get_databases())}")

    # ------------------------
    # 配置文件加载
    # ------------------------
    def _load_config(self) -> dict:
        if not self.config_path.exists():
            log.error(f"未找到配置文件: {self.config_path}")
            raise FileNotFoundError(f"未找到配置文件: {self.config_path}")
        with open(self.config_path, 'r', encoding='utf-8') as f:
            cfg = yaml.safe_load(f)
        cfg.setdefault('mysql', {}).setdefault('database', [])
        cfg.setdefault('backup_path', './backup')
        log.info(f"配置文件加载成功: {self.config_path}")
        return cfg

    # ------------------------
    # 检查MySQL命令
    # ------------------------
    def _check_mysql_commands(self):
        for cmd in ['mysql', 'mysqldump']:
            try:
                subprocess.run([cmd, '--version'], capture_output=True, check=True)
                log.info(f"[检查] {cmd} 可用")
            except (FileNotFoundError, subprocess.CalledProcessError):
                log.critical(f"{cmd} 未找到，请安装 MySQL 客户端并配置 PATH")
                raise RuntimeError(f"{cmd} 未找到，请安装 MySQL 客户端并配置 PATH")

    # ------------------------
    # 获取数据库列表
    # ------------------------
    def get_databases(self) -> List[str]:
        dbs = self.mysql_config.get('database', [])
        if isinstance(dbs, str):
            return [dbs]
        elif isinstance(dbs, list):
            return dbs
        return []

    # ------------------------
    # 构建MySQL连接参数
    # ------------------------
    def get_mysql_connection_args(self) -> List[str]:
        args = []
        host = self.mysql_config.get('host', '127.0.0.1')
        if host and host != 'localhost':
            args.extend(['-h', str(host)])
        port = self.mysql_config.get('port', 3306)
        if port and port != 3306:
            args.extend(['-P', str(port)])
        user = self.mysql_config.get('user', 'root')
        if user:
            args.extend(['-u', user])
        password = self.mysql_config.get('password', '')
        if password:
            args.append(f'--password={password}')
        return args

    # ------------------------
    # 获取数据库表列表
    # ------------------------
    def get_database_tables(self, database: str) -> List[str]:
        try:
            args = self.get_mysql_connection_args()
            args.extend(['-N', '-e', f"SHOW TABLES FROM {database}"])
            result = subprocess.run(['mysql'] + args, capture_output=True, text=True)
            if result.returncode != 0:
                log.error(f"[错误] 获取数据库 {database} 表列表失败: {result.stderr}")
                return []
            tables = [t.strip() for t in result.stdout.splitlines() if t.strip()]
            log.info(f" 数据库 {database} 找到 {len(tables)} 个表")
            return tables
        except Exception as e:
            log.error(f" 获取数据库 {database} 表列表失败: {e}")
            return []

    # ------------------------
    # 创建备份目录
    # ------------------------
    def create_backup_folder(self, database: str, timestamp: str) -> Path:
        backup_dir = self.backup_path / database / timestamp
        backup_dir.mkdir(parents=True, exist_ok=True)
        log.debug(f"创建备份目录: {backup_dir}")
        return backup_dir

    # ------------------------
    # 备份单表
    # ------------------------
    def backup_table(self, database: str, table: str, backup_dir: Path) -> bool:
        table_file = backup_dir / f"{table}.sql"
        dump_args = self.get_mysql_connection_args()
        dump_args.extend([
            '--single-transaction',
            '--skip-lock-tables',
            '--default-character-set=utf8mb4',
            database,
            table
        ])
        try:
            with open(table_file, 'w', encoding='utf-8') as f:
                result = subprocess.run(['mysqldump'] + dump_args, stdout=f,
                                        stderr=subprocess.PIPE, text=True)
            if result.returncode != 0:
                log.error(f"[失败] 备份表 {database}.{table}: {result.stderr}")
                return False
            log.info(f" 备份表成功 {database}.{table}")
            return True
        except Exception as e:
            log.error(f" 备份表 {database}.{table}: {e}")
            return False

    # ------------------------
    # 创建压缩包
    # ------------------------
    def create_backup_archive(self, backup_dir: Path, database: str, timestamp: str) -> Path:
        archive_file = backup_dir / f"{database}_{timestamp}.tar.gz"
        with tarfile.open(archive_file, 'w:gz') as tar:
            for sql_file in backup_dir.glob("*.sql"):
                tar.add(sql_file, arcname=f"{database}/{sql_file.name}")
        log.info(f" 创建压缩包: {archive_file}")
        return archive_file

    # ------------------------
    # rich 表格日志方法
    # ------------------------
    def log_rich(self, title: str, data: dict):
        """渲染字典为 rich 表格日志"""
        table = Table(title=title)
        table.add_column("键")
        table.add_column("值")
        for k, v in data.items():
            table.add_row(str(k), str(v))
        buffer = StringIO()
        console_file = Console(file=buffer, force_terminal=False, color_system=None)
        console_file.print(table)
        for line in buffer.getvalue().splitlines():
            log.info(line)
        Console().print(table)  # 控制台输出

    # ------------------------
    # 备份单数据库
    # ------------------------
    def backup_database(self, database: str, compress: bool = True, as_json: bool = False) -> Optional[dict]:
        start_time = time.time()
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_dir = self.create_backup_folder(database, timestamp)
        tables = self.get_database_tables(database)
        if not tables:
            log.warning(f"[警告] 数据库 {database} 中没有表或无法访问")
            result_data = {'error': f"{database} 中没有表或无法访问"}
            if as_json:
                return result_data
            return None

        success_tables, failed_tables = [], []
        total_size = 0
        for table in tables:
            if self.backup_table(database, table, backup_dir):
                success_tables.append(table)
                total_size += (backup_dir / f"{table}.sql").stat().st_size
            else:
                failed_tables.append(table)

        archive_file, archive_size = None, 0
        if compress and success_tables:
            archive_file = self.create_backup_archive(backup_dir, database, timestamp)
            archive_size = archive_file.stat().st_size if archive_file.exists() else 0

        duration = round(time.time() - start_time, 2)

        info = {
            'database': database,
            'timestamp': timestamp,
            'backup_dir': str(backup_dir),
            'archive_file': str(archive_file) if archive_file else None,
            'tables_total': len(tables),
            'tables_success': len(success_tables),
            'tables_failed': len(failed_tables),
            'success_tables': success_tables,
            'failed_tables': failed_tables,
            'total_size': self._format_size(total_size),
            'archive_size': self._format_size(archive_size),
            'raw_size': total_size,
            'archive_raw_size': archive_size,
            'duration': duration,
            'compress': compress,
            'status': 'success' if not failed_tables else 'partial'
        }

        # 输出 rich 表格
        self.log_rich(f"备份结果: {database}", info)

        return info if as_json else None

    # ------------------------
    # 备份所有数据库
    # ------------------------
    def backup_all_databases(self, compress: bool = True, as_json: bool = False) -> Optional[dict]:
        results = {}
        for db in self.get_databases():
            info = self.backup_database(db, compress, as_json=True)
            results[db] = info
        # 输出总览 rich 表格
        self.log_rich("所有数据库备份总览", {db: info.get('status', 'unknown') for db, info in results.items()})
        return results if as_json else None

    # ------------------------
    # 清理旧备份
    # ------------------------
    def cleanup_old_backups(self, keep_days: int = 7, keep_count: int = 10, as_json: bool = False) -> Optional[dict]:
        deleted_dirs, deleted_files = 0, 0
        cutoff_time = time.time() - keep_days * 24 * 3600

        for db_dir in self.backup_path.iterdir():
            if not db_dir.is_dir():
                continue
            backup_dirs = sorted([d for d in db_dir.iterdir() if d.is_dir()],
                                 key=lambda x: x.name, reverse=True)
            for idx, backup_dir in enumerate(backup_dirs):
                try:
                    dir_time = datetime.strptime(backup_dir.name, "%Y%m%d_%H%M%S").timestamp()
                    if dir_time < cutoff_time or idx >= keep_count:
                        shutil.rmtree(backup_dir)
                        deleted_dirs += 1
                        log.info(f" 删除旧备份目录: {backup_dir}")
                except Exception:
                    continue
        log.info(f" 清理完成, 删除 {deleted_dirs} 个目录, {deleted_files} 个压缩包")
        result = {'deleted_dirs': deleted_dirs, 'deleted_files': deleted_files}
        return result if as_json else None

    # ------------------------
    # 工具函数
    # ------------------------
    @staticmethod
    def _format_size(size_bytes: int) -> str:
        for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
            if size_bytes < 1024:
                return f"{size_bytes:.2f} {unit}"
            size_bytes /= 1024
        return f"{size_bytes:.2f} PB"


# ------------------------
# 快捷函数说明
# ------------------------

def backup_single_database(database: str, compress: bool = True, config_path: Optional[str] = None,
                           as_json: bool = False):
    """
    备份单个数据库。

    参数:
        - database (str): 要备份的数据库名称。
        - compress (bool, 默认 True): 是否将备份的 SQL 文件打包成 .tar.gz 压缩包。
        - config_path (Optional[str], 默认 None): 指定 config.yaml 配置文件路径，若为 None 则使用默认路径。
        - as_json (bool, 默认 False): 是否返回字典形式的备份信息。False 时仅打印日志，不返回数据。

    返回值:
        如果 as_json=True，返回 dict，包含如下字段：
            - database: 数据库名称
            - timestamp: 备份时间戳
            - backup_dir: SQL 文件备份目录路径
            - archive_file: 压缩包路径（如果 compress=True）
            - tables_total: 总表数
            - tables_success: 成功备份表数
            - tables_failed: 失败表数
            - success_tables: 成功备份的表名列表
            - failed_tables: 失败备份的表名列表
            - total_size: SQL 文件总大小（可读格式）
            - archive_size: 压缩包大小（可读格式）
            - raw_size: SQL 文件总大小（字节）
            - archive_raw_size: 压缩包大小（字节）
            - duration: 备份耗时（秒）
            - compress: 是否压缩
            - status: 备份状态 ('success', 'partial')

    用法示例:
        summary = backup_single_database("mydb", compress=True, as_json=True)
    """
    return DatabaseBackup(config_path).backup_database(database, compress, as_json)


def backup_all_databases(compress: bool = True, config_path: Optional[str] = None, as_json: bool = False):
    """
    备份配置文件中所有数据库。

    参数:
        - compress (bool, 默认 True): 是否将每个数据库的 SQL 文件打包成 .tar.gz 压缩包。
        - config_path (Optional[str], 默认 None): 指定 config.yaml 配置文件路径，若为 None 则使用默认路径。
        - as_json (bool, 默认 False): 是否返回字典形式的备份信息。False 时仅打印日志，不返回数据。

    返回值:
        如果 as_json=True，返回 dict，键为数据库名，值为 backup_database() 返回的备份信息字典。
        同时在控制台输出 rich 表格总览，包括每个数据库的备份状态。

    用法示例:
        summary = backup_all_databases(as_json=True)
    """
    return DatabaseBackup(config_path).backup_all_databases(compress, as_json)


def cleanup_old_backups(keep_days: int = 7, keep_count: int = 10, config_path: Optional[str] = None,
                        as_json: bool = False):
    """
    清理旧备份目录，按时间和数量保留最新备份。

    参数:
        - keep_days (int, 默认 7): 保留最近多少天的备份，超过该天数的备份目录会被删除。
        - keep_count (int, 默认 10): 保留每个数据库最近多少个备份目录，超过该数量的旧备份目录会被删除。
        - config_path (Optional[str], 默认 None): 指定 config.yaml 配置文件路径，若为 None 则使用默认路径。
        - as_json (bool, 默认 False): 是否返回字典形式的清理信息。False 时仅打印日志，不返回数据。

    返回值:
        如果 as_json=True，返回 dict，包含：
            - deleted_dirs: 删除的备份目录数量
            - deleted_files: 删除的压缩包文件数量（目前 SQL 文件以目录形式计数，压缩包数量统计可扩展）

    用法示例:
        result = cleanup_old_backups(keep_days=30, keep_count=5, as_json=True)
    """
    return DatabaseBackup(config_path).cleanup_old_backups(keep_days, keep_count, as_json)


# ------------------------
# 测试
# ------------------------
if __name__ == "__main__":
    log.info("开始备份所有数据库")
    summary = backup_all_databases(as_json=True)
    log.info(f"备份结果（字典返回）: {summary}")
