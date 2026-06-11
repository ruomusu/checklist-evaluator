"""
数据模型模块
- 定义题目、知识库条目、新人回答、评估结果等核心数据结构
- 使用 Pydantic 确保数据校验和序列化
"""

from enum import Enum
from typing import Optional
from pydantic import BaseModel, Field


class MasteryLevel(str, Enum):
    """掌握程度枚举"""
    EXCELLENT = "Excellent"
    SATISFACTORY = "Satisfactory"
    FAIL = "Fail"


class KnowledgeItem(BaseModel):
    """知识库中的单道题目"""
    question_id: str = Field(description="题目编号")
    question: str = Field(description="题目内容")
    reference_answer: str = Field(description="标准参考答案文本")
    reference_links: list[str] = Field(default_factory=list, description="官方参考链接列表")


class StudentAnswer(BaseModel):
    """新人对单道题目的回答"""
    question_id: str = Field(description="对应题目编号")
    answer_text: str = Field(description="新人的回答文本")


class QuestionEvaluation(BaseModel):
    """单题评估结果（判定等级、正确率、亮点、盲区）"""
    question_id: str = Field(description="题目编号")
    question: str = Field(default="", description="原题文本")
    mastery_level: MasteryLevel = Field(description="判定等级")
    score: int = Field(description="正确率百分比（0-100）")
    strengths: list[str] = Field(default_factory=list, description="答题亮点（基于具体技术事实）")
    missing_points: list[str] = Field(default_factory=list, description="知识盲区（含角标引用）")
    notes: str = Field(default="", description="可选提醒，如链接区域建议")


class ReadingGuideItem(BaseModel):
    """单题推荐阅读"""
    question_id: str = Field(description="题目编号")
    question_summary: str = Field(description="题目简述")
    resources: list[str] = Field(default_factory=list, description="推荐资源列表")


class EvaluationReport(BaseModel):
    """评估报告"""
    student_name: str = Field(default="新人", description="新人姓名")
    total_questions: int = Field(description="总题目数")
    excellent_count: int = Field(default=0, description="Excellent 的题目数")
    satisfactory_count: int = Field(default=0, description="Satisfactory 的题目数")
    fail_count: int = Field(default=0, description="Fail 的题目数")
    mastered_ids: list[str] = Field(default_factory=list, description="Excellent 的题目编号列表")
    mastered_has_global_links: bool = Field(default=False, description="Excellent 题目中是否有使用全球区链接的")
    question_evaluations: list[QuestionEvaluation] = Field(description="Satisfactory 和 Fail 的逐题评估详情")
    reading_guide: list[ReadingGuideItem] = Field(default_factory=list, description="推荐阅读与提升指南")
