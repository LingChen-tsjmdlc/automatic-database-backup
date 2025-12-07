from datetime import datetime
from pathlib import Path

import pymysql
import yaml
from rich.table import Table

from scripts.log.log import log

SYSTEM_DATABASES = {"mysql", "sys", "performance_schema", "information_schema"}


class MySQLMonitor:
    """MySQL 监控工具（日志系统版，支持 rich 输出 + as_json 参数）"""

    def __init__(self):
        # 加载配置
        config_path = Path(__file__).parent.parent.parent / "config.yaml"
        if not config_path.exists():
            log.critical(f"配置文件不存在: {config_path}")
            raise FileNotFoundError(f"配置文件不存在: {config_path}")

        with open(config_path, "r", encoding="utf-8") as f:
            self.config = yaml.safe_load(f)

        self.mysql_cfg = self.config.get("mysql", {})
        self.databases = self.mysql_cfg.get("database", [])
        self.connection = None

        log.info("MySQL监控初始化完成")

    # ------------------------ MySQL 连接 ------------------------
    def connect(self):
        if self.connection:
            return True
        try:
            self.connection = pymysql.connect(
                host=self.mysql_cfg.get("host", "127.0.0.1"),
                port=self.mysql_cfg.get("port", 3306),
                user=self.mysql_cfg.get("user", "root"),
                password=self.mysql_cfg.get("password", ""),
                charset="utf8mb4",
                autocommit=True
            )
            log.info("MySQL连接成功")
            return True
        except Exception as e:
            log.error(f"MySQL连接失败: {e}")
            return False

    # ===================== MySQL 状态 =====================
    def monitor_status(self, as_json=False):
        if not self.connect():
            return {} if as_json else None
        status = self.get_mysql_status()
        self.log_status_table(status)
        if as_json:
            return status
        return None

    def get_mysql_status(self):
        cursor = self.connection.cursor()
        status_info = {
            "当前时间": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "运行时间": "",
            "当前连接数": "",
            "最大连接数": "",
        }
        try:
            cursor.execute("SHOW GLOBAL STATUS LIKE 'Uptime';")
            uptime = cursor.fetchone()
            if uptime:
                seconds = int(uptime[1])
                hours = seconds // 3600
                minutes = (seconds % 3600) // 60
                secs = seconds % 60
                status_info["运行时间"] = f"{hours}小时{minutes}分钟{secs}秒"

            cursor.execute("SHOW GLOBAL STATUS LIKE 'Threads_connected';")
            conn = cursor.fetchone()
            if conn:
                status_info["当前连接数"] = max(int(conn[1]) - 1, 0)

            cursor.execute("SHOW VARIABLES LIKE 'max_connections';")
            max_con = cursor.fetchone()
            if max_con:
                status_info["最大连接数"] = max_con[1]

        except Exception as e:
            log.error(f"MySQL状态读取异常: {e}")

        return status_info

    def log_status_table(self, status):
        table = Table(title="MySQL 状态")
        table.add_column("项目")
        table.add_column("值")
        for k, v in status.items():
            table.add_row(str(k), str(v))
        self.log_rich(table)

    # ===================== 数据库大小 =====================
    def monitor_database_sizes(self, as_json=False):
        if not self.connect():
            return {} if as_json else None
        db_sizes = self.get_database_sizes()
        self.log_database_sizes(db_sizes)
        if as_json:
            return db_sizes
        return None

    def get_database_sizes(self):
        cursor = self.connection.cursor()
        sql = """
        SELECT table_schema AS db_name,
               SUM(data_length + index_length) AS size_bytes
        FROM information_schema.tables
        GROUP BY table_schema;
        """
        results = {}
        try:
            cursor.execute(sql)
            for db, size in cursor.fetchall():
                if db not in SYSTEM_DATABASES:
                    results[db] = size or 0
        except Exception as e:
            log.error(f"获取数据库大小失败: {e}")
        return results

    def log_database_sizes(self, db_sizes):
        table = Table(title="数据库大小（已排除系统数据库）")
        table.add_column("数据库名")
        table.add_column("大小 (MB)")
        for db, size in db_sizes.items():
            table.add_row(db, f"{size/1024/1024:.2f}")
        self.log_rich(table)

    # ===================== 表行数统计 =====================
    def monitor_table_rows(self, as_json=False):
        if not self.connect():
            return {} if as_json else None
        all_rows = {}
        for db in self.databases:
            try:
                rows = self.get_table_rows(db)
                self.log_table_rows(db, rows)
                all_rows[db] = rows
            except Exception as e:
                log.error(f"{db} 表行数读取失败: {e}")
        if as_json:
            return all_rows
        return None

    def get_table_rows(self, db_name):
        cursor = self.connection.cursor()
        cursor.execute(f"USE `{db_name}`")
        sql = """
        SELECT table_name, table_rows
        FROM information_schema.tables
        WHERE table_schema = %s
        """
        cursor.execute(sql, (db_name,))
        return cursor.fetchall()

    def log_table_rows(self, db_name, rows):
        table = Table(title=f"{db_name} - 表行数")
        table.add_column("表名")
        table.add_column("行数")
        for t, r in rows:
            table.add_row(t, str(r))
        self.log_rich(table)

    # ===================== 表结构统计 =====================
    def monitor_table_structure(self, as_json=False):
        if not self.connect():
            return {} if as_json else None
        all_structures = {}
        for db in self.databases:
            try:
                rows = self.get_table_rows(db)
                db_structures = {}
                for table_name, _ in rows:
                    structure = self.get_table_structure(db, table_name)
                    self.log_table_structure(db, table_name, structure)
                    db_structures[table_name] = structure
                all_structures[db] = db_structures
            except Exception as e:
                log.error(f"{db} 表结构读取失败: {e}")
        if as_json:
            return all_structures
        return None

    def get_table_structure(self, db_name, table_name):
        cursor = self.connection.cursor()
        cursor.execute(f"USE `{db_name}`")
        cursor.execute(f"DESCRIBE `{table_name}`;")
        return cursor.fetchall()

    def log_table_structure(self, db_name, table_name, structure):
        table = Table(title=f"{db_name}.{table_name} - 表结构")
        table.add_column("字段")
        table.add_column("类型")
        table.add_column("允许 NULL")
        table.add_column("Key")
        table.add_column("默认值")
        table.add_column("额外信息")
        for field, type_, null, key, default, extra in structure:
            table.add_row(field, type_, null, key or "", str(default or ""), extra or "")
        self.log_rich(table)

    # ===================== rich 表格日志方法 =====================
    def log_rich(self, renderable):
        """渲染 rich 表格并写入日志和控制台"""
        from io import StringIO
        from rich.console import Console

        buffer = StringIO()
        console_file = Console(file=buffer, force_terminal=False, color_system=None)
        console_file.print(renderable)
        output_str = buffer.getvalue()

        # 写入日志
        for line in output_str.splitlines():
            log.info(line)

        # 控制台输出
        console_out = Console()
        console_out.print(renderable)

    # ===================== 快捷方法：一次性运行全部 =====================
    def run_all(self, as_json=False):
        log.info("===== 1. MySQL 状态 =====")
        self.monitor_status(as_json=as_json)

        log.info("===== 2. 数据库大小 =====")
        self.monitor_database_sizes(as_json=as_json)

        log.info("===== 3. 表行数统计 =====")
        self.monitor_table_rows(as_json=as_json)

        log.info("===== 4. 表结构统计 =====")
        self.monitor_table_structure(as_json=as_json)


if __name__ == "__main__":
    monitor = MySQLMonitor()
    monitor.monitor_status(as_json=True)
