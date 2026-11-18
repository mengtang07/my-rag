# 渡一 Python 全栈框架

基于 `FastAPI` 的 Web 服务工程骨架，采用 `uv` workspace 管理，可直接用于新项目或作为课程配套工程。

## 目录结构

```
my_fastapi/
├── pyproject.toml              # workspace 根配置（依赖组、pytest、mypy）
├── Makefile                    # 常用命令快捷入口
├── .env.example                # 环境变量样例，复制为 .env 后生效
├── .env.test.example           # 测试环境变量样例，复制为 .env.test 后生效
├── .python-version             # 统一的 Python 版本
├── apps/
│   └── web-service/            # Web 服务应用
│       ├── pyproject.toml
│       ├── alembic.ini         # 数据库迁移配置
│       ├── app/
│       │   ├── main.py         # 应用入口：创建 app、注册中间件与异常处理器
│       │   ├── api/            # 接口层：只做参数接收与结果返回
│       │   │   ├── health.py   #   健康检查
│       │   │   ├── products.py #   商品接口
│       │   │   ├── categories.py
│       │   │   ├── skus.py
│       │   │   └── upload.py   #   文件上传接口（阿里云 OSS 直传）
│       │   ├── schema/         # 数据校验层：pydantic 模型
│       │   │   ├── product.py
│       │   │   ├── category.py
│       │   │   ├── sku.py
│       │   │   └── upload.py   #   上传入参/出参
│       │   ├── service/        # 业务逻辑层：真正的业务处理
│       │   │   ├── base.py
│       │   │   ├── product_service.py
│       │   │   ├── category_service.py
│       │   │   ├── sku_service.py
│       │   │   └── upload_service.py #  上传凭证签发、文件查询与删除
│       │   ├── model/          # ORM 层：SQLAlchemy 模型（表结构的唯一来源）
│       │   │   ├── base.py     #   基类与 Mixin
│       │   │   ├── category.py #   分类（与商品多对多）
│       │   │   ├── product.py  #   商品 SPU（与 SKU 一对多）
│       │   │   ├── sku.py      #   商品规格 SKU
│       │   │   └── association/ #  多对多关联表（中间表）
│       │   │       └── product_category.py
│       │   ├── core/           # 基础设施层
│       │   │   ├── config.py   #   配置管理（pydantic-settings）
│       │   │   ├── database.py #   引擎与会话管理
│       │   │   ├── openapi.py  #   OpenAPI 文档定制
│       │   │   └── middleware/ #   中间件
│       │   └── exception/      # 异常定义与统一异常处理器
│       ├── migrations/         # Alembic 迁移脚本
│       ├── scripts/            # 运维脚本
│       │   └── init_db.py      #   初始化数据库（建库 + 跑迁移）
│       └── test/               # 测试
│           ├── unit/           #   单元测试（内存 SQLite，不依赖真实数据库）
│           ├── integration/    #   集成测试（进程内，ASGI）
│           └── e2e/            #   端到端测试（真实起服务进程）
└── packages/
    └── duyi-utils/             # 共享包：阿里云 OSS 上传等通用能力
        ├── pyproject.toml
        ├── src/duyi_utils/
        │   ├── shared/         #   文件后缀、MIME 等小工具
        │   └── upload/         #   OSS 上传器、目录策略
        └── test/               #   共享包自己的测试
```

## 快速开始

命令可以在 `my_fastapi` 目录下执行，也可以在仓库根目录执行（根目录的 Makefile 会自动转发）。

```shell
# 1. 安装依赖
make sync

# 2. 准备配置
cp my_fastapi/.env.example my_fastapi/.env

# 3. 初始化数据库（库不存在则创建，并执行迁移）
make db-init

# 4. 启动服务
make dev
```

默认端口是 `8088`（本机 `8080` 已被 Nacos 占用），可以临时改端口：

```shell
make dev PORT=9001
```

启动后访问：

- http://localhost:8088/health —— 健康检查
- http://localhost:8088/docs —— 接口文档
- http://localhost:8088/redoc —— 接口文档（ReDoc）

## 常用命令

| 命令 | 说明 |
| --- | --- |
| `make sync` | 安装依赖 |
| `make dev` | 启动开发服务器（热重载），`PORT=xxx` 可指定端口 |
| `make debug` | 调试模式（等待 debugpy 连接） |
| `make test` | 运行全部测试（同步 + 异步用例） |
| `make test-verbose` | 详细模式，逐条打印用例名 |
| `make test-unit` | 运行单元测试 |
| `make test-integration` | 运行集成测试（PostgreSQL 用例连不上库会自动跳过） |
| `make test-pg` | 只跑需要 PostgreSQL 的用例；连不上库直接失败（CI 用） |
| `make test-e2e` | 只跑端到端测试（真实起服务进程，用独立测试库） |
| `make test-k keyword=product` | 按关键字筛选用例 |
| `make test-file file=apps/web-service/test/unit/test_schema.py` | 只跑单个测试文件 |
| `make test-cov` | 覆盖率报告（终端输出，缺失行一目了然） |
| `make test-cov-html` | 覆盖率报告（HTML，输出到 `htmlcov/`） |

### 测试

测试配置写在 `pyproject.toml` 的 `[tool.pytest.ini_options]`：

```toml
asyncio_mode = "auto"
```

`auto` 模式下，`pytest-asyncio` 自动接管所有 `async def` 用例和异步夹具，
而普通 `def` 用例仍由 pytest 原生同步执行 —— **同步、异步用例共用这一套配置**，
写同步用例不需要任何额外标注，写异步用例也不需要手写 `@pytest.mark.asyncio`。

| 目录 | 用途 | 例子 |
| --- | --- | --- |
| `test/unit/` | 单元测试，屏蔽外部依赖 | `test_schema.py`（纯同步）、`test_model_orm.py`（异步 + 内存 SQLite）、`test_upload_service.py`（假 uploader，不联网） |
| `test/integration/` | 集成测试，多模块协作 | `test_api_health.py`（内存 SQLite）、`test_api_upload.py`（内存 SQLite）、`test_api_postgres.py`（真实 PostgreSQL） |
| `test/e2e/` | 端到端测试，真实起服务进程 | 起独立进程跑 `fastapi dev`，用 httpx 发真实 HTTP 请求 |

#### 两种数据库夹具

**内存 SQLite（默认，零依赖）**

大部分用例走 `test/conftest.py` 里的 `db_session` 夹具 —— 内存 SQLite + `aiosqlite`，
表结构由 `create_all` 现建，不连真实数据库，跑一次几毫秒：
跑测试前**不需要**执行 `make db-init`，也不需要本机装 PostgreSQL。

测试配置在导入应用之前就被固定（`ENVIRONMENT=test`、`WEB_CORS_*` 等），
不受本机 `.env` 影响；数据库名还会被强制改写成 `tm_db_test`，
即使有代码绕过夹具直接调用 `get_db`，也连接不到开发库。

**真实 PostgreSQL（`postgres` 标记）**

迁移脚本、数据库级约束/级联、`server_default`、JSON 字段这些 SQLite 测不了的内容，
放在 `test/integration/` 下并标上 `postgres`，夹具见 `test/integration/conftest.py`：

- 使用独立测试库，默认 `tm_db_test`（可用 `TEST_DB_NAME` 覆盖，必须以 `_test` 结尾）；
- 库不存在会自动创建，并执行 `alembic upgrade head`，不需要手动准备；
- 每个用例跑在事务里，结束后回滚，用例之间互不影响；
- 连不上 PostgreSQL 时自动跳过，`make test` 在没有数据库的机器上仍能全绿；
  加 `REQUIRE_PG=1`（即 `make test-pg`）则改为失败，避免 CI 静默跳过。

迁移测试在一次性数据库上执行 `upgrade head` / `alembic check` / `downgrade base`，
结束后删除该库，不会碰开发库 `tm_db`。

### 数据库迁移

| 命令 | 说明 |
| --- | --- |
| `make db-init` | 初始化数据库：库不存在则创建，并执行迁移 |
| `make db-reset` | 重建数据库：先删库再建库并迁移（会清空数据） |
| `make db-migrate message="add user table"` | 根据模型变更生成迁移脚本 |
| `make db-upgrade` | 执行迁移，升级到最新版本；`version=xxx` 可升到指定版本 |
| `make db-downgrade` | 回滚一步；`version=xxx` 可回滚到指定版本 |
| `make db-current` | 查看数据库当前停留在哪个迁移版本 |
| `make db-history` | 查看全部迁移历史 |
| `make db-show version=xxx` | 查看某个迁移版本脚本的内容 |
| `make db-check` | 检查模型与数据库结构是否一致（改了模型忘了生成脚本时会报错） |
| `make db-sql > migrate.sql` | 只生成 SQL 不执行（离线模式，不连数据库） |
| `make db-stamp version=xxx` | 只把数据库标记为某个版本，不执行迁移 |

日常开发流程：**改模型 → `make db-migrate` → 审查脚本 → `make db-upgrade`**。

迁移脚本本身也有测试覆盖：`make test-pg` 会在一次性数据库上执行
`upgrade head`、`alembic check`（模型与迁移不一致会失败）、`downgrade base`
往返，并检查模型里的 `server_default` 是否真的落到了数据库上。

## 框架约定

### 分层

```
api → service → model → database
```

- `api`：只负责接收参数、调用 `service`、返回结果，不写业务逻辑
- `service`：业务逻辑的唯一归属地，操作数据库会话
- `model`：ORM 模型，表结构的唯一定义来源
- `schema`：出入参的校验规则，与模型解耦

### 数据库迁移

表结构定义在 `model`，表结构变更记录在 `migrations`，两者必须始终一致：

- 建表只走迁移：`make db-init` / `make db-upgrade`，**不要在代码里调 `create_all`**（它绕过版本管理，会让迁移状态和真实表结构对不上）
- 改完模型必须 `make db-migrate message="描述"` 生成迁移脚本，审查后再 `make db-upgrade` 执行
- 迁移脚本一旦执行过就视为常量，不再修改或删除
- `make db-check` 可随时校验模型与数据库结构是否一致
- 测试用的内存 SQLite 不受此约束，夹具自行建表

### 统一响应

所有 `/api/` 开头的接口，响应体统一为：

```json
{
  "code": "0",
  "data": {},
  "message": "success"
}
```

`code` 为 `0` 表示成功，非 `0` 为业务错误码（详见 `/docs` 中的错误码说明）。

### 统一异常

在业务代码中直接抛出业务异常即可，无需自己拼装响应：

```python
from app.exception import NotFoundException

raise NotFoundException(message="商品不存在")
```

全局异常处理器会把它转换成 `404` + 业务错误码 `404001`。

### 文件上传（阿里云 OSS）

采用**前端直传**模式：应用只签发 OSS 的 PostObject 上传凭证，文件由浏览器直接发到
OSS，不经过应用服务器，因此不受应用带宽限制。

底层实现在共享包 `packages/duyi-utils`（`AliyunOSSUploader`），
应用侧只做配置翻译和异常翻译：`app/service/upload_service.py`。

| 接口 | 说明 |
| --- | --- |
| `POST /api/upload/credentials` | 申请上传凭证，入参 `{"filename": "photo.png", "file_size": 1024}` |
| `GET /api/upload/object/{key}` | 查询文件是否存在 |
| `DELETE /api/upload/object/{key}` | 删除文件 |

凭证字段：`host`（POST 目标地址）、`access_id`、`policy`、`signature`、`key`、
`content_type`。前端拿到后用 `multipart/form-data` 直接 POST 到 `host`，
表单字段依次为 `OSSAccessKeyId` / `policy` / `signature` / `key` / `Content-Type`，
文件本身放在 `file` 字段里。

```javascript
const { host, access_id, policy, signature, key, content_type } = cred;
const form = new FormData();
form.append("OSSAccessKeyId", access_id);
form.append("policy", policy);
form.append("signature", signature);
form.append("key", key);
form.append("Content-Type", content_type);
form.append("file", file);
await fetch(host, { method: "POST", body: form });
```

`policy` 里锁死了 `key`、`Content-Type` 和文件大小范围（`content-length-range`），
拿到的凭证换 key、换类型或超大小上传都会被 OSS 拒绝。

配置项（`.env`）：

| 变量 | 说明 |
| --- | --- |
| `OSS_ACCESS_KEY_ID` / `OSS_ACCESS_KEY_SECRET` | 访问密钥 |
| `OSS_BUCKET_NAME` / `OSS_ENDPOINT` | Bucket 与地域 Endpoint |
| `OSS_EXPIRE_SECONDS` | 凭证有效期，默认 3600 秒 |
| `OSS_MIME_TYPES` | 允许上传的 MIME 类型，逗号分隔；留空不限制 |
| `OSS_DIR_STRATEGY` | `date`（`uploads/YYYY/MM/DD/`）或 `flat`（`uploads/`） |

配置缺失时接口返回业务错误码 `422002`（而不是 500），提示缺哪个配置项。

### 配置

配置集中在 `app/core/config.py`，按模块划分前缀：

| 前缀 | 配置类 | 说明 |
| --- | --- | --- |
| 无 | `CommonSettings` | 环境标识 |
| `WEB_` | `WebSettings` | 应用名、接口前缀、跨域 |
| `DB_` | `DBSettings` | 数据库连接 |
| `OSS_` | `OSSSettings` | 阿里云 OSS（文件上传） |
| `LOG_` | `LogSettings` | 日志级别 |

### 类型标注

所有代码必须带类型标注，`mypy` 检查：

```shell
uv run mypy apps/web-service/app
```
