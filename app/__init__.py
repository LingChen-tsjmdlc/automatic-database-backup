import os
import yaml
from flask import Flask
from flask_cors import CORS
from app.extensions import db
from app.routes.ping import ping_bp


def create_app():
    app = Flask(__name__)

    # 获取项目根目录
    BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    config_path = os.path.join(BASE_DIR, "config.yaml")

    # 读取配置文件
    with open(config_path, "r", encoding="utf-8") as f:
        config = yaml.safe_load(f)

    app.config.update({
        "SQLALCHEMY_DATABASE_URI": f"mysql+pymysql://{config['mysql']['user']}:{config['mysql']['password']}@{config['mysql']['host']}/{config['mysql']['database']}",
        "SQLALCHEMY_TRACK_MODIFICATIONS": False,
        "SECRET_KEY": config.get("jwt", {}).get("secret_key", "default_key"),
        "UPLOAD_FOLDER": os.path.join(os.path.dirname(__file__), "uploads"),
        "MAX_CONTENT_LENGTH": 1024 * 1024 * 1024,  # 1GB
    })

    # 启用跨域
    CORS(app)

    # 初始化数据库
    db.init_app(app)

    # 注册蓝图
    app.register_blueprint(ping_bp, url_prefix="/api/v1")  # ping 检测

    return app
