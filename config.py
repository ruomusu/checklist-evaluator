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
    # LLM 提供者选择（动态）
    # ========================
    # 在 .env 中设置 LLM_PROVIDER=xxx，然后配置对应的：
    #   XXX_API_KEY, XXX_BASE_URL, XXX_MODEL
    # 例如 LLM_PROVIDER=qwen → 读取 QWEN_API_KEY, QWEN_BASE_URL, QWEN_MODEL
    LLM_PROVIDER: str = os.getenv("LLM_PROVIDER", "openai")

    # ========================
    # 通用 LLM 参数
    # ========================
    TEMPERATURE: float = float(os.getenv("TEMPERATURE", "0.2"))
    MAX_TOKENS: int = int(os.getenv("MAX_TOKENS", "4096"))

    @classmethod
    def get_llm_config(cls) -> dict:
        """
        根据 LLM_PROVIDER 动态读取对应的环境变量

        命名规则：
            LLM_PROVIDER=xxx
            → {XXX}_API_KEY
            → {XXX}_BASE_URL
            → {XXX}_MODEL

        Returns:
            dict: {"api_key": ..., "base_url": ..., "model": ..., "provider": ...}

        Raises:
            ValueError: 如果必要的环境变量未配置
        """
        provider = cls.LLM_PROVIDER.strip().upper()

        api_key = os.getenv(f"{provider}_API_KEY", "")
        base_url = os.getenv(f"{provider}_BASE_URL", "")
        model = os.getenv(f"{provider}_MODEL", "")

        if not api_key:
            raise ValueError(
                f"LLM_PROVIDER={cls.LLM_PROVIDER}，但未找到环境变量 {provider}_API_KEY，"
                f"请在 .env 中配置"
            )
        if not base_url:
            raise ValueError(
                f"LLM_PROVIDER={cls.LLM_PROVIDER}，但未找到环境变量 {provider}_BASE_URL，"
                f"请在 .env 中配置"
            )
        if not model:
            raise ValueError(
                f"LLM_PROVIDER={cls.LLM_PROVIDER}，但未找到环境变量 {provider}_MODEL，"
                f"请在 .env 中配置"
            )

        return {
            "api_key": api_key,
            "base_url": base_url,
            "model": model,
            "provider": cls.LLM_PROVIDER,
        }

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
    # 搜索工具配置
    # ========================

    # --- 内部知识库目录（search_internal_kb 的本地 Mock 数据源） ---
    INTERNAL_KB_DIR: str = os.getenv("INTERNAL_KB_DIR", "./internal_kb")

    # --- 外部 AWS 文档搜索 API（如 Tavily / SerpAPI） ---
    SEARCH_API_KEY: str = os.getenv("SEARCH_API_KEY", "")
    SEARCH_API_URL: str = os.getenv("SEARCH_API_URL", "")

    # --- Tool Calling 开关 ---
    # 设为 true 启用大模型主动调用搜索工具，设为 false 则跳过
    ENABLE_TOOL_CALLING: bool = os.getenv("ENABLE_TOOL_CALLING", "true").lower() == "true"

    # ========================
    # 报告输出配置
    # ========================
    OUTPUT_DIR: str = os.getenv("OUTPUT_DIR", "./output")
