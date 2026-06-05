"""
搜索工具模块（Search Tools）
提供两套独立的检索能力，供大模型通过 Tool Calling 机制调用：

1. search_internal_kb — 内部私有知识库检索
   - 大模型在评估时若觉得标准答案不够充分，可主动调用此工具
   - 当前使用 Mock/本地文件占位，未来可无缝接入向量数据库或内部知识库 API

2. search_aws_docs — 外部 AWS 官方文档检索
   - 系统后台自动触发，检索 AWS 官方资源
   - 强制限定搜索源：User Guide、Knowledge Center、Prescriptive Guidance、
     Developer Guide、官方 FAQ
   - 当前使用 Mock 占位，未来接入搜索引擎 API 或爬虫

两个工具的 OpenAI Function Calling 定义在 TOOL_DEFINITIONS 中导出。
"""

import json
import logging
from pathlib import Path
from typing import Optional

import httpx

from config import Config
from logger import log


# ============================================================
# Tool 1: 内部私有知识库检索
# ============================================================

def search_internal_kb(query: str, top_k: int = 3) -> str:
    """
    检索内部私有知识库

    当前实现：Mock 占位（读取本地补充资料文件）
    未来接入：向量数据库（如 OpenSearch / Pinecone / Bedrock Knowledge Base）
              或内部知识库 REST API

    Args:
        query: 检索关键词或问题描述
        top_k: 返回结果条数上限

    Returns:
        str: 检索到的相关文档片段，格式化为文本
             如果无结果返回空字符串
    """
    log(f"[Tool] search_internal_kb 被调用 | query={query}", stage="SEARCH", level=logging.DEBUG)

    # ---- Mock 实现：从本地补充资料目录读取 ----
    # 约定目录：./internal_kb/  下放置 .txt 或 .md 文件
    kb_dir = Path(Config.INTERNAL_KB_DIR)
    if not kb_dir.exists():
        log(f"[Tool] 内部知识库目录不存在: {kb_dir}，返回空", stage="SEARCH", level=logging.DEBUG)
        return ""

    results = []
    query_lower = query.lower()
    for filepath in sorted(kb_dir.glob("**/*.md")) + sorted(kb_dir.glob("**/*.txt")):
        content = filepath.read_text(encoding="utf-8")
        # 简单关键词匹配（Mock 逻辑，正式环境应替换为向量相似度检索）
        if any(kw in content.lower() for kw in query_lower.split()):
            # 截取前 500 字符作为摘要
            snippet = content[:500].strip()
            results.append(f"[来源: {filepath.name}]\n{snippet}")
            if len(results) >= top_k:
                break

    if results:
        log(f"[Tool] 内部知识库命中 {len(results)} 条结果", stage="SEARCH")
    else:
        log(f"[Tool] 内部知识库无匹配结果", stage="SEARCH", level=logging.DEBUG)

    return "\n\n---\n\n".join(results)


# ============================================================
# Tool 2: 外部 AWS 官方文档检索
# ============================================================

# 强制限定的搜索源域名
AWS_ALLOWED_DOMAINS = [
    "docs.aws.amazon.com",
    "docs.amazonaws.cn",
    "repost.aws",                     # Knowledge Center 新域名
    "aws.amazon.com/premiumsupport",  # KC 旧路径
    "aws.amazon.com/prescriptive-guidance",
    "aws.amazon.com/faqs",
    "aws.amazon.com/cn/faqs",
]

# 搜索源类型标签（用于构造搜索 query）
AWS_SOURCE_TYPES = [
    "User Guide",
    "Knowledge Center",
    "Prescriptive Guidance",
    "Developer Guide",
    "FAQ",
]


def search_aws_docs(query: str, top_k: int = 3) -> str:
    """
    检索 AWS 官方文档

    强制搜索源限制：
    - User Guide（用户指南）
    - Knowledge Center（知识中心/KC）
    - Prescriptive Guidance（规范性指导/架构指南）
    - Developer Guide（开发人员指南）
    - 官方 FAQ 页面

    当前实现：Mock 占位
    未来接入方案（任选其一）：
    - 搜索引擎 API（如 Tavily / SerpAPI / Bing API）+ 域名过滤
    - AWS 官方文档爬虫 + 本地索引
    - Amazon Kendra 搜索

    Args:
        query: 检索关键词
        top_k: 返回结果条数上限

    Returns:
        str: 格式化的搜索结果摘要文本
             如果无结果返回空字符串
    """
    log(f"[Tool] search_aws_docs 被调用 | query={query}", stage="SEARCH", level=logging.DEBUG)

    # ---- Mock 实现 ----
    # 如果配置了搜索 API Key，尝试真实调用；否则返回空
    search_api_key = Config.SEARCH_API_KEY
    search_api_url = Config.SEARCH_API_URL

    if search_api_key and search_api_url:
        return _call_search_api(query, search_api_key, search_api_url, top_k)

    # 无搜索 API 配置时，返回空（大模型将仅依赖自身知识）
    log("[Tool] 未配置 SEARCH_API，search_aws_docs 返回空", stage="SEARCH", level=logging.DEBUG)
    return ""


def _call_search_api(query: str, api_key: str, api_url: str, top_k: int) -> str:
    """
    调用外部搜索 API 获取 AWS 官方文档

    预期接入的 API 契约（以 Tavily 为例）：
    POST {api_url}/search
    Body: {
        "query": "...",
        "search_depth": "advanced",
        "include_domains": [...],
        "max_results": N
    }

    Response: {
        "results": [
            {"title": "...", "url": "...", "content": "..."},
            ...
        ]
    }

    可替换为 SerpAPI / Bing API / 自建爬虫，只需返回相同格式即可。
    """
    try:
        # 构造带域名过滤的搜索请求
        payload = {
            "query": f"AWS {query}",
            "search_depth": "advanced",
            "include_domains": AWS_ALLOWED_DOMAINS,
            "max_results": top_k,
        }
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {api_key}",
        }

        with httpx.Client(timeout=15.0) as client:
            resp = client.post(f"{api_url}/search", json=payload, headers=headers)
            resp.raise_for_status()
            data = resp.json()

        results = data.get("results", [])
        if not results:
            return ""

        # 格式化结果（不暴露完整 URL，仅展示标题和内容摘要）
        formatted = []
        for r in results[:top_k]:
            title = r.get("title", "")
            content = r.get("content", "")[:600]
            formatted.append(f"[{title}]\n{content}")

        log(f"[Tool] AWS 文档检索命中 {len(formatted)} 条结果", stage="SEARCH")
        return "\n\n---\n\n".join(formatted)

    except Exception as e:
        log(f"[Tool] search_aws_docs API 调用失败: {e}", stage="ERROR", level=logging.ERROR)
        return ""


# ============================================================
# OpenAI Function Calling 工具定义
# ============================================================

TOOL_DEFINITIONS = [
    {
        "type": "function",
        "function": {
            "name": "search_internal_kb",
            "description": (
                "检索团队内部私有知识库。当标准答案不够充分、需要补充内部资料来辅助判定时调用。"
                "返回相关的内部文档片段。"
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "检索关键词或问题描述，如'EC2 实例类型选择依据'",
                    },
                },
                "required": ["query"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "search_aws_docs",
            "description": (
                "检索 AWS 官方文档（User Guide、Knowledge Center、Prescriptive Guidance、"
                "Developer Guide、FAQ）。当需要查阅最新官方资料来验证新人回答的准确性时调用。"
                "搜索范围严格限定在 AWS 官方资源。"
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "检索关键词，如'S3 跨区域复制 中国区'",
                    },
                },
                "required": ["query"],
            },
        },
    },
]


# 工具名 → 函数映射（供 evaluator 调用）
TOOL_FUNCTIONS = {
    "search_internal_kb": search_internal_kb,
    "search_aws_docs": search_aws_docs,
}
