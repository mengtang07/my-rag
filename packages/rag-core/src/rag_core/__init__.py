"""my-rag 共享包：与框架无关的 RAG 领域逻辑

这里只放**纯函数**（解析、切块、token 估算），刻意不依赖 FastAPI / SQLAlchemy /
litellm，这样共享包的单元测试跑得飞快，也不会把大模型 SDK 的重依赖拖进来。
"""
