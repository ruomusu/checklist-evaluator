"""
FastAPI 服务入口
- 提供 / 根路径的前端页面（服务切换 + 逐题录入）
- 提供 /api/questions/{service} 获取指定服务的题目列表
- 提供 /evaluate 后端 API（流式 SSE 响应）
- 提供 /health 健康检查接口
"""

import asyncio
import concurrent.futures
import io
import json
import logging
import time
from pathlib import Path
from typing import Optional, AsyncGenerator

from fastapi import FastAPI, File, UploadFile, Form, HTTPException, Body
from fastapi.responses import PlainTextResponse, HTMLResponse, StreamingResponse, JSONResponse
from pydantic import BaseModel

from config import Config
from logger import log, log_separator
from models import KnowledgeItem, StudentAnswer, ReadingGuideItem
from evaluator import Evaluator
from report_generator import ReportGenerator
from knowledge_provider import create_provider

import re

app = FastAPI(
    title="Checklist 自动评估系统",
    version="1.0.0",
    docs_url="/api/docs",
    redoc_url="/api/redoc",
)


# ============================================================
# 知识库按服务加载
# ============================================================

def _get_available_services() -> list[dict]:
    """扫描 knowledge_base 目录，返回可用服务列表"""
    kb_dir = Path(Config.KNOWLEDGE_BASE_DIR)
    services = []
    if kb_dir.exists():
        for f in sorted(kb_dir.glob("*.json")):
            services.append({
                "id": f.stem,
                "name": f.stem.upper(),
            })
    return services


def _load_questions_for_service(service_type: str) -> list[KnowledgeItem]:
    """加载指定服务的知识库题目"""
    kb_dir = Path(Config.KNOWLEDGE_BASE_DIR)
    filepath = kb_dir / f"{service_type.lower()}.json"
    if not filepath.exists():
        raise FileNotFoundError(f"知识库不存在: {service_type}")
    with open(filepath, "r", encoding="utf-8") as f:
        data = json.load(f)
    return [KnowledgeItem(**item) for item in data]


# ============================================================
# API 接口
# ============================================================

@app.get("/health", include_in_schema=False)
def health_check():
    return {"status": "ok"}


@app.get("/api/services", include_in_schema=False)
def get_services():
    """返回可用的服务列表"""
    return JSONResponse(content=_get_available_services())


@app.get("/api/questions/{service_type}", include_in_schema=False)
def get_questions(service_type: str):
    """返回指定服务的题目列表（仅题号和题干）"""
    try:
        items = _load_questions_for_service(service_type)
    except FileNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    return JSONResponse(content=[
        {"question_id": item.question_id, "question": item.question}
        for item in items
    ])


class EvaluateRequest(BaseModel):
    service_type: str
    student_name: str = "新人"
    answers: list[dict]  # [{"question_id": "Q1", "answer_text": "..."}]


async def _stream_evaluate_answers(
    service_type: str,
    student_name: str,
    answers: list[dict],
) -> AsyncGenerator[str, None]:
    """SSE 流式评估"""
    total_start = time.time()
    log_separator("API 逐题评估请求")
    log(f"评估对象: {student_name} | 服务: {service_type} | 答题数: {len(answers)}", stage="INIT")

    yield "event: progress\ndata: 正在加载知识库...\n\n"
    await asyncio.sleep(0.1)

    # 加载该服务的完整知识库
    try:
        all_items = _load_questions_for_service(service_type)
    except FileNotFoundError:
        yield "event: content\ndata: 错误：未找到该服务的知识库\n\n"
        yield "event: done\ndata: \n\n"
        return

    # 只取用户实际作答的题目对应的标准答案
    answered_ids = {a["question_id"] for a in answers}
    knowledge_items = [item for item in all_items if item.question_id in answered_ids]

    student_answers = [
        StudentAnswer(question_id=a["question_id"], answer_text=a["answer_text"])
        for a in answers if a.get("answer_text", "").strip()
    ]

    if not student_answers:
        yield "event: content\ndata: 错误：未收到有效的作答内容\n\n"
        yield "event: done\ndata: \n\n"
        return

    yield "event: progress\ndata: 正在调用大模型评估...\n\n"
    await asyncio.sleep(0.1)

    # 线程池执行阻塞 LLM 调用
    loop = asyncio.get_event_loop()
    with concurrent.futures.ThreadPoolExecutor() as pool:
        evaluator = Evaluator()
        report = await loop.run_in_executor(
            pool, evaluator.evaluate, knowledge_items, student_answers
        )
    report.student_name = student_name
    report.total_questions = len(student_answers)

    # 生成报告
    generator = ReportGenerator()
    markdown_report = generator.generate_markdown(report)
    generator.save_report(report)

    total_elapsed = time.time() - total_start
    log(f"API 评估完成 | 总耗时: {total_elapsed:.1f}s", stage="DONE")

    # 逐行流式输出
    lines = markdown_report.split("\n")
    for i, line in enumerate(lines):
        data_line = line if line else " "
        yield f"event: content\ndata: {data_line}\n\n"
        await asyncio.sleep(0.02)

    yield "event: done\ndata: \n\n"


@app.post("/evaluate", include_in_schema=False)
async def evaluate(request: EvaluateRequest):
    """接收逐题答案 JSON，流式返回评估报告"""
    if not request.answers:
        raise HTTPException(status_code=400, detail="未提交任何答案")

    return StreamingResponse(
        _stream_evaluate_answers(request.service_type, request.student_name, request.answers),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


# ============================================================
# 前端页面
# ============================================================

@app.get("/", response_class=HTMLResponse, include_in_schema=False)
def frontend_page():
    html = Path(__file__).parent.joinpath("frontend.html").read_text(encoding="utf-8")
    return HTMLResponse(content=html, headers={"Cache-Control": "no-cache, no-store, must-revalidate"})
