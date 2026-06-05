"""
FastAPI 服务入口
- 提供 / 根路径的新人友好前端页面
- 提供 /evaluate 后端 API 接收答卷文件并返回评估报告
- 提供 /health 健康检查接口（容器化部署预留）
"""

import logging
import time
import io
from typing import Optional

from fastapi import FastAPI, File, UploadFile, Form, HTTPException
from fastapi.responses import PlainTextResponse, HTMLResponse

from config import Config
from logger import log, log_separator
from models import KnowledgeItem, StudentAnswer
from evaluator import Evaluator
from report_generator import ReportGenerator
from knowledge_provider import create_provider

import re

app = FastAPI(
    title="新人 Checklist 自动评估系统",
    description="上传新人答卷文件（.md / .txt），自动评估并返回极简 Markdown 报告",
    version="1.0.0",
    docs_url="/api/docs",
    redoc_url="/api/redoc",
)


# ============================================================
# 前端页面
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
        .container {
            width: 100%;
            max-width: 720px;
        }
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
        .form-group {
            margin-bottom: 20px;
        }
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
        .file-upload-icon {
            font-size: 2rem;
            margin-bottom: 8px;
        }
        .file-upload-text {
            color: #888;
            font-size: 0.9rem;
        }
        .file-name {
            color: #52c41a;
            font-weight: 500;
            font-size: 0.95rem;
        }
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
        .submit-btn:disabled {
            background: #ccc;
            cursor: not-allowed;
        }
        .loading {
            display: none;
            text-align: center;
            padding: 40px 0;
        }
        .loading.active { display: block; }
        .spinner {
            width: 40px;
            height: 40px;
            border: 4px solid #e0e0e0;
            border-top-color: #4a90d9;
            border-radius: 50%;
            animation: spin 0.8s linear infinite;
            margin: 0 auto 16px;
        }
        @keyframes spin { to { transform: rotate(360deg); } }
        .loading-text {
            color: #666;
            font-size: 0.95rem;
        }
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
            font-family: 'SF Mono', 'Fira Code', monospace;
            font-size: 0.88rem;
            line-height: 1.7;
            white-space: pre-wrap;
            word-break: break-word;
            color: #2c3e50;
        }
        .result-content strong { color: #1a1a2e; }
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

        <div class="loading" id="loading">
            <div class="spinner"></div>
            <div class="loading-text">正在评估中，请稍候...<br><small>大模型正在分析答卷内容</small></div>
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
        const loading = document.getElementById('loading');
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

            // 显示加载状态
            uploadCard.style.display = 'none';
            loading.classList.add('active');
            errorMsg.classList.remove('active');
            resultCard.classList.remove('active');

            const formData = new FormData();
            formData.append('file', file);
            formData.append('student_name', studentName.value || '新人');

            try {
                const response = await fetch('/evaluate', {
                    method: 'POST',
                    body: formData,
                });

                loading.classList.remove('active');

                if (response.ok) {
                    const text = await response.text();
                    resultContent.textContent = text;
                    resultCard.classList.add('active');
                } else {
                    let detail = '评估过程中出现问题，请重试';
                    try {
                        const err = await response.json();
                        detail = err.detail || detail;
                    } catch(e) {}
                    errorMsg.textContent = detail;
                    errorMsg.classList.add('active');
                    uploadCard.style.display = 'block';
                }
            } catch (e) {
                loading.classList.remove('active');
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
        });
    </script>
</body>
</html>"""


@app.get("/", response_class=HTMLResponse, include_in_schema=False)
def frontend_page():
    """面向新人的极简前端页面"""
    return HTMLResponse(content=FRONTEND_HTML)


def _extract_text_from_docx(raw_bytes: bytes) -> str:
    """
    从 .docx 文件的二进制内容中提取纯文本

    保留段落结构，用换行分隔。
    Word 中的标题（Heading）会被转为 ## 格式以便后续解析。
    """
    from docx import Document

    doc = Document(io.BytesIO(raw_bytes))
    lines = []
    for para in doc.paragraphs:
        text = para.text.strip()
        if not text:
            lines.append("")
            continue
        # 将 Word 标题样式转为 Markdown 格式
        if para.style and para.style.name and para.style.name.startswith("Heading"):
            lines.append(f"## {text}")
        else:
            lines.append(text)
    return "\n".join(lines)


# ============================================================
# 后端 API
# ============================================================

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

    # fallback：按段落顺序对应
    if not answers and knowledge_items:
        paragraphs = [p.strip() for p in content.split("\n\n") if p.strip()]
        for i, para in enumerate(paragraphs):
            if i < len(knowledge_items):
                answers.append(StudentAnswer(
                    question_id=knowledge_items[i].question_id,
                    answer_text=para,
                ))

    return answers


@app.get("/health", summary="健康检查", tags=["运维"], include_in_schema=False)
def health_check():
    """返回 200 状态码，用于容器化部署的健康探针"""
    return {"status": "ok"}


@app.post(
    "/evaluate",
    summary="上传答卷并评估",
    tags=["评估"],
    response_class=PlainTextResponse,
    include_in_schema=False,
)
async def evaluate(
    file: UploadFile = File(..., description="新人答卷文件（支持 .md / .txt 等文本文件）"),
    student_name: str = Form(default="新人", description="新人姓名"),
    checklist_id: Optional[str] = Form(default=None, description="Checklist ID（可选）"),
):
    """
    接收答卷文件，执行评估，返回极简 Markdown 报告文本。
    """
    # 验证文件
    if not file.filename:
        raise HTTPException(status_code=400, detail="未上传文件")

    # 读取文件内容（根据文件类型选择解析方式）
    try:
        raw_bytes = await file.read()
        filename_lower = file.filename.lower()

        if filename_lower.endswith(".docx"):
            # Word 文档解析
            content = _extract_text_from_docx(raw_bytes)
        elif filename_lower.endswith(".doc"):
            raise HTTPException(status_code=400, detail="不支持旧版 .doc 格式，请另存为 .docx 后重新上传")
        else:
            # 纯文本格式（.md / .txt 等）
            content = raw_bytes.decode("utf-8")
    except HTTPException:
        raise
    except UnicodeDecodeError:
        raise HTTPException(status_code=400, detail="文件编码错误，请确保文件为 UTF-8 编码")
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"文件读取失败: {e}")

    if not content.strip():
        raise HTTPException(status_code=400, detail="文件内容为空")

    # 评估流程
    total_start = time.time()
    log_separator("API 评估请求")
    log(f"评估对象: {student_name} | 文件: {file.filename}", stage="INIT")

    try:
        # 1. 获取知识库
        provider = create_provider()
        knowledge_items = provider.get_all_questions(checklist_id)
        log(f"已获取 {len(knowledge_items)} 道题目", stage="KB")

        # 2. 解析答卷
        student_answers = _parse_answers_from_text(content, knowledge_items)
        if not student_answers:
            raise HTTPException(status_code=400, detail="无法从文件中解析出任何回答，请检查格式")
        log(f"已解析 {len(student_answers)} 道回答", stage="ANSWER")

        # 3. 调用大模型评估
        evaluator = Evaluator()
        report = evaluator.evaluate(knowledge_items, student_answers)
        report.student_name = student_name

        # 4. 生成报告
        generator = ReportGenerator()
        markdown_report = generator.generate_markdown(report)

        # 同时保存到文件
        generator.save_report(report)

        total_elapsed = time.time() - total_start
        log(f"API 评估完成 | 总耗时: {total_elapsed:.1f}s", stage="DONE")

        return PlainTextResponse(content=markdown_report, media_type="text/plain; charset=utf-8")

    except HTTPException:
        raise
    except Exception as e:
        log(f"评估异常: {e}", stage="ERROR", level=logging.ERROR)
        raise HTTPException(status_code=500, detail=f"评估过程中发生错误: {e}")
