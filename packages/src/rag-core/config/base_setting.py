"""配置基类与环境变量文件定位"""

from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

# 本包所在目录（config/）
CONFIG_DIR: Path = Path(__file__).resolve().parent
# 仓库根目录（config/ → rag-core/ → src/ → packages/ → 仓库根）
PROJECT_ROOT: Path = CONFIG_DIR.parents[3]


def _resolve_env_file() -> str:
    """找到环境变量文件

    只有仓库最外层的 `.env`；没有就退回当前工作目录，
    再没有也不报错（pydantic-settings 会直接用字段默认值）。
    """
    root_env = PROJECT_ROOT / ".env"
    if root_env.is_file():
        return str(root_env)
    return str(Path.cwd() / ".env")


ENV_FILE: str = _resolve_env_file()


class _BaseSettingsWithEnv(BaseSettings):
    """所有配置类的基类

    注意：子类的 `model_config` 必须**重复声明** `env_file`。
    pydantic-settings 在子类里换掉整个 `model_config` 时，
    只写 `env_prefix` 会把 `env_file` 一起冲掉，`.env` 就读不到了。
    """

    model_config = SettingsConfigDict(env_file=ENV_FILE, extra="ignore")
