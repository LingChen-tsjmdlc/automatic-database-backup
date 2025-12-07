import logging
from io import StringIO
from logging.handlers import TimedRotatingFileHandler
from pathlib import Path

import yaml
from rich.console import Console

from scripts.log.get_time import get_today_str

# ------------------------------
# 配置文件路径
# ------------------------------
config_path = Path(__file__).parent.parent.parent / "config.yaml"
with open(config_path, "r", encoding="utf-8") as f:
    config = yaml.safe_load(f)

logs_config = config.get("logs", {})
LOGS_PATH = Path(logs_config.get("logs_path", "../../logs")).resolve()
MAX_RETENTION_DAYS = logs_config.get("max_retention_days", 90)
IS_LOG_TO_CONSOLE = logs_config.get("is_log_to_console", True)

# 确保日志目录存在
LOGS_PATH.mkdir(parents=True, exist_ok=True)

# ------------------------------
# 中文日志级别映射
# ------------------------------
LOG_LEVEL_MAP = {
    "DEBUG": "调试",
    "INFO": "信息",
    "WARNING": "警告",
    "ERROR": "错误",
    "CRITICAL": "严重"
}


# ------------------------------
# 自定义日志类
# ------------------------------
class ChineseLogger:
    def __init__(self, name: str = "root"):
        self.logger = logging.getLogger(name)
        self.logger.setLevel(logging.DEBUG)  # 捕获所有级别
        self._setup_handlers()
        self.rich_console = Console(file=StringIO(), force_terminal=True, color_system=None)

    def _setup_handlers(self):
        # --------------------------
        # 文件日志 - 按天切割
        # --------------------------
        log_file = LOGS_PATH / f"{get_today_str()}.log"
        file_handler = TimedRotatingFileHandler(
            filename=str(log_file),
            when="midnight",  # 每天零点切割
            interval=1,
            backupCount=MAX_RETENTION_DAYS,
            encoding="utf-8",
            delay=False,
            utc=False
        )
        file_handler.suffix = "%Y-%m-%d.log"

        formatter = logging.Formatter(
            fmt="%(asctime)s [%(levelname)s] %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S"
        )
        file_handler.setFormatter(formatter)
        self.logger.addHandler(file_handler)

        # --------------------------
        # 控制台日志
        # --------------------------
        if IS_LOG_TO_CONSOLE:
            console_handler = logging.StreamHandler()
            console_handler.setFormatter(formatter)
            self.logger.addHandler(console_handler)

    # --------------------------
    # 中文分级日志方法
    # --------------------------
    def debug(self, msg: str):
        self.logger.debug(f"[{LOG_LEVEL_MAP['DEBUG']}] {msg}")

    def info(self, msg: str):
        self.logger.info(f"[{LOG_LEVEL_MAP['INFO']}] {msg}")

    def warning(self, msg: str):
        self.logger.warning(f"[{LOG_LEVEL_MAP['WARNING']}] {msg}")

    def error(self, msg: str):
        self.logger.error(f"[{LOG_LEVEL_MAP['ERROR']}] {msg}")

    def critical(self, msg: str):
        self.logger.critical(f"[{LOG_LEVEL_MAP['CRITICAL']}] {msg}")

    def rich(self, renderable):
        """
        支持 rich 输出格式（表格、Panel 等），直接写入日志文件和控制台
        """
        # 渲染到字符串
        file_io = StringIO()
        console = Console(file=file_io, force_terminal=False, color_system=None)
        console.print(renderable)
        output_str = file_io.getvalue()

        # 写入日志文件和控制台
        for line in output_str.splitlines():
            self.info(line)


# ------------------------------
# 单例日志
# ------------------------------
log = ChineseLogger()

# ------------------------------
# 使用示例
# ------------------------------
if __name__ == "__main__":
    log.debug("这是调试信息")
    log.info("这是一般信息")
    log.warning("这是警告信息")
    log.error("这是错误信息")
    log.critical("这是严重信息")
