"""
配置模块
- 管理 API 密钥、模型选择、温度参数等全局配置
- 管理知识库数据源配置（本地文件 / API / 数据库）
- 支持通过 .env 文件或环境变量注入
"""

import os
from dotenv import load_dotenv

load_dotenv()


class Config:
    # ========================
    # LLM API 配置
    # ========================
    OPENAI_API_KEY: str = os.getenv("OPENAI_API_KEY", "")
    OPENAI_BASE_URL: str = os.getenv("OPENAI_BASE_URL", "https://api.openai.com/v1")
    MODEL_NAME: str = os.getenv("MODEL_NAME", "gpt-4o")
    TEMPERATURE: float = float(os.getenv("TEMPERATURE", "0.2"))
    MAX_TOKENS: int = int(os.getenv("MAX_TOKENS", "4096"))

    # ========================
    # 知识库数据源配置
    # ========================
    # 提供者类型: "local" | "api" | "database"
    KNOWLEDGE_PROVIDER: str = os.getenv("KNOWLEDGE_PROVIDER", "local")

    # --- 本地文件模式 ---
    KNOWLEDGE_LOCAL_FILE: str = os.getenv("KNOWLEDGE_LOCAL_FILE", "sample_knowledge_base.json")

    # --- API 模式 ---
    KNOWLEDGE_API_URL: str = os.getenv("KNOWLEDGE_API_URL", "https://kb.internal.example.com")
    KNOWLEDGE_API_KEY: str = os.getenv("KNOWLEDGE_API_KEY", "")

    # --- 数据库模式 ---
    KNOWLEDGE_DB_URL: str = os.getenv("KNOWLEDGE_DB_URL", "sqlite:///knowledge.db")

    # ========================
    # 报告输出配置
    # ========================
    OUTPUT_DIR: str = os.getenv("OUTPUT_DIR", "./output")
