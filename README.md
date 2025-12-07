# 数据库备份管理系统 

## 项目概述
本项目是一款面向运维与开发的**数据库管理**与**系统监控工具**，集 **数据库备份** 、状态监控、系统性能监控与任务调度于一体。  
基于 **Flask 提供 Web API 接口**，同时利用 **APScheduler 实现定时任务调度**，可自动进行数据库备份、状态统计和邮件通知。  
项目通过 **日志系统** 和 **Rich 表格** 提供可视化输出，使运维和开发人员能够直观了解数据库及系统状态。
## 项目结构

```text
project-root/
├─ app/                     # Flask 应用模块
│  ├─ models/               # 数据模型（ORM 或数据结构定义）
│  ├─ routes/               # API 路由或接口定义
│  └─ utils/                # 工具模块
│     ├─ __init__.py
│     └─ extensions.py      # 扩展或工具函数
│
├─ backup/                  # 数据库备份存放目录
│
├─ logs/                    # 日志文件存放目录
│
├─ scripts/                 # 脚本模块
│  ├─ database/             # 数据库相关操作脚本
│  │  ├─ backup.py          # 数据库备份脚本
│  │  └─ status_and_info.py # 数据库状态监控与信息统计
│  │
│  ├─ email/                # 邮件相关脚本
│  │  ├─ async_email.py     # 异步发送邮件
│  │  └─ send_email.py      # 邮件发送功能
│  │
│  ├─ log/                  # 日志工具脚本
│  │  ├─ get_time.py        # 获取时间相关工具
│  │  └─ log.py             # 日志记录模块
│  │
│  └─ system/               # 系统监控脚本
│     └─ system.py          # 系统信息与资源监控
│
├─ .gitignore               # Git 忽略文件
├─ config.yaml              # 配置文件
├─ config.yaml.example      # 配置文件示例
├─ main.py                  # 项目入口文件
├─ README.md                # 项目说明文档
└─ requirements.txt         # Python 依赖列表
```

## 特性
1. [x] 数据库备份 (现仅支持 mysql)
2. [x] 数据库状态监控
3. [x] 系统性能监控
4. [x] 日志与可视化
5. [x] Web API 接口 (使用了 Flask 框架，可以当后端使用)
6. [ ] 定时任务调度 (使用了 APScheduler)
7. [x] 配置化管理(使用 YAML 配置文件管理)

## 1. 快速开始

### 1.1 克隆仓库

```bash
git clone https://github.com/LingChen-tsjmdlc/automatic-database-backup.git
# 或者使用 ssh
git clone git@github.com:LingChen-tsjmdlc/automatic-database-backup.git
```

### 1.2 创建 conda 虚拟环境
```bash
# 创建环境（这里用 python 3.11，可根据你需求修改）
conda create -n automatic-database-backup python=3.10 -y

# 激活环境
conda activate automatic-database-backup

```

### 1.3 安装依赖

```bash
pip install -r requirements.txt -i https://pypi.tuna.tsinghua.edu.cn/simple
```

### 1.4 配置文件设置

复制一份`config.yaml.example`并改名为`config.yaml`，然后根据需求编辑 `config.yaml`：

```yaml
# MySQL 配置
mysql:
  host: 127.0.0.1             # 数据库主机地址
  port: 3306                  # 数据库主机端口
  user: user                  # 数据库用户名
  password: "123456password"  # 数据库密码
  database:                   # 要监控备份的数据库
    - database1
    - database2

# 备份配置
backup_path: "../../backup"

# 日志配置
logs:
  max_retention_days: 90  # 最大日志保存天数
  logs_path: "../../logs" # 日志路径
  is_log_to_console: True # 是否再控制台中输出日志

# 邮件配置
email:
  send_by: "example@example.com"    # 发送者
  send_to:                          # 接收者
    - "example@example.com"
    - "example@example.com"
  smtp_password: "smtp"             # smtp 服务密钥(不要改)
  mail_host: "smtp.xxxx.com"        # 邮箱第三方发送服务器地址(不要改)
  port: 123                         # 邮箱第三方发送服务器端口号(不要改)、

# 服务器配置
host: "127.0.0.1" # 主机地址
port: 5000        # 端口号
debug: False       # debug 模式
```

### 1.5 运行
```bash
python app.py
```

---

---

---


> 以下内容是 `./scripts` 文件夹中的工具函数的用法


## 2. 日志系统的使用方法

### 2.1 导入
```python
from scripts.log.log import log
```
### 2.2 使用
```python
log.debug("这是调试信息")
log.info("这是一般信息")
log.warning("这是警告信息")
log.error("这是错误信息")
log.critical("这是严重信息")
```

---

---

## 3. 邮箱发送使用方法

### 3.1 快速导入
```python
from scripts.email.async_email import (
    send_backup_notification_async,
    send_error_notification_async, 
    send_custom_notification_async,
    send_email_async
)
```

### 3.2 邮件发送函数

#### 3.2.1. 备份通知邮件
```python
send_backup_notification_async(
    to_email=None,                    # 可选：指定收件人，None则使用配置中的send_to列表
    backup_type="database",           # 【必须】备份类型: "database", "files", "full"
    backup_info={},                   # 【必须】备份详情字典
    file_size="100MB",                # 可选：备份文件大小
    duration="30s",                   # 可选：备份耗时
    use_default_recipients=True,      # 【必须】是否使用配置中的默认收件人
    attachments=[],                   # 可选：附件列表
    **kwargs                         # 其他参数：theme_color, site_name等，详情见 2.4 自定义主题
)
```

#### 3.2.2. 错误通知邮件
```python
send_error_notification_async(
    to_email=None,                    # 可选：指定收件人
    error_type="数据库错误",           # 错误类型
    error_message="错误描述",         # 错误信息  
    error_details="详细错误信息",     # 可选：错误详情
    solution="解决方案建议",           # 可选：解决方案
    use_default_recipients=True,      # 是否使用默认收件人
    attachments=[],                   # 可选：附件
    **kwargs
)
```

#### 3.2.3. 自定义通知邮件
```python
send_custom_notification_async(
    to_email=None,                    # 可选：指定收件人
    notification_type="info",         # 通知类型: "success", "warning", "error", "info"
    title="通知标题",                 # 邮件标题
    message="通知内容",               # 邮件内容
    details={},                       # 可选：详细信息
    priority="normal",                # 优先级: "low", "normal", "high", "urgent" 
    use_default_recipients=True,      # 是否使用默认收件人
    **kwargs
)
```


#### 3.2.4. 直接发送邮件（不带任何状态）
```python
send_email_async(
    to_email=None,                    # 可选：收件人
    subject="邮件主题",               # 邮件主题
    content="邮件内容",               # 邮件内容（HTML或文本）
    content_type="html",              # 内容类型: "html" 或 "plain"
    attachments=[],                   # 附件列表
    cc_emails=[],                     # 可选：抄送列表
    bcc_emails=[],                    # 可选：密送列表
    use_default_recipients=True,      # 是否使用默认收件人
    **kwargs
)
```

### 3.3 附件使用

```python
# 方式1：使用文件路径
attachments=[
    ("备份文件.sql", "/path/to/backup.sql"),
    ("日志文件.log", "/var/log/backup.log")
]

# 方式2：直接存放文件内容  
attachments=[
    ("错误报告.txt", "这是错误日志内容..."),
    ("统计信息.json", '{"status": "success"}')
]
```

### 3.4 自定义主题

所有函数都支持主题自定义：

```python
send_backup_notification_async(
    # 主题配置
    theme_color="#8ec5ff",           # 主色调
    secondary_color="#f4effb",       # 辅助色  
    theme_gradient=["#f4effb", "#8ec5ff"],  # 渐变配色
    site_name="我的数据库系统",       # 站点名称
    admin_url="https://admin.example.com",  # 管理链接
    
    # 邮件内容
    backup_type="database",
    backup_info={...}
)
```

### 3.5 实用工具函数

```python
from scripts.email.async_email import get_email_queue_stats

# 获取发送统计
stats = get_email_queue_stats()
print(f"已发送: {stats['sent_count']}, 失败: {stats['failed_count']}")

# 程序退出时自动清理
from scripts.email.async_email import shutdown_async_email_sender
shutdown_async_email_sender()
```


---

## 4. 数据库的备份
### 4.1 导入
```python
from scripts.database.backup import (
    backup_single_database,
    backup_all_databases,
    cleanup_old_backups
)
```

### 4.2 备份单个数据库
```python
# 假设备份指定数据库 mydb，压缩备份文件，并返回字典信息
summary = backup_single_database(
    database="mydb",
    compress=True,
    config_path=None,  # 使用默认 config.yaml
    as_json=True       # 返回字典形式
)
```

### 4.3 备份所有数据库
```python
# 备份配置文件中所有数据库，并返回详细信息
summary = backup_all_databases(
    compress=True,
    config_path=None,  # 使用默认 config.yaml
    as_json=True
)
```

### 4.4 清理旧备份
```python
# 清理旧备份，保留最近 7 天，保留每个数据库最近 10 个备份
result = cleanup_old_backups(
    keep_days=7,
    keep_count=10,
    config_path=None,
    as_json=True
)
```

---

## 5. 数据库状态与监控
### 5.1 导入
```python
from scripts.database.mysql_monitor import MySQLMonitor
```
### 5.2 1. MySQL 状态
显示 MySQL 服务器的基本状态信息，如运行时间、当前连接数和最大连接数。
```python
monitor = MySQLMonitor()
status = monitor.monitor_status(as_json=True)
```
### 5.3 2. 数据库大小
获取所有非系统数据库的大小（单位 MB），支持字典输出和 Rich 表格输出。
```python
db_sizes = monitor.monitor_database_sizes(as_json=True)
```

### 5.4 3. 表行数统计
统计在 config 配置下的每个数据库下所有表的行数。
```python
table_rows = monitor.monitor_table_rows(as_json=True)
```

### 5.5 4. 表结构统计
获取在 config 配置下的数据库表的字段信息，包括字段名、类型、是否允许 NULL、主键、默认值和额外信息。
```python
table_struct = monitor.monitor_table_structure(as_json=True)
```

### 5.6 快捷方法：一次性运行全部监控
run_all 方法会依次运行上述四个模块，并输出日志和 Rich 表格。
```python
monitor.run_all(as_json=False)
```

---

## 6. 系统监控工具
### 6.1 导入方法
```python
from scripts.monitor.system_monitor import SystemMonitor
# 实例化
monitor = SystemMonitor()
```

### 6.2 获取系统信息
#### 6.2.1 系统信息摘要
```python
summary = monitor.get_system_summary(as_json=False)
```
#### 6.2.2 系统详细信息
```python
detailed_info = monitor.get_system_detailed(as_json=False)
```

### 6.3 CPU 信息
```python
cpu_info = monitor.get_cpu_info(as_json=False)
```

### 6.4 内存信息
```python
memory_info = monitor.get_memory_info(as_json=False)
```

### 6.5 磁盘信息
```python
disk_info = monitor.get_disk_info(as_json=False)
```

### 6.6 GPU 信息
```python
gpu_info = monitor.get_gpu_info(as_json=False)
```

### 6.7 系统运行时间
```python
uptime_info = monitor.get_uptime(as_json=False)
```