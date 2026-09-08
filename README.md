# 数据库实例管理系统 (DB Instance Management System)

`基于 Python 3.12 + Django 6.1 + DRF + Celery + PostgreSQL + Redis 的数据库实例管理平台。`

## 核心需求

1. 实例 / 集群 / 部门模型与 **CRUD API**
2. **TCP 端口可达性探测** API（Celery 异步任务）
3. 实例账号密码 **每 12 小时随机轮换**，Fernet 加密落库、永不回显
4. **每日 00:00** 按部门/集群维度统计实例数量并入库
5. **请求耗时中间件**（响应头 `X-Request-Duration-Ms` + 慢请求告警日志）

## 技术栈

`Python>=3.12` · `Django 6.1.1` · `DRF` · `Celery 5.4+` · `PostgreSQL 15+` · `Redis 7+` · `uv`

## 快速开始

```powershell
uv sync 
copy .env.example .env # 生成 Fernet 密钥并填入 ENCRYPTION_KEY 
uv run python manage.py migrate 
uv run python manage.py seed_demo # 演示数据 + 当日统计 
uv run python manage.py createsuperuser 
uv run python manage.py runserver
```

## 访问入口

| 地址 | 说明 |
|---|---|
| http://127.0.0.1:8000/dashboard/ | 轻量控制台（需登录）：统计卡片、最近实例/统计、端口探测 |
| http://127.0.0.1:8000/api/schema/swagger-ui/ | Swagger UI 接口文档（Bearer Token 调试） |
| http://127.0.0.1:8000/api/schema/redoc/ | ReDoc 文档 |
| http://127.0.0.1:8000/api/ | DRF API 根 |
| http://127.0.0.1:8000/admin/ | Django Admin |
| http://127.0.0.1:8000/metrics/ | Prometheus 指标（请求量/延迟直方图等） |
| http://127.0.0.1:5555 | Flower：Celery 任务/周期任务可视化 |

## 测试

```powershell
# 单元 + 接口测试（默认使用 PostgreSQL test 库）
uv run python manage.py test app -v 2

# 免外部依赖（SQLite）测试
uv run python manage.py test app --settings=dbinstancemanagement.settings_test -v 2

# 覆盖率报告（htmlcov/index.html）
uv run coverage run --rcfile=.coveragerc manage.py test app -v 2 
uv run coverage report
```
`覆盖：模型加解密/轮换、TCP 探测工具、Celery 任务（仅 active 轮换、统计幂等）、API CRUD/JWT/探测、耗时中间件。`

## Celery 定时任务

Beat 静态调度（settings 内 `CELERY_BEAT_SCHEDULE`）：

| 任务 | 调度 | 说明 |
|---|---|---|
| `app.tasks.rotate_instance_passwords` | 每 12 小时 | 随机轮换 active 实例密码并加密 |
| `app.tasks.generate_daily_instance_stats` | 每日 00:00 | 按部门/集群维度统计写入 |

启动（或直接运行 `scripts/start_all.ps1`）：
```powershell
uv run celery -A dbinstancemanagement worker -l info -P threads
uv run celery -A dbinstancemanagement beat -l info
uv run celery -A dbinstancemanagement flower --port=5555
```

手动验证（无需 Worker）：
```powershell
uv run python manage.py rotate_passwords
uv run python manage.py generate_daily_stats --date 2026-09-08
```

## 并发压测

```powershell
# 准备压测账号
uv run python manage.py shell -c "from django.contrib.auth import get_user_model; U=get_user_model(); U.objects.get_or_create(username='loadtest', defaults={'password':''}); u=U.objects.get(username='loadtest'); u.set_password('Load@12345'); u.save()"

# 运行 waitress + locust
uv run waitress-serve --listen=127.0.0.1:8000 --threads=8 dbinstancemanagement.wsgi:application
uv run locust -f locustfile.py --host http://127.0.0.1:8000 --web-port 8089
```

- Web UI：http://127.0.0.1:8089 （Users/Spawn rate：建议 20~50 起步）
- 关注指标：RPS、中位/P95 响应时间、错误率；结合 `logs/access.log` 与慢请求日志核对
- `POST /api/instances/probe/` 场景需要 Redis/Worker 在运行

## 日志与观测

统一写入 `logs/`（自动创建、按天轮转、保留 7 天）：

| 文件 | 内容 |
|---|---|
| `logs/access.log` | 每条请求：method path status 耗时 user |
| `logs/app.log` | 业务日志 |
| `logs/django.log` | Django 框架日志 |
| `logs/celery.log` | Celery 日志（worker 另有 celery-worker.log） |

指标端点 `/metrics/` 提供请求计数、延迟直方图等 Prometheus 指标，可对接 Grafana。

## 项目结构
```text
## 项目结构

```text
├── app/                          # 业务模块
│   ├── models/                   # 数据模型
│   ├── serializers/              # 序列化器
│   ├── views/                    # 视图层
│   ├── tasks/                    # Celery 异步任务
│   ├── middleware/               # 中间件
│   └── utils/                    # 工具函数
├── app/management/commands/      # Django 自定义管理命令
│   ├── seed_demo                 # 演示数据填充
│   ├── rotate_passwords          # 密码轮换
│   └── generate_daily_stats      # 每日统计生成
├── dbinstancemanagement/         # 工程配置模块
│   ├── settings/                 # Django 配置
│   ├── celery/                   # Celery 配置
│   └── urls/                     # URL 路由配置
├── templates/dashboard/          # 控制台前端页面模板
├── scripts/                      # 运维脚本
│   ├── start_all.ps1             # 一键启动脚本
│   └── run_load.ps1              # 负载测试执行脚本
└── locustfile.py                 # Locust 压测场景定义
```
