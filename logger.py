"""
日志模块
- 为远程 SSH 执行优化的结构化日志输出
- 支持彩色终端显示和纯文本文件记录
- 提供统一的日志接口供所有模块调用
"""

import logging
import os
import sys
from datetime import datetime
from pathlib import Path

from config import Config


class ColorFormatter(logging.Formatter):
    """
    终端彩色日志格式化器
    在 SSH 远程终端中仍能正常显示颜色（依赖终端 ANSI 支持）
    """

    COLORS = {
        logging.DEBUG: "\033[36m",     # 青色
        logging.INFO: "\033[32m",      # 绿色
        logging.WARNING: "\033[33m",   # 黄色
        logging.ERROR: "\033[31m",     # 红色
        logging.CRITICAL: "\033[35m",  # 紫色
    }
    RESET = "\033[0m"
    BOLD = "\033[1m"

    # 阶段图标映射
    STAGE_ICONS = {
        "INIT": "🚀",
        "KB": "📖",
        "ANSWER": "📝",
        "SEARCH": "🔍",
        "LLM": "🤖",
        "REPORT": "📊",
        "DONE": "✅",
        "ERROR": "❌",
    }

    def format(self, record: logging.LogRecord) -> str:
        color = self.COLORS.get(record.levelno, self.RESET)
        # 提取阶段标识
        stage = getattr(record, "stage", "")
        icon = self.STAGE_ICONS.get(stage, "")

        timestamp = datetime.fromtimestamp(record.created).strftime("%H:%M:%S")
        level = record.levelname.ljust(7)

        if icon:
            prefix = f"{color}{self.BOLD}[{timestamp}]{self.RESET} {icon} "
        else:
            prefix = f"{color}{self.BOLD}[{timestamp}] {level}{self.RESET} "

        message = f"{prefix}{record.getMessage()}"

        if record.exc_info:
            message += "\n" + self.formatException(record.exc_info)

        return message


class PlainFormatter(logging.Formatter):
    """纯文本日志格式化器，用于文件记录"""

    def format(self, record: logging.LogRecord) -> str:
        timestamp = datetime.fromtimestamp(record.created).strftime("%Y-%m-%d %H:%M:%S")
        stage = getattr(record, "stage", "-")
        return f"[{timestamp}] [{record.levelname:7s}] [{stage:6s}] {record.getMessage()}"


def setup_logger(
    name: str = "checklist_evaluator",
    log_to_file: bool = True,
    log_dir: str = None,
) -> logging.Logger:
    """
    创建并配置 Logger 实例

    Args:
        name: Logger 名称
        log_to_file: 是否同时输出到日志文件
        log_dir: 日志文件目录，默认为 ./logs

    Returns:
        配置好的 Logger 实例
    """
    logger = logging.getLogger(name)

    # 避免重复添加 handler
    if logger.handlers:
        return logger

    logger.setLevel(logging.DEBUG)

    # 终端 Handler（彩色输出）
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(logging.INFO)
    console_handler.setFormatter(ColorFormatter())
    logger.addHandler(console_handler)

    # 文件 Handler（完整日志记录）
    if log_to_file:
        log_dir = log_dir or os.path.join(os.path.dirname(__file__), "logs")
        Path(log_dir).mkdir(parents=True, exist_ok=True)

        log_filename = datetime.now().strftime("eval_%Y%m%d_%H%M%S.log")
        file_handler = logging.FileHandler(
            os.path.join(log_dir, log_filename),
            encoding="utf-8",
        )
        file_handler.setLevel(logging.DEBUG)
        file_handler.setFormatter(PlainFormatter())
        logger.addHandler(file_handler)

    return logger


# 全局 Logger 实例
logger = setup_logger()


def log(message: str, stage: str = "", level: int = logging.INFO):
    """
    便捷日志函数

    Args:
        message: 日志消息
        stage: 处理阶段标识（INIT/KB/ANSWER/SEARCH/LLM/REPORT/DONE/ERROR）
        level: 日志级别
    """
    logger.log(level, message, extra={"stage": stage})


def log_separator(title: str = ""):
    """打印分隔线，便于在远程终端中区分不同阶段"""
    sep = "─" * 50
    if title:
        log(f"\n{sep}\n  {title}\n{sep}", stage="INIT")
    else:
        log(sep)
