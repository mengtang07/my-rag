-- 初始化脚本：只在数据卷为空（首次启动）时执行一次。
--
-- pg_trgm 给 chunk.content 提供三元组模糊匹配索引，
-- 后续做「关键词召回 + Milvus 稠密召回」的 RRF 混合检索时直接可用，
-- 不需要改 Milvus schema、不需要重建向量。
CREATE EXTENSION IF NOT EXISTS pg_trgm;
