# ---------- 基础 ----------

.PHONY: sync dev debug help

# 开发服务器端口：8080 被本机 Nacos 占用
PORT ?= 8088
# 前端开发服务器端口
WEB_PORT ?= 5173

help:
	@echo "my-rag 可用命令："
	@echo "  依赖：sync / dev / debug / web-install / dev-web / web-build"
	@echo "  容器：docker-up / docker-down / docker-reset / docker-logs / docker-ps"
	@echo "  数据库：db-init / db-reset / db-migrate / db-upgrade / db-current / db-check"
	@echo "  向量库：milvus-init / milvus-status / milvus-reset"
	@echo "  知识库：ingest / ingest-dir / reindex / reindex-all / search"
	@echo "  测试：test / test-unit / test-integration / test-pg / test-milvus / test-e2e"
	@echo "  其他：typecheck / smoke"

# 必须带 --all-packages：裸 `uv sync` 只同步根项目自身的依赖，
# 会把 apps/api 的依赖（fastapi/alembic/...）当成多余包卸载掉
sync:
	uv sync --all-packages

dev:
	uv run --package api fastapi dev apps/api/app/main.py --port $(PORT)

debug:
	uv run --package api python -m debugpy --listen 0.0.0.0:5678 --wait-for-client -m fastapi dev apps/api/app/main.py --port $(PORT)

# ---------- 前端（独立的 pnpm 工程，不属于 uv workspace）----------

.PHONY: web-install dev-web web-build web-preview

web-install:
	cd apps/web && pnpm install

dev-web:
	cd apps/web && pnpm dev --port $(WEB_PORT)

web-build:
	cd apps/web && pnpm build

web-preview:
	cd apps/web && pnpm preview --port $(WEB_PORT)

# ---------- 容器（PostgreSQL + Milvus）----------

.PHONY: docker-up docker-down docker-reset docker-logs docker-ps

docker-up:
	docker compose up -d

docker-down:
	docker compose down

# 连数据卷一起清：Milvus 集合与 PG 数据都会消失
docker-reset:
	docker compose down -v
	docker compose up -d

docker-logs:
	docker compose logs -f

docker-ps:
	docker compose ps

# ---------- 数据库 ----------

.PHONY: db-init db-reset db-migrate db-upgrade db-downgrade db-current db-history db-show db-check db-sql db-stamp

db-init:
	uv run --package api python apps/api/scripts/init_db.py

# 重建数据库会重置 PG 序列 → chunk.id 会被复用 →
# 必须连带 milvus-reset，否则 Milvus 里的旧向量会覆盖新向量
db-reset:
	uv run --package api python apps/api/scripts/init_db.py --drop
	$(MAKE) milvus-reset

db-migrate:
	uv run --package api alembic -c apps/api/alembic.ini revision --autogenerate -m "$(message)"

db-upgrade:
	uv run --package api alembic -c apps/api/alembic.ini upgrade $(or $(version),head)

db-downgrade:
	uv run --package api alembic -c apps/api/alembic.ini downgrade $(or $(version),-1)

db-current:
	uv run --package api alembic -c apps/api/alembic.ini current

db-history:
	uv run --package api alembic -c apps/api/alembic.ini history

db-show:
	uv run --package api alembic -c apps/api/alembic.ini show $(version)

db-check:
	uv run --package api alembic -c apps/api/alembic.ini check

db-sql:
	uv run --package api alembic -c apps/api/alembic.ini upgrade $(or $(version),head) --sql

db-stamp:
	uv run --package api alembic -c apps/api/alembic.ini stamp $(version)

# ---------- 向量库 ----------

.PHONY: milvus-init milvus-status milvus-reset milvus-drop

# 幂等：集合已存在时只校验维度并补建索引，不会报错
milvus-init:
	uv run --package api python apps/api/scripts/milvus_init.py

milvus-status:
	uv run --package api python apps/api/scripts/milvus_init.py --status

# 删集合并按当前维度重建。PG 序列重置（db-reset）或换 embedding 模型后必须执行
milvus-reset:
	uv run --package api python apps/api/scripts/milvus_init.py --reset

milvus-drop:
	uv run --package api python apps/api/scripts/milvus_init.py --drop

# ---------- 知识库 ----------

.PHONY: ingest ingest-dir reindex reindex-all search

# 摄入单个文件：make ingest file=docs/部署手册.md
ingest:
	uv run --package api python -m app.cli ingest "$(file)"

# 摄入整个目录（递归）：make ingest-dir dir=docs
ingest-dir:
	uv run --package api python -m app.cli ingest --dir "$(dir)"

# 重建单个文档的向量：make reindex doc=1
reindex:
	uv run --package api python -m app.cli reindex --doc "$(doc)"

# 全量重建（换 embedding 模型后用）
reindex-all:
	uv run --package api python -m app.cli reindex --all

# 命令行检索（不调用大模型）：make search query="怎么安装依赖"
search:
	uv run --package api python -m app.cli search "$(query)"

# ---------- 测试 ----------

.PHONY: test test-verbose test-unit test-integration test-pg test-milvus test-e2e test-k test-file test-cov test-cov-html

test:
	uv run --package api pytest

test-verbose:
	uv run --package api pytest -v

test-unit:
	uv run --package api pytest apps/api/test/unit packages/rag-core/test/unit

test-integration:
	uv run --package api pytest apps/api/test/integration

# 只跑需要 PostgreSQL 的用例；连不上库直接失败（CI 用）
test-pg:
	REQUIRE_PG=1 uv run --package api pytest -m postgres

# 只跑需要 Milvus 的用例
test-milvus:
	REQUIRE_MILVUS=1 uv run --package api pytest -m milvus

test-e2e:
	uv run --package api pytest apps/api/test/e2e

test-k:
	uv run --package api pytest -k "$(keyword)"

test-file:
	uv run --package api pytest "$(file)"

test-cov:
	uv run --package api pytest --cov=app --cov-report=term-missing

test-cov-html:
	uv run --package api pytest --cov=app --cov-report=html

# ---------- 类型检查 ----------

.PHONY: typecheck

typecheck:
	uv run --package api mypy apps/api/app packages/rag-core/src

# ---------- 冒烟 ----------

.PHONY: smoke

# 端到端冒烟：需要 docker-up 之后执行
smoke:
	uv run --package api python apps/api/scripts/smoke.py
