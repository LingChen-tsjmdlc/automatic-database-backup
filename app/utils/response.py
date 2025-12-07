from typing import Optional

from flask import jsonify


def standard_response(code: int = 200, message: str = "success", data: Optional[dict] = None):
    """
    标准化返回的工具函数

    参数：
        code (int): 状态码，200 为正常，其他可自定义
        message (str): 提示信息
        data (dict | None): 返回的数据内容

    返回：
        Flask Response 对象，包含 JSON 格式的响应
    """
    if data is None:
        data = {}

    response = {
        "code": code,
        "message": message,
        "data": data
    }
    return jsonify(response)
