"""配置

配置相关的都在这个包里：

- `settings.py` —— pydantic-settings 配置类与单例
- `env.example` —— 环境变量样例（复制成 `env` 就是实际用的文件）
- `env.test.example` —— 测试环境变量样例
- `README.md` —— 每个变量的说明

用法：`from config import db_settings, llm_settings`
"""

from config.settings import (
    ENV_FILE,
    common_settings,
    db_settings,
    dingtalk_settings,
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
