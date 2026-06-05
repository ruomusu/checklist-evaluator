"""
评估引擎模块
- 负责组装 Prompt、调用大模型、解析返回结果
- 支持外部搜索上下文注入
- 集成结构化日志记录
"""

import json
import logging
import time

from openai import OpenAI

from config import Config
from logger import log
from models import (
    KnowledgeItem,
    StudentAnswer,
    QuestionEvaluation,
    FocusArea,
    FollowUpQuestion,
    EvaluationReport,
    MasteryLevel,
)
from prompts import SYSTEM_PROMPT, EVALUATION_USER_PROMPT_TEMPLATE


class Evaluator:
    """
    核心评估引擎
    职责：整合知识库、新人答案和搜索上下文，调用 LLM 生成评估报告
    """

    def __init__(self):
        self.client = OpenAI(
            api_key=Config.OPENAI_API_KEY,
            base_url=Config.OPENAI_BASE_URL,
        )
        self.model = Config.MODEL_NAME
        self.temperature = Config.TEMPERATURE
        self.max_tokens = Config.MAX_TOKENS
        log(f"Evaluator 初始化完成 | 模型: {self.model} | 温度: {self.temperature}", stage="INIT")

    def _format_knowledge_base(self, items: list[KnowledgeItem]) -> str:
        """将知识库格式化为文本供 Prompt 使用"""
        sections = []
        for item in items:
            links_text = "\n".join(f"  - {link}" for link in item.reference_links)
            section = (
                f"### 题目 {item.question_id}: {item.question}\n"
                f"**标准答案：**\n{item.reference_answer}\n"
                f"**参考链接：**\n{links_text}"
            )
            sections.append(section)
        return "\n\n".join(sections)

    def _format_student_answers(self, answers: list[StudentAnswer]) -> str:
        """将新人答案格式化为文本"""
        parts = []
        for ans in answers:
            parts.append(f"### 题目 {ans.question_id}\n{ans.answer_text}")
        return "\n\n".join(parts)

    def _call_llm(self, user_prompt: str) -> str:
        """调用大模型并返回原始文本响应"""
        log(f"正在调用 LLM（{self.model}）...", stage="LLM")
        log(f"Prompt 总长度: {len(user_prompt)} 字符", stage="LLM", level=logging.DEBUG)

        start_time = time.time()
        try:
            response = self.client.chat.completions.create(
                model=self.model,
                temperature=self.temperature,
                max_tokens=self.max_tokens,
                messages=[
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": user_prompt},
                ],
            )
            elapsed = time.time() - start_time
            content = response.choices[0].message.content.strip()

            # 记录 token 使用情况
            usage = response.usage
            if usage:
                log(
                    f"LLM 响应完成 | 耗时: {elapsed:.1f}s | "
                    f"输入 tokens: {usage.prompt_tokens} | "
                    f"输出 tokens: {usage.completion_tokens} | "
                    f"总计: {usage.total_tokens}",
                    stage="LLM",
                )
            else:
                log(f"LLM 响应完成 | 耗时: {elapsed:.1f}s", stage="LLM")

            return content

        except Exception as e:
            elapsed = time.time() - start_time
            log(f"LLM 调用失败 | 耗时: {elapsed:.1f}s | 错误: {e}", stage="ERROR", level=logging.ERROR)
            raise

    def _parse_response(self, raw: str, knowledge_items: list[KnowledgeItem]) -> EvaluationReport:
        """解析 LLM 返回的 JSON 并构建 EvaluationReport"""
        log("正在解析 LLM 响应...", stage="LLM", level=logging.DEBUG)

        # 尝试清理可能包含的 markdown 代码块标记
        cleaned = raw
        if cleaned.startswith("```"):
            cleaned = cleaned.split("\n", 1)[1]
        if cleaned.endswith("```"):
            cleaned = cleaned.rsplit("```", 1)[0]
        cleaned = cleaned.strip()

        try:
            data = json.loads(cleaned)
        except json.JSONDecodeError as e:
            log(f"JSON 解析失败: {e}", stage="ERROR", level=logging.ERROR)
            log(f"原始响应前 200 字符: {cleaned[:200]}", stage="ERROR", level=logging.DEBUG)
            raise ValueError(f"LLM 返回的内容无法解析为 JSON: {e}")

        # 构建逐题评估
        evaluations = []
        for item in data.get("question_evaluations", []):
            evaluations.append(QuestionEvaluation(
                question_id=item["question_id"],
                question=item.get("question", ""),
                mastery_level=MasteryLevel(item["mastery_level"]),
                strengths=item.get("strengths", []),
                missing_points=item.get("missing_points", []),
                comment=item.get("comment", ""),
            ))

        # 构建重点复习聚焦
        focus_areas = []
        for area in data.get("focus_areas", []):
            focus_areas.append(FocusArea(
                topic=area["topic"],
                related_questions=area.get("related_questions", []),
                suggestion=area.get("suggestion", ""),
            ))

        # 构建导师追问
        follow_ups = []
        for fq in data.get("follow_up_questions", []):
            follow_ups.append(FollowUpQuestion(
                question_id=fq["question_id"],
                follow_up=fq["follow_up"],
                purpose=fq.get("purpose", ""),
            ))

        # 统计各等级数量
        mastered = sum(1 for e in evaluations if e.mastery_level == MasteryLevel.MASTERED)
        ambiguous = sum(1 for e in evaluations if e.mastery_level == MasteryLevel.AMBIGUOUS)
        weak = sum(1 for e in evaluations if e.mastery_level == MasteryLevel.WEAK)

        log(
            f"解析完成 | 掌握: {mastered} | 模棱两可: {ambiguous} | 薄弱: {weak}",
            stage="LLM",
        )

        return EvaluationReport(
            total_questions=len(knowledge_items),
            mastered_count=mastered,
            ambiguous_count=ambiguous,
            weak_count=weak,
            question_evaluations=evaluations,
            focus_areas=focus_areas,
            follow_up_questions=follow_ups,
            overall_summary=data.get("overall_summary", ""),
        )

    def evaluate(
        self,
        knowledge_items: list[KnowledgeItem],
        student_answers: list[StudentAnswer],
        search_context: str = "",
    ) -> EvaluationReport:
        """
        执行完整评估流程

        Args:
            knowledge_items: 知识库题目列表
            student_answers: 新人回答列表
            search_context: 外部搜索补充资料（预留接口，由外部插件注入）

        Returns:
            EvaluationReport: 结构化评估报告
        """
        log(f"开始评估 | 题目数: {len(knowledge_items)} | 回答数: {len(student_answers)}", stage="LLM")

        kb_text = self._format_knowledge_base(knowledge_items)
        answers_text = self._format_student_answers(student_answers)
        context_text = search_context if search_context else "（无额外搜索资料）"

        if search_context:
            log(f"外部搜索上下文已注入 | 长度: {len(search_context)} 字符", stage="SEARCH")

        user_prompt = EVALUATION_USER_PROMPT_TEMPLATE.format(
            knowledge_base_text=kb_text,
            student_answers_text=answers_text,
            search_context=context_text,
        )

        raw_response = self._call_llm(user_prompt)
        report = self._parse_response(raw_response, knowledge_items)
        return report
