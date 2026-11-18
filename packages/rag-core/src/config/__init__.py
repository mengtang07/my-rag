"""配置

配置相关的都在这个包里：

- `settings.py` —— 通用 / Web / 数据库 / Milvus / LLM / RAG / 日志配置
- `dingding_setting.py` —— 钉钉开放平台配置
- `README.md` —— 每个变量的说明

环境变量文件在仓库最外层：`.env`
（样例是 `.env.example`，复制一份改名即可）。

用法：`from config import db_settings, llm_settings, dingtalk_settings`
"""

from config.dingding_setting import dingtalk_settings
from config.settings import (
    ENV_FILE,
    common_settings,
    db_settings,
    llm_settings,
    log_settings,
    milvus_settings,
    rag_settings,
    web_settings,
)

__all__ = [
    "ENV_FILE",
    "common_settings",
    "db_settings",
    "dingtalk_settings",
    "llm_settings",
    "log_settings",
    "milvus_settings",
    "rag_settings",
    "web_settings",
]
