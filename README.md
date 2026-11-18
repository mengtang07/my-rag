# my-rag：个人知识库 RAG 系统

把一堆文档灌进去，用自然语言提问，拿到**带引用来源**的答案。

- **后端**：FastAPI + PostgreSQL（文档元数据与正文）+ Milvus（向量）+ LiteLLM 网关（对话 / 向量化 / 重排）
- **前端**：Vite + React 单页应用（文档管理 + 流式问答 + 来源面板）
- **工具链**：uv workspace（Python）+ pnpm（前端）

## 目录结构

```
my-rag/
├── pyproject.toml            # uv workspace 根（依赖组、pytest、mypy）
├── Makefile                  # 常用命令快捷入口
├── docker-compose.yml        # PostgreSQL + Milvus（etcd + minio）
├── README.md                 # 本文件
├── .env.example              # 环境变量样例，复制为 .env 后生效
├── .env.test.example         # 测试环境变量样例
├── .python-version           # 统一的 Python 版本
├── docker/
│   ├── postgres/init/        # 首次初始化时执行的 SQL（pg_trgm 扩展）
│   └── milvus-init/          # 一次性容器：幂等建集合 + 建索引 + 加载
├── apps/
│   ├── api/                  # ---------- Python 后端（uv 成员） ----------
│   │   ├── pyproject.toml  alembic.ini  README.md
│   │   ├── app/
│   │   │   ├── main.py       # 应用入口：创建 app、注册中间件与异常处理器
│   │   │   ├── cli.py        # 命令行：ingest / reindex / search / dingtalk
│   │   │   ├── api/          # 接口层：只做参数接收与结果返回
│   │   │   │   ├── health.py #   健康检查 + 系统状态
│   │   │   │   ├── documents.py # 文档上传/入库/列表/详情/切块/重建/删除
│   │   │   │   ├── search.py #   纯向量检索（不调大模型）
│   │   │   │   ├── chat.py  #   流式问答（SSE）与非流式问答
│   │   │   │   └── conversations.py # 会话与消息
│   │   │   ├── schema/       # 数据校验层：pydantic 模型
│   │   │   ├── service/      # 业务逻辑层：真正的业务处理
│   │   │   │   ├── base.py
│   │   │   │   ├── document_service.py
│   │   │   │   ├── ingest_service.py    # 解析→切块→向量化→落库→建索引
│   │   │   │   ├── retrieval_service.py # 向量召回→回表→上下文组装
│   │   │   │   ├── chat_service.py      # 提示词、token 预算、流式事件
│   │   │   │   └── conversation_service.py
│   │   │   ├── model/        # ORM 层：SQLAlchemy 模型（表结构的唯一来源）
│   │   │   │   ├── base.py   #   基类与 Mixin
│   │   │   │   ├── document.py
│   │   │   │   ├── chunk.py
│   │   │   │   ├── conversation.py
│   │   │   │   └── message.py
│   │   │   ├── core/         # 基础设施层
│   │   │   │   ├── config.py #   配置管理（pydantic-settings）
│   │   │   │   ├── database.py # 引擎与会话管理
│   │   │   │   ├── llm.py    #   LiteLLM 网关客户端
│   │   │   │   ├── milvus_schema.py # 集合 schema 与幂等建集合
│   │   │   │   ├── vector_store.py  # Milvus 读写封装
│   │   │   │   ├── openapi.py #  OpenAPI 文档定制
│   │   │   │   ├── prompt.py #   系统提示词（必须字面稳定）
│   │   │   │   └── middleware/ # 中间件
│   │   │   └── exception/    # 异常定义与统一异常处理器
│   │   ├── migrations/       # Alembic 迁移脚本
│   │   ├── scripts/          # 运维脚本
│   │   │   ├── init_db.py    #   初始化数据库（建库 + 跑迁移）
│   │   │   ├── milvus_init.py #  建集合 / 查状态 / 重建
│   │   │   └── smoke.py      #   端到端冒烟断言
│   │   └── test/             # 测试
│   │       ├── unit/         #   单元测试（零外部依赖）
│   │       ├── integration/  #   集成测试（真 PG / 真 Milvus）
│   │       └── e2e/          #   端到端测试（真实起服务进程）
│   └── web/                  # ---------- 前端（pnpm，独立工具链） ----------
│       ├── package.json  vite.config.ts  index.html
│       └── src/
│           ├── api/          #   请求封装与 SSE 客户端
│           ├── components/   #   列表、上传、对话、消息、来源卡片
│           ├── hooks/        #   useDocuments / useChat
│           └── types/api.ts  #   与后端 schema 对应的类型
└── packages/
    └── rag-core/             # 共享包：纯 RAG 领域逻辑
        ├── src/rag_core/
        │   ├── models.py     #   Block / ParsedDocument / ChunkDraft
        │   ├── parsing/      #   markdown / pdf / docx / html / txt 解析
        │   ├── chunking/     #   结构感知切块
        │   ├── text/         #   CJK 感知的 token 估算
        │   └── dingding/     #   钉钉知识库接入
        │       ├── client.py     #     开放平台接口的异步客户端
        │       ├── models.py     #     树结构模型（DingNode / DingBlock / …）
        │       ├── tree.py       #     树构建：节点解析、标题树、遍历
        │       └── exceptions.py #     DingTalkError
        └── test/unit/
```

## 快速开始

```shell
# 1. 装依赖（Python 侧）
make sync

# 2. 装前端依赖
make web-install

# 3. 准备配置
cp .env.example .env
#    填 LLM_API_KEY（LiteLLM 网关的密钥）

# 4. 起依赖容器（PostgreSQL + Milvus）
make docker-up

# 5. 建库 + 建集合
make db-init
make milvus-init

# 6. 启动
make dev          # 后端 http://localhost:8088
make dev-web      # 前端 http://localhost:5173
```

打开 http://localhost:5173 ，上传一份 markdown，然后提问。

冒烟验证（需要 `make dev` 已经在跑）：

```shell
make smoke
```

## 常用命令

| 命令 | 说明 |
| --- | --- |
| `make sync` | 安装 Python 依赖 |
| `make dev` | 启动后端（热重载），`PORT=xxx` 可指定端口 |
| `make dev-web` | 启动前端开发服务器（`/api` 代理到 8088） |
| `make web-build` | 构建前端产物到 `apps/web/dist` |
| `make docker-up` / `docker-down` | 起停 PostgreSQL + Milvus |
| `make docker-reset` | 连数据卷一起清 |
| `make db-init` / `db-reset` | 建库+迁移 / 删库重建 |
| `make db-migrate message="描述"` | 根据模型变更生成迁移脚本 |
| `make db-upgrade` / `db-downgrade` | 执行迁移 / 回滚一步 |
| `make db-check` | 检查模型与数据库结构是否一致 |
| `make milvus-init` | 幂等建集合 + 建索引 + 加载 |
| `make milvus-status` | 查看集合维度与向量条数 |
| `make milvus-reset` | 删集合并按当前维度重建 |
| `make ingest file=docs/a.md` | 摄入单个文件 |
| `make ingest-dir dir=docs` | 摄入整个目录（递归） |
| `make reindex doc=1` | 重建单个文档的向量 |
| `make reindex-all` | 全量重建（换 embedding 模型后用） |
| `make search query="怎么装"` | 命令行检索（不调大模型） |
| `make test` / `test-unit` / `test-integration` | 运行测试 |
| `make test-pg` / `test-milvus` | 需要真实 PG / Milvus，缺依赖则失败（CI 用） |
| `make test-e2e` | 端到端测试（真实起服务进程） |
| `make typecheck` | mypy 检查 |
| `make smoke` | 端到端冒烟断言 |

## 架构

### 存储分工

| 数据 | 存在哪 | 为什么 |
| --- | --- | --- |
| 文档元数据（标题、状态、sha256…） | PostgreSQL `document` 表 | 需要事务、唯一约束、分页 |
| **切块正文** | PostgreSQL `chunk` 表 | **唯一真相源**，检索命中后回表取 |
| 会话与消息 | PostgreSQL `conversation` / `message` 表 | 同上 |
| 向量 | Milvus `rag_chunks` 集合 | 专门做向量检索，支持 HNSW |

Milvus 集合里**只有向量和主键**，没有正文：

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| `pk` | INT64 主键 | = PostgreSQL 里 `chunk.id` |
| `vector` | FLOAT_VECTOR(1024) | 稠密向量 |
| `doc_id` | INT64 | = `document.id`，按文档过滤/删除用 |
| `chunk_index` | INT64 | 文档内序号 |

索引：HNSW + 余弦距离（`M=16`、`efConstruction=200`），查询 `ef=64`。

### 一致性边界

**PostgreSQL 是真相源，Milvus 是可随时重建的派生索引。**

写入顺序固定为 **PG 先 → Milvus 后 → PG 状态最后**：

1. 插入 `document`（status=`parsing`）并提交
2. 解析 → 切块 → 插入 `chunk` 行，status 改为 `indexing`，提交
3. 批量向量化 → 写入 Milvus
4. status 改为 `ready`，提交

反过来（先写 Milvus）会产生没法对齐的孤儿向量；先写 PG 的失败态则是**可恢复**的 ——
重跑 `make reindex doc=<id>` 只需要第 3、4 步。

删除顺序相反：**先删 Milvus 再删 PG**。PG 删成功而 Milvus 删失败只是留下孤儿向量（可清理）；
PG 有正文但向量没了会让检索直接漏召回，更糟。

> ⚠️ `make db-reset` 会重置 PG 序列，`chunk.id` 会被复用 → **必须连带 `make milvus-reset`**，
> 否则 Milvus 里的旧向量会覆盖新向量。Makefile 里已经成对执行了。

### 切块策略

**结构感知为主、定长兜底**，而不是纯定长窗口：

1. 解析器先按标题层级把文档切成「带标题路径的区块」
   （markdown / docx / html 能还原标题树；PDF 没结构，退化成按页切）
2. 区块正文过长时按 段落 → 句子 → 硬切 三级降到 `RAG_CHUNK_MAX_CHARS`
3. 同一区块内的相邻片段保留 `RAG_CHUNK_OVERLAP` 字符重叠（跨标题不重叠，否则语义会串）
4. 过短的片段并入同标题路径下的前一片段（跨标题不合并，引用出处会失真）
5. 入库正文前面拼上 `## 标题路径`，**前缀参与向量化** —— 检索「依赖安装」时更容易命中对应章节

定长窗口会把标题和它下面的正文切开、拦腰截断表格，结果是命中块语义不完整、引用对不上原文结构。

### 检索与生成

```
问题 → 向量化 → Milvus top_k×2 → 回表取正文 → (可选重排) → 组装上下文 → 大模型 → 流式吐字 + 引用
```

- 上下文按分数降序累加，超 `RAG_MAX_CONTEXT_TOKENS` 就停（至少保留一条）
- 历史消息按 token 预算从最旧开始丢
- 系统提示词固定在 `app/core/prompt.py`，**字面必须稳定**（将来挂 prompt cache 的前提）

## 接口一览

所有 `/api/` 开头且返回 JSON 的接口，响应体统一为：

```json
{ "code": "0", "data": {}, "message": "success" }
```

`code` 为 `0` 表示成功，非 `0` 为业务错误码。`/health` 刻意不带 `/api/` 前缀，不参与封装。

| 方法 | 路径 | 说明 |
| --- | --- | --- |
| GET | `/health` | 存活探针 |
| GET | `/api/system/status` | 三个依赖的就绪状态（含集合维度对照） |
| POST | `/api/documents` | 上传文件并入库（幂等） |
| POST | `/api/documents/text` | 直接提交文本入库 |
| GET | `/api/documents` | 文档分页列表 |
| GET | `/api/documents/{id}` | 文档详情 |
| GET | `/api/documents/{id}/chunks` | 查看切块 |
| POST | `/api/documents/{id}/reindex` | 重建该文档向量 |
| DELETE | `/api/documents/{id}` | 删除文档（连带删向量） |
| POST | `/api/search` | 纯向量检索，不调大模型 |
| POST | `/api/chat/stream` | **SSE 流式问答** |
| POST | `/api/chat/complete` | 非流式问答 |
| GET/POST/DELETE | `/api/conversations[...]` | 会话与消息 |

SSE 事件顺序：`sources`（先推引用，界面立刻能显示）→ `token`（增量文本）→ `done`。

```text
event: sources
data: {"citations":[{"index":1,"chunk_id":42,"document_title":"部署手册","heading_path":"安装 > 依赖","score":0.82}]}

event: token
data: {"text":"先安装 "}

event: done
data: {"conversation_id":7,"message_id":19}
```

> SSE 端点**豁免**统一响应封装（`app/core/middleware/response.py` 里的 `EXEMPT_PATHS`）——
> 它有自己的一套事件协议，被包一层就废了。

## 配置

| 前缀 | 变量 | 默认 | 说明 |
| --- | --- | --- | --- |
| — | `ENVIRONMENT` | development | 生产环境关 `/docs` |
| WEB_ | `WEB_APP_NAME` / `WEB_CORS_*` | — | 应用名与跨域 |
| DB_ | `DB_HOST` / `DB_PORT` / `DB_NAME` / `DB_USER` / `DB_PASSWORD` | localhost / **5433** / rag_db / admin / 123123 | 连接串手工拼接，没有 `DATABASE_URL` |
| MILVUS_ | `MILVUS_URI` | http://localhost:19530 | |
| | `MILVUS_COLLECTION` | rag_chunks | |
| | `MILVUS_EMBED_DIM` | **1024** | 必须与网关 embedding 模型一致 |
| | `MILVUS_SEARCH_EF` / `MILVUS_BATCH_SIZE` / `MILVUS_TIMEOUT` | 64 / 500 / 30 | |
| LLM_ | `LLM_API_BASE` | http://localhost:4000 | LiteLLM 网关地址 |
| | `LLM_API_KEY` | — | 网关密钥 |
| | `LLM_CHAT_MODEL` / `LLM_EMBED_MODEL` / `LLM_RERANK_MODEL` | chat-standard / text-embedding / rerank | 网关侧的模型别名 |
| | `LLM_EMBED_BATCH_SIZE` / `LLM_TIMEOUT` / `LLM_TEMPERATURE` / `LLM_MAX_TOKENS` / `LLM_CONTEXT_WINDOW` | 32 / 60 / 0.2 / 1024 / 32000 | |
| RAG_ | `RAG_CHUNK_MAX_CHARS` / `RAG_CHUNK_MIN_CHARS` / `RAG_CHUNK_OVERLAP` | 1200 / 80 / 150 | 切块 |
| | `RAG_TOP_K` / `RAG_MAX_CONTEXT_TOKENS` / `RAG_HISTORY_TURNS` / `RAG_MAX_FILE_MB` | 5 / 6000 / 6 / 20 | 检索与上下文 |
| | `RAG_USE_RERANK` | false | 是否走网关重排 |
| LOG_ | `LOG_LEVEL` | INFO | |

> `LLM_API_KEY` 所在的 `.env` 已被 gitignore，不会进版本库。

## 测试

| 目录 | 依赖 | 覆盖 |
| --- | --- | --- |
| `test/unit/` | 无 | 切块边界、各格式解析、token 估算、schema 校验、LLM 异常映射、**模型注册表断言** |
| `test/integration/` | 内存 SQLite + 假 LLM/向量库 | 文档全链路、统一信封、SSE 帧顺序、会话落库 |
| | 真实 PostgreSQL（`postgres` 标记） | 迁移往返（upgrade/check/downgrade）、约束、pg_trgm |
| | 真实 Milvus（`milvus` 标记） | 建集合幂等性、向量写入检索往返、按文档删除 |
| `test/e2e/` | 真起服务进程 + 真 PG + 真 Milvus + 真网关 | 上传 → 落库 → 列表可见 → 检索命中 → 删除 → 列表为空 |

依赖不可用时自动跳过，`make test-pg` / `make test-milvus` 会改为失败（CI 用，避免静默跳过）。

**e2e 里那条「列表可见」是回归防线**：框架的老版本 `get_db()` 从不提交事务，
写接口的数据实际会回滚 —— 而进程内的集成测试全程用同一个内存 session，
根本看不出这个问题，只有真起进程 + 真数据库才暴露得出来。

## 钉钉知识库

数据源之一是**钉钉知识库**。对接了开放平台的四个接口：

| 用途 | 接口 |
| --- | --- |
| 鉴权 | `POST /v1.0/oauth2/accessToken` → `{accessToken, expireIn: 7200}` |
| 知识库列表 | `GET /v2.0/wiki/workspaces` |
| 节点树 | `GET /v2.0/wiki/nodes?parentNodeId=&operatorId=&maxResults=50` |
| 文档正文 | `GET /v1.0/doc/suites/documents/{docKey}/blocks?operatorId=` |

所有请求带 `x-acs-dingtalk-access-token` 头。**`operatorId` 必须是用户的 unionId，
不是 userId** —— 拿错了会返回权限错误。

### 两层树

```
知识库
└── 📁 研发
    ├── 📁 前端
    │   └── 📄 组件规范.md        ← DingNode.path = ["研发", "前端", "组件规范.md"]
    └── 📄 部署手册.md
        └── 快速开始              ← DingBlock 组成的标题树
            ├── 第一段正文
            ├── 前置条件
            └── 安装步骤
```

- **目录树**（`DingNode`）：知识库 → 文件夹 → 文档，每个节点记着从根到自己的路径
- **文档内标题树**（`DingBlock`）：blocks 按 `heading.level` 拼成层级树，
  `iter_blocks()` 能按原文顺序遍历并带上标题路径 —— 切块时直接当面包屑用

块的字段名在钉钉那边并不完全一致（`heading.level` 见过 `"2"` 和 `"heading-2"` 两种写法，
表格/代码块的字段也不同），所以解析层对字段名做了兼容：
`text` → 表格的 `cells` → 递归找 `text`/`content`。

### 配置

```shell
DINGTALK_APP_KEY=       # 企业内部应用的 AppKey
DINGTALK_APP_SECRET=    # 企业内部应用的 AppSecret
DINGTALK_OPERATOR_ID=   # 用户的 unionId
DINGTALK_WORKSPACE_ID=  # 留空则取第一个可见的知识库
```

### 怎么拿到这些值

**1. 建应用** — https://open-dev.dingtalk.com/ → 应用开发 → 企业内部应用 → 创建应用
> 若提示「暂无权限」，说明账号还不是开发者：OA 管理后台 → 设置 → 权限管理 → 管理组 → 给你加「开发者」权限。

**2. 拿凭证** — 应用 → 凭证与基础信息 → AppKey / AppSecret

**3. 申请权限** — 应用 → 权限管理 → 按英文 Scope 名搜索开通（发布后生效）：

| Scope | 干什么 |
| --- | --- |
| `Wiki.Node.Read` | 读知识库节点（目录树） |
| `Storage.File.Read` | 读文档正文（blocks） |
| `qyapi_get_member` | 成员信息读权限（查 unionId 用） |

**4. 发布** — 版本管理与发布 → 创建版本 → 发布

**5. 可见范围** — 把你自己加进「应用可见范围」。接口是以 `operatorId` 那个人的身份读的，
他看不到的知识库你也拉不到。

**6. 查 unionId** — `operatorId` 要的是 unionId，但钉钉查询接口的入参给的是 userId：

```shell
make dingtalk-unionid userid=你的userId
```

userId 从 OA 后台的成员列表能看到。返回字段是 `result.unionid`（**没有下划线**），
`result.union_id` 在部分组织里是空的 —— 这是个高频坑，客户端里已经处理了。

### 命令

```shell
make dingtalk-check                             # 体检整条凭证链（鉴权→列库→读根节点）
make dingtalk-unionid userid=xxx                # userId → unionId
make dingtalk-workspaces                        # 列出知识库
make dingtalk-tree                              # 打印目录树
make dingtalk-pull out=tmp/dingtalk.json        # 拉整个知识库（目录树 + 正文）成 JSON
```

`dingtalk-check` 是排障用的一次性体检，能直接看出卡在哪一环：

```
1) 鉴权 … ✓
2) 列知识库 … ✓ 2 个
   知识库：团队知识库（ws-1）
3) 读根节点 … ✓ 8 个
```

## 已知限制与后续可做

- **只做稠密单路检索**。精确词/编号/专有名词的召回目前靠 embedding 的语义能力，
  精确匹配偏弱。数据都在 PostgreSQL 里，加 `pg_trgm` 索引后按 RRF 合并关键词召回
  与向量召回是下一步 —— **不需要改 Milvus schema，也不需要重建向量**。
- **PDF 没有结构**。PDF 一般没有标题层级，退化成「按页 + 段落切分」，引用里给页码。
- **系统提示词固定**。想做 prompt cache 就把它挪到能稳定缓存的位置，
  并保证一个字都不改。
- **没有鉴权**。个人自用默认开放；对外暴露前必须加。
- **`litellm` 依赖树很重**。`import litellm` 放在方法体里懒加载，
  应用启动和单测不受影响；真要减重可以换成直接调网关的 OpenAI 兼容 HTTP 接口。
- **钉钉侧只处理在线文档**（`contentType=ALIDOC`）。本地文件（docx/pdf 附件）
  和代码块/图片还没接 —— 后者目前在钉钉那边就返回 `unknown` 类型。

## 开发约定

- 分层 `api → service → model → database`：
  `api` 只负责接收参数、调用 `service`、返回结果，不写业务逻辑；
  `service` 是业务逻辑的唯一归属地，操作数据库会话。
- 所有 `/api/` 开头的接口，响应体统一信封。
- 业务代码直接抛业务异常，无需自己拼装响应：

  ```python
  from app.exception import NotFoundException

  raise NotFoundException(message="文档不存在")
  ```

- 建表只走迁移：`make db-init` / `make db-upgrade`，**不要在代码里调 `create_all`**。
- 改完模型必须 `make db-migrate message="描述"` 生成迁移脚本，审查后再 `make db-upgrade`。
- **新增模型必须在 `app/model/__init__.py` 里加一行 import**，
  否则 Alembic autogenerate 会认为这张表不存在（生成的迁移里会凭空少一张表）。
- 所有代码必须带类型标注，`make typecheck` 检查。
