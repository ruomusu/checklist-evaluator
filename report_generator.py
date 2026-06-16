"""
报告生成模块
- 将 EvaluationReport 转换为极简 Markdown 格式
- 只展示逐题判定和缺失点，帮导师快速定位盲区
"""

import os
from datetime import datetime, timezone, timedelta

from config import Config
from models import EvaluationReport, MasteryLevel

# 北京时间 UTC+8
_BJT = timezone(timedelta(hours=8))


class ReportGenerator:
    """将评估报告输出为精简 Markdown 文件"""

    def __init__(self, output_dir: str = None):
        self.output_dir = output_dir or Config.OUTPUT_DIR
        os.makedirs(self.output_dir, exist_ok=True)

    def _level_emoji(self, level: MasteryLevel) -> str:
        mapping = {
            MasteryLevel.EXCELLENT: "✅",
            MasteryLevel.SATISFACTORY: "⚠️",
            MasteryLevel.FAIL: "❌",
        }
        return mapping.get(level, "")

    def generate_markdown(self, report: EvaluationReport, student_answers: list = None) -> str:
        """生成按评级分组的 Markdown 报告"""
        # 构建答案查找字典
        answers_map = {}
        if student_answers:
            for sa in student_answers:
                qid = sa.question_id if hasattr(sa, 'question_id') else sa.get('question_id', '')
                text = sa.answer_text if hasattr(sa, 'answer_text') else sa.get('answer_text', '')
                answers_map[qid] = text

        lines = []

        lines.append(f"# Checklist 评估报告 — {report.student_name}")
        lines.append("")
        lines.append(f"评估时间: {datetime.now(_BJT).strftime('%Y-%m-%d %H:%M')}")
        lines.append(f"总计 {report.total_questions} 题 | "
                     f"✅ Excellent (85%+) {report.excellent_count} | "
                     f"⚠️ Satisfactory (60%-84%) {report.satisfactory_count} | "
                     f"❌ Fail (<60%) {report.fail_count}")
        lines.append("")
        lines.append("---")
        lines.append("")

        # ═══ Excellent 优秀区 ═══
        excellent_evals = [e for e in report.question_evaluations if e.mastery_level == MasteryLevel.EXCELLENT]
        if excellent_evals:
            lines.append(f"## ✅ Excellent 优秀区（{len(excellent_evals)} 题）")
            lines.append("")
            if report.mastered_has_global_links:
                lines.append("💡 提示：部分题目使用了全球区链接，建议替换为中国区链接")
                lines.append("")
            for ev in excellent_evals:
                if ev.question:
                    lines.append(f"**{ev.question_id}: {ev.question}** — Excellent ({ev.score}%) ✅")
                else:
                    lines.append(f"**{ev.question_id}** — Excellent ({ev.score}%) ✅")
                lines.append("")
                # 显示学生作答
                if ev.question_id in answers_map:
                    lines.append("**📝 学生作答**")
                    lines.append("")
                    lines.append(f"> {answers_map[ev.question_id]}")
                    lines.append("")
                if ev.strengths:
                    lines.append("**🌟 答题亮点**")
                    for s in ev.strengths:
                        lines.append(f"- {s}")
                    lines.append("")
                if ev.missing_points:
                    lines.append("**⚠️ 轻微遗漏**")
                    for m in ev.missing_points:
                        lines.append(f"- {m}")
                    lines.append("")

        # ═══ Satisfactory 提示区 ═══
        satisfactory_evals = [e for e in report.question_evaluations if e.mastery_level == MasteryLevel.SATISFACTORY]
        if satisfactory_evals:
            lines.append(f"## ⚠️ Satisfactory 提示区（{len(satisfactory_evals)} 题）")
            lines.append("")
            for ev in satisfactory_evals:
                self._render_question(lines, ev, answers_map)

        # ═══ Fail 警示区 ═══
        fail_evals = [e for e in report.question_evaluations if e.mastery_level == MasteryLevel.FAIL]
        if fail_evals:
            lines.append(f"## ❌ Fail 警示区（{len(fail_evals)} 题）")
            lines.append("")
            for ev in fail_evals:
                self._render_question(lines, ev, answers_map)

        # ═══ 推荐阅读 ═══
        if report.reading_guide:
            lines.append("---")
            lines.append("")
            lines.append("### 🎯 推荐阅读与提升指南")
            lines.append("")
            for item in report.reading_guide:
                lines.append(f"**{item.question_id}: {item.question_summary}**")
                for res in item.resources:
                    lines.append(f"- {res}")
                lines.append("")

        return "\n".join(lines)

    def _render_question(self, lines: list, ev, answers_map: dict = None) -> None:
        """渲染单题详情"""
        if answers_map is None:
            answers_map = {}
        emoji = self._level_emoji(ev.mastery_level)
        if ev.question:
            lines.append(f"**{ev.question_id}: {ev.question}** — {ev.mastery_level.value} ({ev.score}%) {emoji}")
        else:
            lines.append(f"**{ev.question_id}** — {ev.mastery_level.value} ({ev.score}%) {emoji}")
        lines.append("")
        # 显示学生作答
        if ev.question_id in answers_map:
            lines.append("**📝 学生作答**")
            lines.append("")
            lines.append(f"> {answers_map[ev.question_id]}")
            lines.append("")
        if ev.strengths:
            lines.append("**🌟 答题亮点**")
            for s in ev.strengths:
                lines.append(f"- {s}")
            lines.append("")
        if ev.missing_points:
            lines.append("**⚠️ 知识盲区**")
            for point in ev.missing_points:
                lines.append(f"- {point}")
            lines.append("")
        if ev.notes:
            lines.append(f"💡 {ev.notes}")
            lines.append("")

    def save_report(self, report: EvaluationReport, filename: str = None, student_answers: list = None) -> str:
        if not filename:
            timestamp = datetime.now(_BJT).strftime("%Y%m%d_%H%M%S")
            filename = f"evaluation_report_{timestamp}.md"

        filepath = os.path.join(self.output_dir, filename)
        content = self.generate_markdown(report, student_answers)

        with open(filepath, "w", encoding="utf-8") as f:
            f.write(content)

        return filepath
