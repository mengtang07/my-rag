# my-rag 后端 API

FastAPI 服务：文档入库、向量检索、流式问答。

## 启动

```shell
# 根目录执行
make docker-up     # 起 PostgreSQL + Milvus
make db-init       # 建库 + 跑迁移
make milvus-init   # 幂等建集合 + 建索引
make dev           # http://localhost:8088
```

接口文档：http://localhost:8088/docs

## 目录

```
app/
├── main.py       应用入口
├── cli.py        命令行：ingest / reindex / search
├── api/          接口层
├── schema/       出入参 DTO
├── service/      业务逻辑
├── model/        ORM 模型
├── core/         配置 / 数据库 / LLM / Milvus / 中间件
└── exception/    业务异常 + 全局处理器
```

## 命令行

```shell
make ingest file=docs/部署手册.md   # 摄入单个文件
make ingest-dir dir=docs             # 摄入整个目录
make search query="怎么安装依赖"      # 只检索，不调大模型
```
