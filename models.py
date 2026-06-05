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
    MASTERED = "掌握"
    AMBIGUOUS = "模棱两可"
    WEAK = "薄弱"


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
    """单题评估结果"""
    question_id: str = Field(description="题目编号")
    question: str = Field(description="题目内容")
    mastery_level: MasteryLevel = Field(description="掌握程度判定")
    strengths: list[str] = Field(default_factory=list, description="回答中的亮点")
    missing_points: list[str] = Field(default_factory=list, description="缺失的关键知识点")
    comment: str = Field(default="", description="评语")


class FocusArea(BaseModel):
    """重点复习领域"""
    topic: str = Field(description="薄弱知识点主题")
    related_questions: list[str] = Field(description="关联的题目编号列表")
    suggestion: str = Field(description="复习建议")


class FollowUpQuestion(BaseModel):
    """导师追问建议"""
    question_id: str = Field(description="针对的原始题目编号")
    follow_up: str = Field(description="追问问题")
    purpose: str = Field(description="追问目的")


class EvaluationReport(BaseModel):
    """最终评估报告"""
    student_name: str = Field(default="新人", description="新人姓名")
    total_questions: int = Field(description="总题目数")
    mastered_count: int = Field(default=0, description="掌握的题目数")
    ambiguous_count: int = Field(default=0, description="模棱两可的题目数")
    weak_count: int = Field(default=0, description="薄弱的题目数")
    question_evaluations: list[QuestionEvaluation] = Field(description="逐题评估详情")
    focus_areas: list[FocusArea] = Field(default_factory=list, description="重点复习聚焦")
    follow_up_questions: list[FollowUpQuestion] = Field(default_factory=list, description="导师追问建议")
    overall_summary: str = Field(default="", description="总体评价")
