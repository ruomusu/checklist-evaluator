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

    def generate_markdown(self, report: EvaluationReport) -> str:
        """生成极简 Markdown 报告"""
        lines = []

        lines.append(f"# Checklist 评估报告 — {report.student_name}")
        lines.append("")
        lines.append(f"评估时间: {datetime.now(_BJT).strftime('%Y-%m-%d %H:%M')}")
        lines.append(f"总计 {report.total_questions} 题 | "
                     f"✅ Excellent (85%+) {report.excellent_count} | "
                     f"⚠️ Satisfactory (60%-84%) {report.satisfactory_count} | "
                     f"❌ Fail (<60%) {report.fail_count}")
        lines.append("")

        # 聚合 Excellent 题目（一行展示）
        if report.mastered_ids:
            lines.append(f"✅ **Excellent 题目**：{', '.join(report.mastered_ids)}")
            if report.mastered_has_global_links:
                lines.append("💡 提示：部分 Excellent 题目使用了全球区链接，建议替换为中国区链接")
            lines.append("")

        lines.append("---")
        lines.append("")

        # 只展示 Satisfactory 和 Fail 的题目
        for ev in report.question_evaluations:
            emoji = self._level_emoji(ev.mastery_level)
            if ev.question:
                lines.append(f"**{ev.question_id}: {ev.question}** {ev.mastery_level.value} ({ev.score}%) {emoji}")
            else:
                lines.append(f"**{ev.question_id}** {ev.mastery_level.value} ({ev.score}%) {emoji}")
            lines.append("")
            # 亮点模块（必填）
            if ev.strengths:
                lines.append("**🌟 答题亮点**")
                for s in ev.strengths:
                    lines.append(f"- {s}")
                lines.append("")
            # 盲区模块
            if ev.missing_points:
                lines.append("**⚠️ 知识盲区**")
                for point in ev.missing_points:
                    lines.append(f"- {point}")
                lines.append("")
            if ev.notes:
                lines.append(f"- 💡 {ev.notes}")
                lines.append("")

        # 参考文献板块（仅在有工具检索来源时输出）
        if report.references:
            lines.append("---")
            lines.append("")
            lines.append("### 📚 参考资料 (References)")
            lines.append("")
            for ref in report.references:
                lines.append(ref)
            lines.append("")

        return "\n".join(lines)

    def save_report(self, report: EvaluationReport, filename: str = None) -> str:
        if not filename:
            timestamp = datetime.now(_BJT).strftime("%Y%m%d_%H%M%S")
            filename = f"evaluation_report_{timestamp}.md"

        filepath = os.path.join(self.output_dir, filename)
        content = self.generate_markdown(report)

        with open(filepath, "w", encoding="utf-8") as f:
            f.write(content)

        return filepath
