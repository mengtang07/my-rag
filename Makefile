# Makefile

.PHONY: sync dev debug test test-verbose test-unit test-integration test-pg \
        test-e2e test-k test-file test-cov test-cov-html \
        db-init db-reset db-migrate db-upgrade db-downgrade \
        db-current db-history db-show db-check db-sql db-stamp

# 开发服务器端口：8080 被本机 Nacos 容器占用，默认改用 8088
# 需要换端口时：make dev PORT=9001
PORT ?= 8088

# ---------- 环境 ----------

# 安装依赖
# 必须带 --all-packages：裸 `uv sync` 只同步根项目自身的依赖，
# 会把 apps/web-service 的依赖（fastapi/alembic/...）当成多余包卸载掉
sync:
	uv sync --all-packages

# ---------- 服务 ----------

# 启动开发服务器（热重载），PORT=xxx 可指定端口
dev:
	export PYTHONDONTWRITEBYTECODE=1; \
	uv run --package web-service fastapi dev apps/web-service/app/main.py --port $(PORT)

# 调试模式（等待 debugpy 连接）
debug:
	export PYTHONDONTWRITEBYTECODE=1; \
	uv run --package web-service python -m debugpy --listen 0.0.0.0:5678 --wait-for-client -m fastapi dev apps/web-service/app/main.py --port 8000

# ---------- 测试 ----------

# 运行全部测试（同步用例、异步用例一起跑）
test:
	uv run --package web-service pytest

# 详细模式：逐条打印用例名
test-verbose:
	uv run --package web-service pytest -v

# 只跑单元测试
test-unit:
	uv run --package web-service pytest apps/web-service/test/unit

# 只跑集成测试（PostgreSQL 用例连不上库会自动跳过）
test-integration:
	uv run --package web-service pytest apps/web-service/test/integration

# 只跑需要 PostgreSQL 的用例：连不上库直接失败，适合 CI
# 测试库默认 tm_db_test，会在第一次运行时自动创建并执行迁移
test-pg:
	REQUIRE_PG=1 uv run --package web-service pytest -m postgres

# 只跑端到端测试：真实起一个服务进程，用 httpx 发真实 HTTP 请求
# 需要 PostgreSQL（连不上会自动跳过）；测试库为 tm_db_e2e_test
test-e2e:
	uv run --package web-service pytest apps/web-service/test/e2e

# 按关键字筛选用例：make test-k keyword=product
test-k:
	uv run --package web-service pytest -k "$(keyword)"

# 跑单个文件：make test-file file=apps/web-service/test/unit/test_model_orm.py
test-file:
	uv run --package web-service pytest "$(file)"

# 覆盖率报告（终端输出，缺失行一目了然）
test-cov:
	uv run --package web-service pytest --cov=app --cov-report=term-missing

# 覆盖率报告（HTML，输出到 htmlcov/）
test-cov-html:
	uv run --package web-service pytest --cov=app --cov-report=html

# ---------- 数据库迁移（Alembic） ----------

# 建库 + 跑迁移
db-init:
	uv run --package web-service python apps/web-service/scripts/init_db.py

# 删库重建 + 跑迁移（会清空数据）
db-reset:
	uv run --package web-service python apps/web-service/scripts/init_db.py --drop

# 生成迁移脚本
db-migrate:
	uv run --package web-service alembic -c apps/web-service/alembic.ini revision --autogenerate -m "$(message)"

# 执行迁移，升级到最新版本；version=xxx 可升到指定版本
db-upgrade:
	uv run --package web-service alembic -c apps/web-service/alembic.ini upgrade $(or $(version),head)

# 回滚一步；version=xxx 可回滚到指定版本
db-downgrade:
	uv run --package web-service alembic -c apps/web-service/alembic.ini downgrade $(or $(version),-1)

# 查看数据库当前停留在哪个迁移版本
db-current:
	uv run --package web-service alembic -c apps/web-service/alembic.ini current

# 查看全部迁移历史
db-history:
	uv run --package web-service alembic -c apps/web-service/alembic.ini history

# 查看某个迁移版本脚本的内容
db-show:
	uv run --package web-service alembic -c apps/web-service/alembic.ini show $(version)

# 检查模型与数据库结构是否一致（改了模型忘了生成脚本时会报错）
db-check:
	uv run --package web-service alembic -c apps/web-service/alembic.ini check

# 只生成 SQL 不执行（离线模式，不连数据库）
db-sql:
	uv run --package web-service alembic -c apps/web-service/alembic.ini upgrade $(or $(version),head) --sql

# 只改版本号不执行迁移
db-stamp:
	uv run --package web-service alembic -c apps/web-service/alembic.ini stamp $(version)
