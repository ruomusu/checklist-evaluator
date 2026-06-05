"""
报告生成模块
- 将 EvaluationReport 转换为可读的 Markdown 格式报告
- 支持输出到文件或标准输出
"""

import os
from datetime import datetime

from config import Config
from models import EvaluationReport, MasteryLevel


class ReportGenerator:
    """将评估报告输出为结构化 Markdown 文件"""

    def __init__(self, output_dir: str = None):
        self.output_dir = output_dir or Config.OUTPUT_DIR
        os.makedirs(self.output_dir, exist_ok=True)

    def _level_emoji(self, level: MasteryLevel) -> str:
        """为掌握等级添加可视化标识"""
        mapping = {
            MasteryLevel.MASTERED: "✅",
            MasteryLevel.AMBIGUOUS: "⚠️",
            MasteryLevel.WEAK: "❌",
        }
        return mapping.get(level, "")

    def generate_markdown(self, report: EvaluationReport) -> str:
        """生成 Markdown 格式报告文本"""
        lines = []

        # 标题与概览
        lines.append(f"# 新人 Checklist 评估报告")
        lines.append(f"")
        lines.append(f"- **姓名**: {report.student_name}")
        lines.append(f"- **评估时间**: {datetime.now().strftime('%Y-%m-%d %H:%M')}")
        lines.append(f"- **总题目数**: {report.total_questions}")
        lines.append(f"- **掌握**: {report.mastered_count} 题 | **模棱两可**: {report.ambiguous_count} 题 | **薄弱**: {report.weak_count} 题")
        lines.append("")

        # 总体评价
        lines.append("## 📋 总体评价")
        lines.append("")
        lines.append(report.overall_summary)
        lines.append("")

        # 板块一：逐题掌握情况
        lines.append("---")
        lines.append("## 一、逐题掌握情况判定")
        lines.append("")
        for ev in report.question_evaluations:
            emoji = self._level_emoji(ev.mastery_level)
            lines.append(f"### 题目 {ev.question_id}: {ev.question}")
            lines.append(f"")
            lines.append(f"**判定**: {emoji} {ev.mastery_level.value}")
            lines.append("")
            if ev.strengths:
                lines.append("**亮点：**")
                for s in ev.strengths:
                    lines.append(f"- {s}")
                lines.append("")
            if ev.missing_points:
                lines.append("**缺失关键点：**")
                for m in ev.missing_points:
                    lines.append(f"- {m}")
                lines.append("")
            if ev.comment:
                lines.append(f"**评语**: {ev.comment}")
                lines.append("")

        # 板块二：重点复习聚焦
        lines.append("---")
        lines.append("## 二、重点复习聚焦")
        lines.append("")
        if report.focus_areas:
            for area in report.focus_areas:
                lines.append(f"### 🎯 {area.topic}")
                lines.append(f"- **关联题目**: {', '.join(area.related_questions)}")
                lines.append(f"- **复习建议**: {area.suggestion}")
                lines.append("")
        else:
            lines.append("暂无需要重点复习的领域，表现良好！")
            lines.append("")

        # 板块三：导师面谈追问建议
        lines.append("---")
        lines.append("## 三、导师面谈追问建议")
        lines.append("")
        if report.follow_up_questions:
            for fq in report.follow_up_questions:
                lines.append(f"**针对题目 {fq.question_id}：**")
                lines.append(f"- 追问: {fq.follow_up}")
                lines.append(f"- 目的: {fq.purpose}")
                lines.append("")
        else:
            lines.append("新人表现优秀，暂无需要追问的内容。")
            lines.append("")

        return "\n".join(lines)

    def save_report(self, report: EvaluationReport, filename: str = None) -> str:
        """
        保存报告到文件

        Args:
            report: 评估报告对象
            filename: 自定义文件名，默认按时间生成

        Returns:
            str: 保存的文件路径
        """
        if not filename:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"evaluation_report_{timestamp}.md"

        filepath = os.path.join(self.output_dir, filename)
        content = self.generate_markdown(report)

        with open(filepath, "w", encoding="utf-8") as f:
            f.write(content)

        return filepath
