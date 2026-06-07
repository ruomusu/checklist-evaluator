"""
FastAPI 服务入口
- 提供 / 根路径的新人友好前端页面
- 提供 /evaluate 后端 API（流式 SSE 响应）
- 提供 /health 健康检查接口（容器化部署预留）
"""

import asyncio
import io
import json
import logging
import time
from typing import Optional, AsyncGenerator

from fastapi import FastAPI, File, UploadFile, Form, HTTPException
from fastapi.responses import PlainTextResponse, HTMLResponse, StreamingResponse

from config import Config
from logger import log, log_separator
from models import KnowledgeItem, StudentAnswer
from evaluator import Evaluator
from report_generator import ReportGenerator
from knowledge_provider import create_provider

import re

app = FastAPI(
    title="新人 Checklist 自动评估系统",
    description="上传新人答卷文件，自动评估并返回极简 Markdown 报告",
    version="1.0.0",
    docs_url="/api/docs",
    redoc_url="/api/redoc",
)


# ============================================================
# 前端页面（支持流式渲染）
# ============================================================

FRONTEND_HTML = """<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>新人 Checklist 自动评估系统</title>
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body {
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            background: #f5f7fa;
            color: #333;
            min-height: 100vh;
            display: flex;
            flex-direction: column;
            align-items: center;
            padding: 40px 20px;
        }
        .container { width: 100%; max-width: 720px; }
        h1 {
            text-align: center;
            font-size: 1.8rem;
            font-weight: 600;
            color: #1a1a2e;
            margin-bottom: 8px;
        }
        .subtitle {
            text-align: center;
            color: #666;
            font-size: 0.95rem;
            margin-bottom: 40px;
        }
        .upload-card {
            background: #fff;
            border-radius: 12px;
            padding: 32px;
            box-shadow: 0 2px 12px rgba(0,0,0,0.08);
        }
        .form-group { margin-bottom: 20px; }
        .form-group label {
            display: block;
            font-size: 0.9rem;
            font-weight: 500;
            color: #555;
            margin-bottom: 6px;
        }
        .form-group input[type="text"] {
            width: 100%;
            padding: 10px 14px;
            border: 1px solid #ddd;
            border-radius: 8px;
            font-size: 0.95rem;
            transition: border-color 0.2s;
        }
        .form-group input[type="text"]:focus {
            outline: none;
            border-color: #4a90d9;
        }
        .file-upload-area {
            border: 2px dashed #ccc;
            border-radius: 10px;
            padding: 30px;
            text-align: center;
            cursor: pointer;
            transition: all 0.2s;
            position: relative;
        }
        .file-upload-area:hover {
            border-color: #4a90d9;
            background: #f8fbff;
        }
        .file-upload-area.has-file {
            border-color: #52c41a;
            background: #f6ffed;
        }
        .file-upload-area input[type="file"] {
            position: absolute;
            inset: 0;
            opacity: 0;
            cursor: pointer;
        }
        .file-upload-icon { font-size: 2rem; margin-bottom: 8px; }
        .file-upload-text { color: #888; font-size: 0.9rem; }
        .file-name { color: #52c41a; font-weight: 500; font-size: 0.95rem; }
        .submit-btn {
            width: 100%;
            padding: 14px;
            background: #4a90d9;
            color: #fff;
            border: none;
            border-radius: 8px;
            font-size: 1rem;
            font-weight: 500;
            cursor: pointer;
            transition: background 0.2s;
            margin-top: 8px;
        }
        .submit-btn:hover { background: #357abd; }
        .submit-btn:disabled { background: #ccc; cursor: not-allowed; }
        .status-bar {
            display: none;
            text-align: center;
            padding: 24px 0;
        }
        .status-bar.active { display: block; }
        .spinner {
            width: 36px;
            height: 36px;
            border: 4px solid #e0e0e0;
            border-top-color: #4a90d9;
            border-radius: 50%;
            animation: spin 0.8s linear infinite;
            margin: 0 auto 12px;
        }
        @keyframes spin { to { transform: rotate(360deg); } }
        .status-text { color: #666; font-size: 0.9rem; }
        .result-card {
            display: none;
            background: #fff;
            border-radius: 12px;
            padding: 32px;
            box-shadow: 0 2px 12px rgba(0,0,0,0.08);
            margin-top: 24px;
        }
        .result-card.active { display: block; }
        .result-content {
            font-family: 'SF Mono', 'Fira Code', Consolas, monospace;
            font-size: 0.88rem;
            line-height: 1.7;
            white-space: pre-wrap;
            word-break: break-word;
            color: #2c3e50;
            min-height: 60px;
        }
        .cursor {
            display: inline-block;
            width: 2px;
            height: 1em;
            background: #4a90d9;
            animation: blink 0.8s step-end infinite;
            vertical-align: text-bottom;
        }
        @keyframes blink { 50% { opacity: 0; } }
        .error-msg {
            display: none;
            background: #fff2f0;
            border: 1px solid #ffccc7;
            border-radius: 8px;
            padding: 16px;
            margin-top: 16px;
            color: #cf1322;
            font-size: 0.9rem;
        }
        .error-msg.active { display: block; }
        .reset-btn {
            display: inline-block;
            margin-top: 20px;
            padding: 10px 24px;
            background: #f0f0f0;
            border: none;
            border-radius: 8px;
            color: #555;
            cursor: pointer;
            font-size: 0.9rem;
        }
        .reset-btn:hover { background: #e0e0e0; }
    </style>
</head>
<body>
    <div class="container">
        <h1>📋 新人 Checklist 自动评估系统</h1>
        <p class="subtitle">上传答卷文件，系统将自动评估并生成报告</p>

        <div class="upload-card" id="uploadCard">
            <div class="form-group">
                <label for="studentName">姓名</label>
                <input type="text" id="studentName" placeholder="请输入新人姓名" value="">
            </div>
            <div class="form-group">
                <label>答卷文件</label>
                <div class="file-upload-area" id="fileArea">
                    <input type="file" id="fileInput" accept=".md,.txt,.text,.markdown,.docx">
                    <div class="file-upload-icon">📄</div>
                    <div class="file-upload-text" id="fileText">点击选择文件或拖拽到此处<br><small>支持 .md / .txt / .docx 格式</small></div>
                </div>
            </div>
            <button class="submit-btn" id="submitBtn" disabled>开始评估</button>
        </div>

        <div class="status-bar" id="statusBar">
            <div class="spinner"></div>
            <div class="status-text" id="statusText">准备中...</div>
        </div>

        <div class="error-msg" id="errorMsg"></div>

        <div class="result-card" id="resultCard">
            <div class="result-content" id="resultContent"></div>
            <button class="reset-btn" id="resetBtn">重新评估</button>
        </div>
    </div>

    <script>
        const fileInput = document.getElementById('fileInput');
        const fileArea = document.getElementById('fileArea');
        const fileText = document.getElementById('fileText');
        const submitBtn = document.getElementById('submitBtn');
        const uploadCard = document.getElementById('uploadCard');
        const statusBar = document.getElementById('statusBar');
        const statusText = document.getElementById('statusText');
        const resultCard = document.getElementById('resultCard');
        const resultContent = document.getElementById('resultContent');
        const errorMsg = document.getElementById('errorMsg');
        const resetBtn = document.getElementById('resetBtn');
        const studentName = document.getElementById('studentName');

        fileInput.addEventListener('change', function() {
            if (this.files.length > 0) {
                fileArea.classList.add('has-file');
                fileText.innerHTML = '<span class="file-name">✅ ' + this.files[0].name + '</span>';
                submitBtn.disabled = false;
            }
        });

        submitBtn.addEventListener('click', async function() {
            const file = fileInput.files[0];
            if (!file) return;

            uploadCard.style.display = 'none';
            statusBar.classList.add('active');
            statusText.textContent = '正在上传文件...';
            errorMsg.classList.remove('active');
            resultCard.classList.remove('active');
            resultContent.textContent = '';

            const formData = new FormData();
            formData.append('file', file);
            formData.append('student_name', studentName.value || '新人');

            try {
                const response = await fetch('/evaluate', {
                    method: 'POST',
                    body: formData,
                });

                if (!response.ok) {
                    statusBar.classList.remove('active');
                    let detail = '评估过程中出现问题，请重试';
                    try {
                        const err = await response.json();
                        detail = err.detail || detail;
                    } catch(e) {}
                    errorMsg.textContent = detail;
                    errorMsg.classList.add('active');
                    uploadCard.style.display = 'block';
                    return;
                }

                // 流式读取响应
                statusText.textContent = '大模型正在分析答卷...';
                resultCard.classList.add('active');
                resultContent.innerHTML = '<span class="cursor"></span>';

                const reader = response.body.getReader();
                const decoder = new TextDecoder('utf-8');
                let buffer = '';

                while (true) {
                    const { done, value } = await reader.read();
                    if (done) break;

                    const chunk = decoder.decode(value, { stream: true });
                    buffer += chunk;
                    resultContent.textContent = buffer;
                    // 添加光标
                    const cursor = document.createElement('span');
                    cursor.className = 'cursor';
                    resultContent.appendChild(cursor);
                    // 滚动到底部
                    resultCard.scrollTop = resultCard.scrollHeight;
                }

                // 完成，移除光标
                statusBar.classList.remove('active');
                resultContent.textContent = buffer;

            } catch (e) {
                statusBar.classList.remove('active');
                errorMsg.textContent = '网络连接失败，请检查服务是否正常运行';
                errorMsg.classList.add('active');
                uploadCard.style.display = 'block';
            }
        });

        resetBtn.addEventListener('click', function() {
            resultCard.classList.remove('active');
            uploadCard.style.display = 'block';
            fileInput.value = '';
            fileArea.classList.remove('has-file');
            fileText.innerHTML = '点击选择文件或拖拽到此处<br><small>支持 .md / .txt / .docx 格式</small>';
            submitBtn.disabled = true;
            resultContent.textContent = '';
        });
    </script>
</body>
</html>"""


@app.get("/", response_class=HTMLResponse, include_in_schema=False)
def frontend_page():
    """面向新人的极简前端页面"""
    return HTMLResponse(content=FRONTEND_HTML)


# ============================================================
# 文件解析工具
# ============================================================

def _extract_text_from_docx(raw_bytes: bytes) -> str:
    """从 .docx 文件提取纯文本，Word 标题转为 ## 格式"""
    from docx import Document

    doc = Document(io.BytesIO(raw_bytes))
    lines = []
    for para in doc.paragraphs:
        text = para.text.strip()
        if not text:
            lines.append("")
            continue
        if para.style and para.style.name and para.style.name.startswith("Heading"):
            lines.append(f"## {text}")
        else:
            lines.append(text)
    return "\n".join(lines)


def _parse_answers_from_text(content: str, knowledge_items: list[KnowledgeItem]) -> list[StudentAnswer]:
    """从文本内容解析新人回答"""
    answers = []
    pattern = r"##\s*(Q?\d+)\s*\n(.*?)(?=\n##\s*Q?\d+|\Z)"
    matches = re.findall(pattern, content, re.DOTALL)

    for qid, answer_text in matches:
        if not qid.startswith("Q"):
            qid = f"Q{qid}"
        answers.append(StudentAnswer(
            question_id=qid,
            answer_text=answer_text.strip(),
        ))

    if not answers and knowledge_items:
        paragraphs = [p.strip() for p in content.split("\n\n") if p.strip()]
        for i, para in enumerate(paragraphs):
            if i < len(knowledge_items):
                answers.append(StudentAnswer(
                    question_id=knowledge_items[i].question_id,
                    answer_text=para,
                ))

    return answers


# ============================================================
# 后端 API
# ============================================================

@app.get("/health", summary="健康检查", tags=["运维"], include_in_schema=False)
def health_check():
    """返回 200 状态码，用于容器化部署的健康探针"""
    return {"status": "ok"}


async def _stream_evaluate(
    content: str,
    student_name: str,
    checklist_id: Optional[str],
    filename: str,
) -> AsyncGenerator[str, None]:
    """
    流式评估生成器：执行评估并逐块 yield 报告文本

    流式策略：
    - 评估阶段（Tool Calling + LLM）需要完整执行后才能解析 JSON
    - 拿到报告文本后，逐行流式输出（模拟打字机效果）
    """
    total_start = time.time()
    log_separator("API 流式评估请求")
    log(f"评估对象: {student_name} | 文件: {filename}", stage="INIT")

    # 1. 获取知识库
    provider = create_provider()
    knowledge_items = provider.get_all_questions(checklist_id)
    log(f"已获取 {len(knowledge_items)} 道题目", stage="KB")

    # 2. 解析答卷
    student_answers = _parse_answers_from_text(content, knowledge_items)
    if not student_answers:
        yield "错误：无法从文件中解析出任何回答，请检查格式"
        return
    log(f"已解析 {len(student_answers)} 道回答", stage="ANSWER")

    # 3. 调用大模型评估（这步需要完整执行）
    evaluator = Evaluator()
    report = evaluator.evaluate(knowledge_items, student_answers)
    report.student_name = student_name

    # 4. 生成报告并保存
    generator = ReportGenerator()
    markdown_report = generator.generate_markdown(report)
    generator.save_report(report)

    total_elapsed = time.time() - total_start
    log(f"API 评估完成 | 总耗时: {total_elapsed:.1f}s", stage="DONE")

    # 5. 逐行流式输出报告（打字机效果）
    lines = markdown_report.split("\n")
    for i, line in enumerate(lines):
        yield line
        if i < len(lines) - 1:
            yield "\n"
        # 短暂延迟，制造流式效果
        await asyncio.sleep(0.03)


@app.post(
    "/evaluate",
    summary="上传答卷并评估（流式响应）",
    tags=["评估"],
    include_in_schema=False,
)
async def evaluate(
    file: UploadFile = File(..., description="新人答卷文件"),
    student_name: str = Form(default="新人", description="新人姓名"),
    checklist_id: Optional[str] = Form(default=None, description="Checklist ID"),
):
    """接收答卷文件，流式返回评估报告"""
    if not file.filename:
        raise HTTPException(status_code=400, detail="未上传文件")

    # 读取文件
    try:
        raw_bytes = await file.read()
        filename_lower = file.filename.lower()

        if filename_lower.endswith(".docx"):
            content = _extract_text_from_docx(raw_bytes)
        elif filename_lower.endswith(".doc"):
            raise HTTPException(status_code=400, detail="不支持旧版 .doc 格式，请另存为 .docx 后重新上传")
        else:
            content = raw_bytes.decode("utf-8")
    except HTTPException:
        raise
    except UnicodeDecodeError:
        raise HTTPException(status_code=400, detail="文件编码错误，请确保文件为 UTF-8 编码")
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"文件读取失败: {e}")

    if not content.strip():
        raise HTTPException(status_code=400, detail="文件内容为空")

    # 返回流式响应
    return StreamingResponse(
        _stream_evaluate(content, student_name, checklist_id, file.filename),
        media_type="text/plain; charset=utf-8",
    )
