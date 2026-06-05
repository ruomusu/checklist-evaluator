"""
知识库提供者模块（Knowledge Provider）
- 将标准答案的获取抽象为可插拔的 Provider 接口
- 支持本地 JSON、外部 API、数据库三种获取方式
- 可根据题目 ID 或题目列表动态拉取标准答案
"""

import json
from abc import ABC, abstractmethod
from typing import Optional

import httpx

from config import Config
from models import KnowledgeItem


class KnowledgeProvider(ABC):
    """
    知识库提供者抽象基类
    所有具体实现（本地文件 / API / 数据库）都需继承此类
    """

    @abstractmethod
    def get_all_questions(self, checklist_id: str = None) -> list[KnowledgeItem]:
        """
        获取某个 Checklist 下的所有题目与标准答案

        Args:
            checklist_id: 可选的 Checklist 标识（如 "ec2-basics"），
                          用于从外部系统筛选特定题目集

        Returns:
            list[KnowledgeItem]: 题目列表
        """
        ...

    @abstractmethod
    def get_question_by_id(self, question_id: str) -> Optional[KnowledgeItem]:
        """
        根据题目 ID 获取单道题目

        Args:
            question_id: 题目编号（如 "Q1"）

        Returns:
            KnowledgeItem 或 None
        """
        ...


class LocalFileProvider(KnowledgeProvider):
    """
    本地 JSON 文件提供者（保留向后兼容）
    适合开发调试或离线场景
    """

    def __init__(self, filepath: str):
        self.filepath = filepath
        self._cache: list[KnowledgeItem] = []

    def _load(self) -> list[KnowledgeItem]:
        if not self._cache:
            with open(self.filepath, "r", encoding="utf-8") as f:
                data = json.load(f)
            self._cache = [KnowledgeItem(**item) for item in data]
        return self._cache

    def get_all_questions(self, checklist_id: str = None) -> list[KnowledgeItem]:
        return self._load()

    def get_question_by_id(self, question_id: str) -> Optional[KnowledgeItem]:
        for item in self._load():
            if item.question_id == question_id:
                return item
        return None


class APIProvider(KnowledgeProvider):
    """
    外部 API 提供者
    通过 HTTP 接口从远程知识库服务拉取标准答案

    预期 API 契约：
    - GET /api/checklist/{checklist_id}/questions  → 返回题目列表 JSON
    - GET /api/questions/{question_id}             → 返回单道题目 JSON

    响应格式与 KnowledgeItem 字段一致：
    {
      "question_id": "Q1",
      "question": "...",
      "reference_answer": "...",
      "reference_links": [...]
    }
    """

    def __init__(self, base_url: str = None, api_key: str = None, timeout: float = 30.0):
        """
        Args:
            base_url: 知识库 API 的根地址，如 "https://kb.internal.example.com"
            api_key:  API 认证密钥（可选，取决于你的后端鉴权方式）
            timeout:  请求超时时间（秒）
        """
        self.base_url = (base_url or Config.KNOWLEDGE_API_URL).rstrip("/")
        self.api_key = api_key or Config.KNOWLEDGE_API_KEY
        self.timeout = timeout

    def _headers(self) -> dict:
        headers = {"Content-Type": "application/json"}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
        return headers

    def get_all_questions(self, checklist_id: str = None) -> list[KnowledgeItem]:
        """从 API 拉取指定 Checklist 的所有题目"""
        cid = checklist_id or "default"
        url = f"{self.base_url}/api/checklist/{cid}/questions"

        with httpx.Client(timeout=self.timeout) as client:
            resp = client.get(url, headers=self._headers())
            resp.raise_for_status()
            data = resp.json()

        return [KnowledgeItem(**item) for item in data]

    def get_question_by_id(self, question_id: str) -> Optional[KnowledgeItem]:
        """从 API 拉取单道题目"""
        url = f"{self.base_url}/api/questions/{question_id}"

        with httpx.Client(timeout=self.timeout) as client:
            resp = client.get(url, headers=self._headers())
            if resp.status_code == 404:
                return None
            resp.raise_for_status()
            data = resp.json()

        return KnowledgeItem(**data)


class DatabaseProvider(KnowledgeProvider):
    """
    数据库提供者
    通过 SQL 查询从关系型数据库获取标准答案

    预期表结构：
    CREATE TABLE knowledge_base (
        question_id   VARCHAR(32) PRIMARY KEY,
        checklist_id  VARCHAR(64),
        question      TEXT NOT NULL,
        reference_answer TEXT NOT NULL,
        reference_links  JSON,         -- 存储为 JSON 数组
        created_at    TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );

    注意：此类依赖 asyncpg 或 pymysql 等驱动，请根据实际数据库类型安装对应依赖
    """

    def __init__(self, connection_string: str = None):
        """
        Args:
            connection_string: 数据库连接字符串
                PostgreSQL: "postgresql://user:pass@host:5432/dbname"
                MySQL:      "mysql://user:pass@host:3306/dbname"
                SQLite:     "sqlite:///path/to/db.sqlite"
        """
        self.connection_string = connection_string or Config.KNOWLEDGE_DB_URL

    def _get_connection(self):
        """
        获取数据库连接
        这里使用 sqlite3 作为示例实现，生产环境可替换为 asyncpg / pymysql / SQLAlchemy
        """
        import sqlite3
        return sqlite3.connect(self.connection_string.replace("sqlite:///", ""))

    def get_all_questions(self, checklist_id: str = None) -> list[KnowledgeItem]:
        """从数据库查询所有题目"""
        conn = self._get_connection()
        cursor = conn.cursor()

        if checklist_id:
            cursor.execute(
                "SELECT question_id, question, reference_answer, reference_links "
                "FROM knowledge_base WHERE checklist_id = ?",
                (checklist_id,),
            )
        else:
            cursor.execute(
                "SELECT question_id, question, reference_answer, reference_links "
                "FROM knowledge_base"
            )

        rows = cursor.fetchall()
        conn.close()

        items = []
        for row in rows:
            links = json.loads(row[3]) if row[3] else []
            items.append(KnowledgeItem(
                question_id=row[0],
                question=row[1],
                reference_answer=row[2],
                reference_links=links,
            ))
        return items

    def get_question_by_id(self, question_id: str) -> Optional[KnowledgeItem]:
        """从数据库查询单道题目"""
        conn = self._get_connection()
        cursor = conn.cursor()
        cursor.execute(
            "SELECT question_id, question, reference_answer, reference_links "
            "FROM knowledge_base WHERE question_id = ?",
            (question_id,),
        )
        row = cursor.fetchone()
        conn.close()

        if not row:
            return None

        links = json.loads(row[3]) if row[3] else []
        return KnowledgeItem(
            question_id=row[0],
            question=row[1],
            reference_answer=row[2],
            reference_links=links,
        )


def create_provider(provider_type: str = None, **kwargs) -> KnowledgeProvider:
    """
    工厂函数：根据配置创建对应的 KnowledgeProvider 实例

    Args:
        provider_type: "local" | "api" | "database"，默认读取 Config.KNOWLEDGE_PROVIDER
        **kwargs: 传递给具体 Provider 的参数

    Returns:
        KnowledgeProvider 实例
    """
    ptype = (provider_type or Config.KNOWLEDGE_PROVIDER).lower()

    if ptype == "local":
        filepath = kwargs.get("filepath", Config.KNOWLEDGE_LOCAL_FILE)
        return LocalFileProvider(filepath)
    elif ptype == "api":
        return APIProvider(
            base_url=kwargs.get("base_url"),
            api_key=kwargs.get("api_key"),
        )
    elif ptype == "database":
        return DatabaseProvider(
            connection_string=kwargs.get("connection_string"),
        )
    else:
        raise ValueError(f"不支持的 provider 类型: {ptype}，可选: local, api, database")
