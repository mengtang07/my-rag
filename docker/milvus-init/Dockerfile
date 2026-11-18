# Milvus 集合初始化镜像
#
# 刻意只装 pymilvus（不装项目的其它依赖）：
# app/core/milvus_schema.py 不 import pydantic-settings 等任何配置模块，
# 因此这个几十 MB 的镜像就能完成「建集合 + 建索引 + 加载」。
FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

WORKDIR /app

RUN pip install --no-cache-dir pymilvus==3.0.3

COPY entrypoint.py /app/entrypoint.py

ENTRYPOINT ["python", "/app/entrypoint.py"]
