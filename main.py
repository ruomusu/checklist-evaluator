"""
主入口模块
- 通过 KnowledgeProvider 动态获取标准答案（支持本地/API/数据库）
- 读取新人答卷文件
- 编排完整评估流程
- 结构化日志输出，适配远程 SSH 终端
"""

import logging
import re
import sys
import time

from config import Config
from logger import log, log_separator
from models import KnowledgeItem, StudentAnswer
from evaluator import Evaluator
from report_generator import ReportGenerator
from knowledge_provider import create_provider, KnowledgeProvider


def load_student_answers(filepath: str, knowledge_items: list[KnowledgeItem]) -> list[StudentAnswer]:
    """
    从 Markdown/TXT 文件解析新人回答

    支持的格式：
    ## Q1
    回答内容...

    ## Q2
    回答内容...
    """
    with open(filepath, "r", encoding="utf-8") as f:
        content = f.read()

    answers = []
    # 按 ## Qn 或 ## 题目编号 分割
    pattern = r"##\s*(Q?\d+)\s*\n(.*?)(?=\n##\s*Q?\d+|\Z)"
    matches = re.findall(pattern, content, re.DOTALL)

    for qid, answer_text in matches:
        # 标准化题目编号
        if not qid.startswith("Q"):
            qid = f"Q{qid}"
        answers.append(StudentAnswer(
            question_id=qid,
            answer_text=answer_text.strip(),
        ))

    # 如果正则没匹配到，尝试简单按序对应
    if not answers and knowledge_items:
        paragraphs = [p.strip() for p in content.split("\n\n") if p.strip()]
        for i, para in enumerate(paragraphs):
            if i < len(knowledge_items):
                answers.append(StudentAnswer(
                    question_id=knowledge_items[i].question_id,
                    answer_text=para,
                ))

    return answers


def run_evaluation(
    student_answers_path: str,
    checklist_id: str = None,
    student_name: str = "新人",
    output_filename: str = None,
    provider: KnowledgeProvider = None,
) -> str:
    """
    执行完整评估流程

    Args:
        student_answers_path: 新人答卷文件路径（Markdown/TXT）
        checklist_id: Checklist 标识，用于从外部系统筛选题目集
        student_name: 新人姓名
        output_filename: 自定义报告文件名
        provider: 可选的自定义 KnowledgeProvider 实例

    Returns:
        str: 生成的报告文件路径
    """
    total_start = time.time()

    log_separator("新人 Checklist 自动评估系统")
    log(f"评估对象: {student_name}", stage="INIT")
    log(f"答卷文件: {student_answers_path}", stage="INIT")
    if checklist_id:
        log(f"Checklist ID: {checklist_id}", stage="INIT")

    # 1. 通过 Provider 动态获取知识库
    if provider is None:
        provider = create_provider()

    log(f"正在从知识库获取标准答案（{type(provider).__name__}）...", stage="KB")
    try:
        knowledge_items = provider.get_all_questions(checklist_id)
        log(f"已获取 {len(knowledge_items)} 道题目", stage="KB")
    except Exception as e:
        log(f"知识库获取失败: {e}", stage="ERROR", level=logging.ERROR)
        raise

    # 2. 读取新人答卷
    log(f"正在读取新人答卷...", stage="ANSWER")
    try:
        student_answers = load_student_answers(student_answers_path, knowledge_items)
        log(f"已解析 {len(student_answers)} 道回答", stage="ANSWER")
    except FileNotFoundError:
        log(f"答卷文件不存在: {student_answers_path}", stage="ERROR", level=logging.ERROR)
        raise
    except Exception as e:
        log(f"答卷解析失败: {e}", stage="ERROR", level=logging.ERROR)
        raise

    # 3. 调用大模型评估（搜索由 Tool Calling 在评估过程中自动触发）
    log_separator("调用大模型评估")
    evaluator = Evaluator()
    report = evaluator.evaluate(knowledge_items, student_answers)
    report.student_name = student_name

    # 4. 生成报告
    log_separator("生成评估报告")
    generator = ReportGenerator()
    filepath = generator.save_report(report, output_filename)

    total_elapsed = time.time() - total_start
    log(f"报告已保存: {filepath}", stage="REPORT")
    log(f"评估完成 | 总耗时: {total_elapsed:.1f}s", stage="DONE")

    # 输出报告摘要到终端
    print("\n" + "=" * 60)
    print(generator.generate_markdown(report))

    return filepath


def main():
    """命令行入口"""
    if len(sys.argv) < 2:
        print(
            "用法: python main.py <新人答卷.md> [checklist_id] [新人姓名]\n"
            "\n"
            "说明:\n"
            "  标准答案通过 KNOWLEDGE_PROVIDER 配置的数据源自动获取\n"
            "  支持的数据源: local（本地JSON）, api（外部API）, database（数据库）\n"
            "  外部资料检索由大模型通过 Tool Calling 自动触发，无需手动传入\n"
            "  配置方式: 编辑 .env 文件中的相关参数\n"
            "\n"
            "示例:\n"
            "  python main.py answers.md                    # 使用默认 provider\n"
            "  python main.py answers.md ec2-basics         # 指定 checklist\n"
            "  python main.py answers.md ec2-basics 张三    # 完整参数\n"
        )
        sys.exit(1)

    answers_path = sys.argv[1]
    checklist_id = sys.argv[2] if len(sys.argv) > 2 else None
    name = sys.argv[3] if len(sys.argv) > 3 else "新人"

    try:
        run_evaluation(answers_path, checklist_id, name)
    except KeyboardInterrupt:
        log("\n用户中断执行", stage="ERROR", level=logging.WARNING)
        sys.exit(130)
    except Exception as e:
        log(f"执行异常终止: {e}", stage="ERROR", level=logging.ERROR)
        sys.exit(1)


if __name__ == "__main__":
    main()
