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

from fastapi import FastAPI, File, UploadFile, Form, HTTPException, Body, Depends
from fastapi.responses import PlainTextResponse, HTMLResponse, StreamingResponse, JSONResponse
from pydantic import BaseModel

from config import Config
from logger import log, log_separator
from models import KnowledgeItem, StudentAnswer, ReadingGuideItem
from evaluator import Evaluator
from report_generator import ReportGenerator
from knowledge_provider import create_provider
from storage import save_report as db_save_report, get_history as db_get_history, toggle_highlight as db_toggle_highlight
from storage import register_user as db_register_user, verify_user as db_verify_user, get_user as db_get_user, get_all_users as db_get_all_users
from storage import get_all_history as db_get_all_history
from auth import create_access_token, get_current_user

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
    markdown_report = generator.generate_markdown(report, student_answers)
    generator.save_report(report, student_answers=student_answers)

    # 自动保存到 DynamoDB
    saved_sort_key = ''
    try:
        item = db_save_report(
            trainee_name=student_name,
            service_type=service_type,
            report_data=markdown_report,
            is_highlighted=False,
        )
        saved_sort_key = item.get("service_timestamp", "")
    except Exception as e:
        log(f"DynamoDB 自动保存失败（非致命）: {e}", stage="ERROR", level=logging.WARNING)

    total_elapsed = time.time() - total_start
    log(f"API 评估完成 | 总耗时: {total_elapsed:.1f}s", stage="DONE")

    # 逐行流式输出
    lines = markdown_report.split("\n")
    for i, line in enumerate(lines):
        data_line = line if line else " "
        yield f"event: content\ndata: {data_line}\n\n"
        await asyncio.sleep(0.02)

    yield "event: done" + "\n" + "data: " + saved_sort_key + "\n\n"


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

class SaveReportRequest(BaseModel):
    trainee_name: str
    service_type: str
    report_data: str
    is_highlighted: bool = False


@app.post("/api/save-report", include_in_schema=False)
async def save_report_endpoint(request: SaveReportRequest):
    """保存评估报告到 DynamoDB"""
    try:
        item = db_save_report(
            trainee_name=request.trainee_name,
            service_type=request.service_type,
            report_data=request.report_data,
            is_highlighted=request.is_highlighted,
        )
        return JSONResponse(content={"status": "ok", "sort_key": item["service_timestamp"]})
    except Exception as e:
        log(f"DynamoDB 保存失败: {e}", stage="ERROR", level=logging.ERROR)
        raise HTTPException(status_code=500, detail=f"保存失败: {e}")


class ToggleHighlightRequest(BaseModel):
    trainee_name: str
    service_timestamp: str


# ========================
# 认证相关 API
# ========================

class RegisterRequest(BaseModel):
    username: str
    password: str


class LoginRequest(BaseModel):
    username: str
    password: str


@app.post("/api/auth/register", include_in_schema=False)
async def register(request: RegisterRequest):
    """用户注册"""
    try:
        user = db_register_user(request.username, request.password)
        return JSONResponse(content={"status": "ok", "user": user})
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        log(f"注册失败: {e}", stage="ERROR", level=logging.ERROR)
        raise HTTPException(status_code=500, detail=f"注册失败: {e}")


@app.post("/api/auth/login", include_in_schema=False)
async def login(request: LoginRequest):
    """用户登录"""
    try:
        if not db_verify_user(request.username, request.password):
            raise HTTPException(status_code=401, detail="用户名或密码错误")

        user = db_get_user(request.username)
        token = create_access_token({"sub": request.username, "role": user.get("role", "user")})

        return JSONResponse(content={
            "status": "ok",
            "token": token,
            "user": user,
        })
    except HTTPException:
        raise
    except Exception as e:
        log(f"登录失败: {e}", stage="ERROR", level=logging.ERROR)
        raise HTTPException(status_code=500, detail=f"登录失败: {e}")


@app.get("/api/auth/me", include_in_schema=False)
async def get_me(current_user: dict = Depends(get_current_user)):
    """获取当前登录用户信息"""
    return JSONResponse(content={"status": "ok", "user": current_user})


@app.get("/api/auth/users", include_in_schema=False)
async def get_users(current_user: dict = Depends(get_current_user)):
    """获取所有用户列表（仅管理员）"""
    if current_user.get("role") != "admin":
        raise HTTPException(status_code=403, detail="仅管理员可访问")

    users = db_get_all_users()
    return JSONResponse(content={"status": "ok", "users": users})


@app.get("/api/admin/all-history", include_in_schema=False)
async def get_all_history_endpoint(current_user: dict = Depends(get_current_user)):
    """获取所有用户的所有历史记录（仅管理员）"""
    if current_user.get("role") != "admin":
        raise HTTPException(status_code=403, detail="仅管理员可访问")

    try:
        items = db_get_all_history()
        import json
        from decimal import Decimal

        class DecimalEncoder(json.JSONEncoder):
            def default(self, o):
                if isinstance(o, Decimal):
                    return int(o) if o == int(o) else float(o)
                return super().default(o)

        clean_items = json.loads(json.dumps(items, cls=DecimalEncoder))
        return JSONResponse(content={"status": "ok", "items": clean_items})
    except Exception as e:
        log(f"DynamoDB 查询失败: {e}", stage="ERROR", level=logging.ERROR)
        raise HTTPException(status_code=500, detail=f"查询失败: {e}")


@app.patch("/api/toggle-highlight", include_in_schema=False)
async def toggle_highlight_endpoint(request: ToggleHighlightRequest):
    """翻转某条记录的高光状态"""
    try:
        new_state = db_toggle_highlight(request.trainee_name, request.service_timestamp)
        return JSONResponse(content={"status": "ok", "is_highlighted": new_state})
    except Exception as e:
        log(f"DynamoDB toggle 失败: {e}", stage="ERROR", level=logging.ERROR)
        raise HTTPException(status_code=500, detail=f"操作失败: {e}")


@app.get("/api/history/{trainee_name}", include_in_schema=False)
async def get_history_endpoint(trainee_name: str, current_user: dict = Depends(get_current_user)):
    """查询某新人的所有历史评估记录"""
    # 权限检查：普通用户只能查看自己的记录，管理员可以查看任何用户的记录
    log(f"History 权限检查 | token_user='{current_user.get('trainee_name')}' | 请求trainee='{trainee_name}' | role={current_user.get('role')}", stage="KB")
    if current_user.get("role") != "admin" and current_user.get("trainee_name") != trainee_name:
        raise HTTPException(status_code=403, detail=f"无权访问: token用户='{current_user.get('trainee_name')}', 请求='{trainee_name}'")
    
    try:
        items = db_get_history(trainee_name)
        import json
        from decimal import Decimal

        class DecimalEncoder(json.JSONEncoder):
            def default(self, o):
                if isinstance(o, Decimal):
                    return int(o) if o == int(o) else float(o)
                return super().default(o)

        clean_items = json.loads(json.dumps(items, cls=DecimalEncoder))
        return JSONResponse(content=clean_items)
    except Exception as e:
        log(f"DynamoDB 查询失败: {e}", stage="ERROR", level=logging.ERROR)
        raise HTTPException(status_code=500, detail=f"查询失败: {e}")


# ============================================================
# 知识库管理 API（仅管理员）
# ============================================================

class UpdateQuestionRequest(BaseModel):
    question: str
    reference_answer: str
    reference_links: list[str] = []


@app.get("/api/admin/knowledge/{service_type}", include_in_schema=False)
async def get_knowledge_full(service_type: str, current_user: dict = Depends(get_current_user)):
    """获取指定服务的完整知识库内容（含标准答案，仅管理员）"""
    if current_user.get("role") != "admin":
        raise HTTPException(status_code=403, detail="仅管理员可访问")
    try:
        items = _load_questions_for_service(service_type)
    except FileNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    return JSONResponse(content=[item.model_dump() for item in items])


@app.put("/api/admin/knowledge/{service_type}/{question_id}", include_in_schema=False)
async def update_question(
    service_type: str,
    question_id: str,
    request: UpdateQuestionRequest,
    current_user: dict = Depends(get_current_user),
):
    """更新指定题目的内容（仅管理员）"""
    if current_user.get("role") != "admin":
        raise HTTPException(status_code=403, detail="仅管理员可访问")

    kb_dir = Path(Config.KNOWLEDGE_BASE_DIR)
    filepath = kb_dir / f"{service_type.lower()}.json"
    if not filepath.exists():
        raise HTTPException(status_code=404, detail=f"知识库不存在: {service_type}")

    # 读取现有数据
    with open(filepath, "r", encoding="utf-8") as f:
        data = json.load(f)

    # 找到对应题目并更新
    found = False
    for item in data:
        if item["question_id"] == question_id:
            item["question"] = request.question
            item["reference_answer"] = request.reference_answer
            item["reference_links"] = request.reference_links
            found = True
            break

    if not found:
        raise HTTPException(status_code=404, detail=f"题目不存在: {question_id}")

    # 写回文件
    with open(filepath, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

    log(f"管理员 {current_user.get('trainee_name')} 更新了 {service_type}/{question_id}", stage="ADMIN")
    return JSONResponse(content={"status": "ok", "message": f"题目 {question_id} 已更新"})


@app.get("/", response_class=HTMLResponse, include_in_schema=False)
def frontend_page():
    html = Path(__file__).parent.joinpath("frontend.html").read_text(encoding="utf-8")
    return HTMLResponse(content=html, headers={"Cache-Control": "no-cache, no-store, must-revalidate"})


@app.get("/landing", response_class=HTMLResponse, include_in_schema=False)
def landing_page():
    html = Path(__file__).parent.joinpath("landing.html").read_text(encoding="utf-8")
    return HTMLResponse(content=html, headers={"Cache-Control": "no-cache, no-store, must-revalidate"})


@app.get("/login", response_class=HTMLResponse, include_in_schema=False)
def login_page():
    html = Path(__file__).parent.joinpath("login.html").read_text(encoding="utf-8")
    return HTMLResponse(content=html, headers={"Cache-Control": "no-cache, no-store, must-revalidate"})


@app.get("/login.html", response_class=HTMLResponse, include_in_schema=False)
def login_page_html():
    html = Path(__file__).parent.joinpath("login.html").read_text(encoding="utf-8")
    return HTMLResponse(content=html, headers={"Cache-Control": "no-cache, no-store, must-revalidate"})


@app.get("/admin", response_class=HTMLResponse, include_in_schema=False)
def admin_page():
    html = Path(__file__).parent.joinpath("admin.html").read_text(encoding="utf-8")
    return HTMLResponse(content=html, headers={"Cache-Control": "no-cache, no-store, must-revalidate"})


@app.get("/admin.html", response_class=HTMLResponse, include_in_schema=False)
def admin_page_html():
    html = Path(__file__).parent.joinpath("admin.html").read_text(encoding="utf-8")
    return HTMLResponse(content=html, headers={"Cache-Control": "no-cache, no-store, must-revalidate"})
