# 配置

配置相关的都在这个包里。

```
config/
├── settings.py         # 通用 / Web / 数据库 / RAG / 日志配置
├── milvus_setting.py   # Milvus 向量库配置
├── llm_setting.py      # LiteLLM 网关配置
├── dingding_setting.py # 钉钉开放平台配置
└── README.md           # 本文件
```

环境变量文件统一放在仓库最外层：

```
.env                   # 实际使用的环境变量文件（gitignored）
.env.example           # 环境变量样例
.env.test.example      # 测试环境变量样例
```

## 怎么用

```python
from config import db_settings, llm_settings, milvus_settings

db_settings.host          # localhost
```

变量名前缀 = 用途，一个前缀一个配置类：

| 前缀 | 配置类 | 单例 | 管什么 |
| --- | --- | --- | --- |
| 无 | `_CommonSettings` | `common_settings` | 环境标识 |
| `WEB_` | `_WebSettings` | `web_settings` | 应用名、跨域 |
| `DB_` | `_DBSettings` | `db_settings` | PostgreSQL 连接 |
| `MILVUS_` | `_MilvusSettings` | `milvus_settings` | Milvus 向量库 |
| `LLM_` | `_LLMSettings` | `llm_settings` | LiteLLM 网关（对话/向量化/重排） |
| `RAG_` | `_RAGSettings` | `rag_settings` | 切块与检索参数 |
| `DINGTALK_` | `_DingtalkSettings` | `dingtalk_settings` | 钉钉知识库 |
| `LOG_` | `_LogSettings` | `log_settings` | 日志级别 |

## 环境变量文件

仓库最外层的 `.env` 是实际生效的文件（gitignored），样例在 `.env.example`：

```shell
cp .env.example .env
```

配置代码默认读仓库根目录的 `.env`，找不到时退回当前工作目录的 `.env`
（读不到就用字段默认值，不会报错）。

> **踩过的坑**：子类必须**重复声明** `env_file`。pydantic-settings 在子类里换掉
> 整个 `model_config` 时，只写 `env_prefix` 会把 `env_file` 一起冲掉，`.env` 就读不到了。

## 变量总表

### 通用

| 变量 | 默认 | 说明 |
| --- | --- | --- |
| `ENVIRONMENT` | development | 生产环境关掉 `/docs` |

### WEB_

| 变量 | 默认 | 说明 |
| --- | --- | --- |
| `WEB_APP_NAME` | my-rag API | OpenAPI 标题 |
| `WEB_CORS_ORIGINS` | * | 跨域白名单，逗号分隔 |
| `WEB_CORS_ALLOW_METHODS` | * | |
| `WEB_CORS_ALLOW_HEADERS` | * | |
| `WEB_CORS_EXPOSE_HEADERS` | 空 | 浏览器可读响应头 |
| `WEB_CORS_ALLOW_CREDENTIALS` | false | |
| `WEB_CORS_MAX_AGE` | 600 | 预检缓存秒数 |

### DB_

| 变量 | 默认 | 说明 |
| --- | --- | --- |
| `DB_HOST` | localhost | |
| `DB_PORT` | 5433 | compose 映射 5433→5432（5432 被本机别的服务占了） |
| `DB_NAME` | rag_db | |
| `DB_USER` | admin | |
| `DB_PASSWORD` | 123123 | |
| `DB_ECHO` | false | SQL 回显 |

### MILVUS_

| 变量 | 默认 | 说明 |
| --- | --- | --- |
| `MILVUS_URI` | http://localhost:19530 | |
| `MILVUS_COLLECTION` | rag_chunks | |
| `MILVUS_EMBED_DIM` | 1024 | **必须 == 网关 embedding 模型的实际维度** |
| `MILVUS_SEARCH_EF` | 64 | HNSW 查询 ef |
| `MILVUS_BATCH_SIZE` | 500 | upsert 每批行数 |
| `MILVUS_TIMEOUT` | 30 | 秒 |
| `MILVUS_TOKEN` | 空 | 托管版鉴权 |

### LLM_

| 变量 | 默认 | 说明 |
| --- | --- | --- |
| `LLM_API_BASE` | http://localhost:4000 | LiteLLM 网关 |
| `LLM_API_KEY` | 空 | 网关密钥 |
| `LLM_CHAT_MODEL` | chat-standard | 网关侧别名 |
| `LLM_EMBED_MODEL` | text-embedding | 网关侧别名（维度 1024） |
| `LLM_RERANK_MODEL` | rerank | 网关侧别名 |
| `LLM_EMBED_BATCH_SIZE` | 32 | |
| `LLM_TIMEOUT` | 60 | 秒 |
| `LLM_TEMPERATURE` | 0.2 | |
| `LLM_MAX_TOKENS` | 1024 | |
| `LLM_CONTEXT_WINDOW` | 32000 | 预算计算用 |

### RAG_

| 变量 | 默认 | 说明 |
| --- | --- | --- |
| `RAG_CHUNK_MAX_CHARS` | 1200 | 单块最大字符数 |
| `RAG_CHUNK_MIN_CHARS` | 80 | 小于此值且同标题的块并入前一块 |
| `RAG_CHUNK_OVERLAP` | 150 | 同区块内相邻块的重叠字符数 |
| `RAG_TOP_K` | 5 | 默认召回条数 |
| `RAG_MAX_CONTEXT_TOKENS` | 6000 | 拼进 prompt 的上下文上限 |
| `RAG_HISTORY_TURNS` | 6 | 参与上下文的历史消息条数 |
| `RAG_MAX_FILE_MB` | 20 | 上传大小上限 |
| `RAG_USE_RERANK` | false | 是否走网关重排 |

### DINGTALK_

| 变量 | 默认 | 说明 |
| --- | --- | --- |
| `DINGTALK_APP_KEY` | 空 | 企业内部应用的 AppKey（新版后台叫 Client ID） |
| `DINGTALK_APP_SECRET` | 空 | 同上（新版叫 Client Secret） |
| `DINGTALK_OPERATOR_ID` | 空 | **必须是 unionId，不是 userId** |
| `DINGTALK_WORKSPACE_ID` | 空 | 留空则取第一个可见的知识库 |
| `DINGTALK_BASE_URL` | https://api.dingtalk.com | |
| `DINGTALK_TIMEOUT` | 30 | 秒 |

> 需要的权限 Scope：`Wiki.Workspace.Read`、`Wiki.Node.Read`、`Storage.File.Read`。
> `make dingtalk-scopes` 会打印带 AppKey 的申请链接。

### LOG_

| 变量 | 默认 | 说明 |
| --- | --- | --- |
| `LOG_LEVEL` | INFO | |
