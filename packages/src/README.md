# rag-core

my-rag 的共享发行包：**纯 RAG 领域逻辑**，不依赖 FastAPI / SQLAlchemy / litellm。

一个发行包里带三个 import 包：

```
rag-core/
├── rag_core/     # RAG 领域逻辑
│   ├── models.py     #   Block / ParsedDocument / ChunkDraft
│   ├── parsing/      #   markdown / pdf / docx / html / txt 解析
│   ├── chunking/     #   结构感知切块
│   └── text/         #   CJK 感知的 token 估算
├── dingding/     # 钉钉知识库接入（独立 import 包）
│   ├── client.py     #   开放平台接口的异步客户端
│   ├── models.py     #   树结构模型（DingNode / DingBlock / …）
│   ├── tree.py       #   树构建：节点解析、标题树、遍历
│   └── exceptions.py #   DingTalkError
└── config/       # 配置（pydantic-settings 配置类与单例）
```

## 设计要点

- **标题路径随块走**：markdown / docx / html 能还原标题层级，切块带上
  `安装 > 依赖` 这样的路径，回答时才能精确引用到章节。
- **切块带标题前缀**：入库正文是 `## 标题路径\n\n正文`，前缀参与向量化，
  检索「依赖安装」时更容易命中对应章节。
- **PDF 退化**：PDF 通常没有标题结构，退化成「按页切」，引用时给页码。

## 钉钉知识库

`dingding` 把钉钉知识库拉成**两层树**：

```
知识库
└── 📁 研发
    ├── 📁 前端
    │   └── 📄 组件规范.md        ← DingNode.path = ["研发", "前端", "组件规范.md"]
    └── 📄 部署手册.md
        └── 快速开始              ← DingBlock 组成的标题树
```

- **目录树**（`DingNode`）：知识库 → 文件夹 → 文档，每节点记着从根到自己的路径
- **文档内标题树**（`DingBlock`）：blocks 按 `heading.level` 拼成层级树，
  `iter_blocks()` 能按原文顺序遍历并带上标题路径 —— 切块时直接当面包屑用

用的接口与需要的 Scope：

| 用途 | 接口 | Scope |
| --- | --- | --- |
| 鉴权 | `POST /v1.0/oauth2/accessToken` | — |
| 知识库列表 | `GET /v2.0/wiki/workspaces` | `Wiki.Workspace.Read` |
| 节点树 | `GET /v2.0/wiki/nodes` | `Wiki.Node.Read` |
| 文档正文 | `GET /v1.0/doc/suites/documents/{docKey}/blocks` | `Storage.File.Read` |

几个坑（代码里都处理了）：

- `operatorId` 必须是用户的 **unionId**，不是 userId
- 文档的 `docKey`：wiki 接口里等于 nodeId，企业存储接口里是 uuid
- `heading.level` 见过 `"2"` 和 `"heading-2"` 两种写法
- 返回的 unionId 字段是 `result.unionid`（**没有下划线**）
