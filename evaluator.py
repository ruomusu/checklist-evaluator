"""
评估引擎模块
- 负责组装 Prompt、调用大模型、解析返回结果
- 支持 Tool Calling：大模型可主动调用内部知识库和外部文档搜索工具
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
    ReadingGuideItem,
    EvaluationReport,
    MasteryLevel,
)
from prompts import SYSTEM_PROMPT, EVALUATION_USER_PROMPT_TEMPLATE
from search_tools import TOOL_DEFINITIONS, TOOL_FUNCTIONS


# Tool Calling 最大循环次数，防止无限调用
MAX_TOOL_ROUNDS = 5


class Evaluator:
    """
    核心评估引擎
    职责：整合知识库、新人答案，通过 Tool Calling 让大模型主动检索补充资料，
          最终生成评估报告
    """

    def __init__(self):
        llm_config = Config.get_llm_config()
        self.client = OpenAI(
            api_key=llm_config["api_key"],
            base_url=llm_config["base_url"],
        )
        self.model = llm_config["model"]
        self.temperature = Config.TEMPERATURE
        self.max_tokens = Config.MAX_TOKENS
        self.enable_tools = Config.ENABLE_TOOL_CALLING
        log(
            f"Evaluator 初始化完成 | 提供者: {Config.LLM_PROVIDER} | "
            f"模型: {self.model} | 温度: {self.temperature} | "
            f"Tool Calling: {'启用' if self.enable_tools else '禁用'}",
            stage="INIT",
        )

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

    def _call_llm_with_tools(self, user_prompt: str) -> str:
        """
        调用大模型，支持 Tool Calling 循环

        流程：
        1. 发送 messages + tools 定义给 LLM
        2. 如果 LLM 返回 tool_calls，执行对应工具函数，将结果作为 tool message 追加
        3. 重复直到 LLM 返回最终文本响应（或达到最大轮次）

        Returns:
            str: LLM 最终的文本响应
        """
        log(f"正在调用 LLM（{self.model}）...", stage="LLM")
        log(f"Prompt 总长度: {len(user_prompt)} 字符", stage="LLM", level=logging.DEBUG)

        messages = [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": user_prompt},
        ]

        # 构建请求参数
        request_kwargs = {
            "model": self.model,
            "temperature": self.temperature,
            "max_tokens": self.max_tokens,
            "messages": messages,
        }

        # 如果启用了 Tool Calling，附加工具定义
        if self.enable_tools:
            request_kwargs["tools"] = TOOL_DEFINITIONS
            request_kwargs["tool_choice"] = "auto"

        total_start = time.time()
        tool_round = 0

        while True:
            try:
                start_time = time.time()
                response = self.client.chat.completions.create(**request_kwargs)
                elapsed = time.time() - start_time

                # 记录 token 使用
                usage = response.usage
                if usage:
                    log(
                        f"LLM 响应 | 耗时: {elapsed:.1f}s | "
                        f"输入: {usage.prompt_tokens} | "
                        f"输出: {usage.completion_tokens} | "
                        f"总计: {usage.total_tokens}",
                        stage="LLM",
                    )
                else:
                    log(f"LLM 响应 | 耗时: {elapsed:.1f}s", stage="LLM")

            except Exception as e:
                elapsed = time.time() - start_time
                log(f"LLM 调用失败 | 耗时: {elapsed:.1f}s | 错误: {e}", stage="ERROR", level=logging.ERROR)
                raise

            choice = response.choices[0]
            message = choice.message

            # 如果没有 tool_calls，说明 LLM 已给出最终响应
            if not message.tool_calls:
                total_elapsed = time.time() - total_start
                log(f"LLM 评估完成 | 总耗时: {total_elapsed:.1f}s | 工具调用轮次: {tool_round}", stage="LLM")
                return message.content.strip()

            # 处理 tool_calls
            tool_round += 1
            if tool_round > MAX_TOOL_ROUNDS:
                log(f"Tool Calling 达到最大轮次({MAX_TOOL_ROUNDS})，强制结束", stage="LLM", level=logging.WARNING)
                # 移除 tools 定义，强制 LLM 给出最终回答
                request_kwargs.pop("tools", None)
                request_kwargs.pop("tool_choice", None)
                messages.append({"role": "assistant", "content": "", "tool_calls": None})
                messages.append({"role": "user", "content": "请直接输出最终的 JSON 评估结果。"})
                request_kwargs["messages"] = messages
                continue

            # 将 assistant 的 tool_calls 消息追加到对话
            messages.append(message.model_dump())

            # 逐个执行工具调用
            for tool_call in message.tool_calls:
                func_name = tool_call.function.name
                func_args = json.loads(tool_call.function.arguments)

                log(f"[Tool Call] {func_name}({func_args})", stage="SEARCH")

                # 调用对应工具函数
                tool_func = TOOL_FUNCTIONS.get(func_name)
                if tool_func:
                    result = tool_func(**func_args)
                else:
                    result = f"未知工具: {func_name}"
                    log(f"[Tool] 未知工具名: {func_name}", stage="ERROR", level=logging.WARNING)

                # 将工具返回结果追加到对话
                messages.append({
                    "role": "tool",
                    "tool_call_id": tool_call.id,
                    "content": result if result else "（无检索结果）",
                })

            # 更新 messages 后继续循环
            request_kwargs["messages"] = messages

    def _call_llm_simple(self, user_prompt: str) -> str:
        """不带 Tool Calling 的简单调用（fallback）"""
        log(f"正在调用 LLM（{self.model}，无工具模式）...", stage="LLM")

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

            usage = response.usage
            if usage:
                log(
                    f"LLM 响应完成 | 耗时: {elapsed:.1f}s | "
                    f"输入: {usage.prompt_tokens} | "
                    f"输出: {usage.completion_tokens} | "
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

        # 构建逐题评估（只包含 Satisfactory 和 Fail）
        evaluations = []
        for item in data.get("question_evaluations", []):
            evaluations.append(QuestionEvaluation(
                question_id=item["question_id"],
                question=item.get("question", ""),
                mastery_level=MasteryLevel(item["mastery_level"]),
                score=item.get("score", 0),
                strengths=item.get("strengths", []),
                missing_points=item.get("missing_points", []),
                notes=item.get("notes", ""),
            ))

        # 提取 Excellent 题目信息
        mastered_ids = data.get("mastered_ids", [])
        mastered_has_global_links = data.get("mastered_has_global_links", False)

        # 统计各等级数量（从实际 evaluations 计数，确保准确）
        excellent = sum(1 for e in evaluations if e.mastery_level == MasteryLevel.EXCELLENT)
        satisfactory = sum(1 for e in evaluations if e.mastery_level == MasteryLevel.SATISFACTORY)
        fail = sum(1 for e in evaluations if e.mastery_level == MasteryLevel.FAIL)

        log(
            f"解析完成 | Excellent: {excellent} | Satisfactory: {satisfactory} | Fail: {fail}",
            stage="LLM",
        )

        return EvaluationReport(
            total_questions=len(knowledge_items),
            excellent_count=excellent,
            satisfactory_count=satisfactory,
            fail_count=fail,
            mastered_ids=mastered_ids,
            mastered_has_global_links=mastered_has_global_links,
            question_evaluations=evaluations,
            reading_guide=[
                ReadingGuideItem(**item) for item in data.get("reading_guide", [])
            ],
        )

    def evaluate(
        self,
        knowledge_items: list[KnowledgeItem],
        student_answers: list[StudentAnswer],
    ) -> EvaluationReport:
        """
        执行完整评估流程

        Args:
            knowledge_items: 知识库题目列表
            student_answers: 新人回答列表

        Returns:
            EvaluationReport: 结构化评估报告
        """
        log(f"开始评估 | 题目数: {len(knowledge_items)} | 回答数: {len(student_answers)}", stage="LLM")

        kb_text = self._format_knowledge_base(knowledge_items)
        answers_text = self._format_student_answers(student_answers)

        user_prompt = EVALUATION_USER_PROMPT_TEMPLATE.format(
            knowledge_base_text=kb_text,
            student_answers_text=answers_text,
        )

        # 根据配置选择是否启用 Tool Calling
        if self.enable_tools:
            raw_response = self._call_llm_with_tools(user_prompt)
        else:
            raw_response = self._call_llm_simple(user_prompt)

        report = self._parse_response(raw_response, knowledge_items)
        return report
