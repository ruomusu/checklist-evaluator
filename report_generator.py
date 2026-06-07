"""
报告生成模块
- 将 EvaluationReport 转换为极简 Markdown 格式
- 只展示逐题判定和缺失点，帮导师快速定位盲区
"""

import os
from datetime import datetime

from config import Config
from models import EvaluationReport, MasteryLevel


class ReportGenerator:
    """将评估报告输出为精简 Markdown 文件"""

    def __init__(self, output_dir: str = None):
        self.output_dir = output_dir or Config.OUTPUT_DIR
        os.makedirs(self.output_dir, exist_ok=True)

    def _level_emoji(self, level: MasteryLevel) -> str:
        mapping = {
            MasteryLevel.MASTERED: "✅",
            MasteryLevel.AMBIGUOUS: "⚠️",
            MasteryLevel.WEAK: "❌",
        }
        return mapping.get(level, "")

    def generate_markdown(self, report: EvaluationReport) -> str:
        """生成极简 Markdown 报告"""
        lines = []

        lines.append(f"# Checklist 评估报告 — {report.student_name}")
        lines.append("")
        lines.append(f"评估时间: {datetime.now().strftime('%Y-%m-%d %H:%M')}")
        lines.append(f"总计 {report.total_questions} 题 | "
                     f"✅ 掌握 {report.mastered_count} | "
                     f"⚠️ 模棱两可 {report.ambiguous_count} | "
                     f"❌ 薄弱 {report.weak_count}")
        lines.append("")
        lines.append("---")
        lines.append("")

        for ev in report.question_evaluations:
            emoji = self._level_emoji(ev.mastery_level)
            lines.append(f"**{ev.question_id}** {emoji} {ev.mastery_level.value}")
            if ev.missing_points:
                for point in ev.missing_points:
                    lines.append(f"- {point}")
            if ev.notes:
                lines.append(f"- 💡 {ev.notes}")
            lines.append("")

        # 参考文献板块
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
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"evaluation_report_{timestamp}.md"

        filepath = os.path.join(self.output_dir, filename)
        content = self.generate_markdown(report)

        with open(filepath, "w", encoding="utf-8") as f:
            f.write(content)

        return filepath
