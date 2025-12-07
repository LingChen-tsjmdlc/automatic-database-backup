from app import create_app
import yaml

# 读取配置文件
with open("config.yaml", "r", encoding="utf-8") as f:
    config = yaml.safe_load(f)

debug_mode = config.get("debug", False)     # 如果没有 debug 字段，默认为 False
port_number = config.get("port", 5000)      # 如果没有 port 字段，默认为 5000
host_url = config.get("host", "127.0.0.1")  # 如果没有 host 字段，默认为 127.0.0.1

# 创建 Flask 应用
app = create_app()

if __name__ == "__main__":
    app.run(host=host_url, port=port_number, debug=debug_mode)
