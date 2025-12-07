from datetime import datetime


def get_now() -> datetime:
    """
    获取当前本地时间
    """
    return datetime.now()


def get_today_str(fmt: str = "%Y-%m-%d") -> str:
    """
    获取今天日期的字符串形式
    默认格式: 2025-12-06
    """
    return get_now().strftime(fmt)


def get_timestamp_str(fmt: str = "%Y-%m-%d %H:%M:%S") -> str:
    """
    获取当前时间戳字符串
    默认格式: 2025-12-06 02:35:18
    """
    return get_now().strftime(fmt)
