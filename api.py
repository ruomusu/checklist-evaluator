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
    <title>Checklist 自动评估系统</title>
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
            padding: 32px 0;
        }
        .status-bar.active { display: block; }
        .progress-wrapper {
            width: 100%;
            max-width: 400px;
            margin: 0 auto 16px;
            background: #e8ecf0;
            border-radius: 20px;
            height: 12px;
            overflow: hidden;
        }
        .progress-fill {
            height: 100%;
            width: 0%;
            background: linear-gradient(90deg, #4a90d9, #67b8f7);
            border-radius: 20px;
            transition: width 0.5s ease;
        }
        .status-text { color: #666; font-size: 0.9rem; margin-top: 8px; }
        .progress-percent { 
            color: #4a90d9; 
            font-weight: 600; 
            font-size: 1.1rem; 
            margin-bottom: 8px; 
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
        .result-actions {
            margin-top: 20px;
            display: flex;
            gap: 12px;
        }
        .reset-btn {
            display: inline-block;
            padding: 10px 24px;
            background: #f0f0f0;
            border: none;
            border-radius: 8px;
            color: #555;
            cursor: pointer;
            font-size: 0.9rem;
        }
        .reset-btn:hover { background: #e0e0e0; }
        .download-btn {
            display: inline-block;
            padding: 10px 24px;
            background: #52c41a;
            color: #fff;
            border: none;
            border-radius: 8px;
            cursor: pointer;
            font-size: 0.9rem;
            text-decoration: none;
        }
        .download-btn:hover { background: #45a814; }
    </style>
</head>
<body>
    <div class="container">
        <h1>📋 Checklist 自动评估系统</h1>
        <p class="subtitle">上传作答文件，系统将自动评估并生成报告</p>

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
            <div class="progress-percent" id="progressPercent">0%</div>
            <div class="progress-wrapper">
                <div class="progress-fill" id="progressFill"></div>
            </div>
            <div class="status-text" id="statusText">准备中...</div>
        </div>

        <div class="error-msg" id="errorMsg"></div>

        <div class="result-card" id="resultCard">
            <div class="result-content" id="resultContent"></div>
            <div class="result-actions">
                <button class="reset-btn" id="resetBtn">重新评估</button>
                <button class="download-btn" id="downloadBtn">📥 下载报告</button>
            </div>
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
        const progressFill = document.getElementById('progressFill');
        const progressPercent = document.getElementById('progressPercent');
        const resultCard = document.getElementById('resultCard');
        const resultContent = document.getElementById('resultContent');
        const errorMsg = document.getElementById('errorMsg');
        const resetBtn = document.getElementById('resetBtn');
        const downloadBtn = document.getElementById('downloadBtn');
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

            // 模拟动态进度条
            let progressTimer = null;
            let currentPct = 0;
            let stepIdx = 0;
            const steps = [
                { pct: 5,  msg: '正在上传文件...' },
                { pct: 12, msg: '正在加载知识库...' },
                { pct: 20, msg: '正在解析答卷内容...' },
                { pct: 30, msg: '正在分析第 1 题...' },
                { pct: 40, msg: '正在分析第 2 题...' },
                { pct: 50, msg: '正在分析第 3 题...' },
                { pct: 60, msg: '正在分析第 4 题...' },
                { pct: 70, msg: '正在分析第 5 题...' },
                { pct: 80, msg: '正在综合评估...' },
                { pct: 88, msg: '正在生成报告...' },
                { pct: 92, msg: '即将完成...' },
            ];
            function setProgress(pct, msg) {
                progressFill.style.width = pct + '%';
                progressPercent.textContent = pct + '%';
                if (msg) statusText.textContent = msg;
            }
            function startProgress() {
                stepIdx = 0;
                setProgress(steps[0].pct, steps[0].msg);
                progressTimer = setInterval(function() {
                    stepIdx++;
                    if (stepIdx < steps.length) {
                        setProgress(steps[stepIdx].pct, steps[stepIdx].msg);
                    }
                }, 3000);
            }
            function stopProgress() {
                if (progressTimer) { clearInterval(progressTimer); progressTimer = null; }
                setProgress(100, '评估完成');
            }

            startProgress();

            try {
                const response = await fetch('/evaluate', {
                    method: 'POST',
                    body: formData,
                });

                if (!response.ok) {
                    stopProgress();
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

                // SSE 流式读取
                const reader = response.body.getReader();
                const decoder = new TextDecoder('utf-8');
                let sseBuffer = '';
                let reportBuffer = '';
                let reportStarted = false;

                while (true) {
                    const { done, value } = await reader.read();
                    if (done) break;

                    sseBuffer += decoder.decode(value, { stream: true });

                    // 解析 SSE 消息（以双换行分隔）
                    const messages = sseBuffer.split('\\n\\n');
                    sseBuffer = messages.pop(); // 保留未完成的部分

                    for (const msg of messages) {
                        if (!msg.trim()) continue;

                        let eventType = 'message';
                        let data = '';

                        for (const line of msg.split('\\n')) {
                            if (line.startsWith('event: ')) {
                                eventType = line.slice(7);
                            } else if (line.startsWith('data: ')) {
                                data = line.slice(6);
                            }
                        }

                        if (eventType === 'progress') {
                            // 更新进度提示文字
                            statusText.textContent = data;
                        } else if (eventType === 'content') {
                            // 收到报告内容
                            if (!reportStarted) {
                                reportStarted = true;
                                stopProgress();
                                statusBar.classList.remove('active');
                                resultCard.classList.add('active');
                            }
                            // 空行占位还原
                            const lineText = (data === ' ') ? '' : data;
                            reportBuffer += (reportBuffer ? '\\n' : '') + lineText;
                            resultContent.textContent = reportBuffer;
                            // 添加光标
                            const cursor = document.createElement('span');
                            cursor.className = 'cursor';
                            resultContent.appendChild(cursor);
                            resultCard.scrollTop = resultCard.scrollHeight;
                        } else if (eventType === 'done') {
                            // 完成
                            statusBar.classList.remove('active');
                            resultContent.textContent = reportBuffer;
                        }
                    }
                }

                // 确保最终状态正确
                statusBar.classList.remove('active');
                if (reportBuffer) {
                    resultContent.textContent = reportBuffer;
                    resultCard.classList.add('active');
                }

            } catch (e) {
                stopProgress();
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

        downloadBtn.addEventListener('click', function() {
            const content = resultContent.textContent;
            if (!content) return;
            const name = studentName.value || '新人';
            const filename = '评估报告_' + name + '_' + new Date().toISOString().slice(0,10) + '.md';
            const blob = new Blob([content], { type: 'text/markdown;charset=utf-8' });
            const url = URL.createObjectURL(blob);
            const a = document.createElement('a');
            a.href = url;
            a.download = filename;
            document.body.appendChild(a);
            a.click();
            document.body.removeChild(a);
            URL.revokeObjectURL(url);
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
    SSE 流式评估生成器

    协议：
    - 进度消息格式：  event: progress\ndata: 正在分析第 N 题...\n\n
    - 报告内容格式：  event: content\ndata: <一行报告文本>\n\n
    - 完成信号：      event: done\ndata: \n\n
    """
    total_start = time.time()
    log_separator("API 流式评估请求")
    log(f"评估对象: {student_name} | 文件: {filename}", stage="INIT")

    # 发送初始进度
    yield "event: progress\ndata: 正在加载知识库...\n\n"
    await asyncio.sleep(0.1)

    # 1. 获取知识库
    provider = create_provider()
    knowledge_items = provider.get_all_questions(checklist_id)
    log(f"已获取 {len(knowledge_items)} 道题目", stage="KB")

    # 2. 解析答卷
    yield "event: progress\ndata: 正在解析答卷...\n\n"
    await asyncio.sleep(0.1)

    student_answers = _parse_answers_from_text(content, knowledge_items)
    if not student_answers:
        yield "event: content\ndata: 错误：无法从文件中解析出任何回答，请检查格式\n\n"
        yield "event: done\ndata: \n\n"
        return
    log(f"已解析 {len(student_answers)} 道回答", stage="ANSWER")

    # 3. 调用大模型评估
    yield "event: progress\ndata: 正在调用大模型评估...\n\n"
    await asyncio.sleep(0.1)

    # 在线程池中执行阻塞的 LLM 调用，避免阻塞事件循环
    import concurrent.futures
    loop = asyncio.get_event_loop()
    with concurrent.futures.ThreadPoolExecutor() as pool:
        evaluator = Evaluator()
        report = await loop.run_in_executor(
            pool, evaluator.evaluate, knowledge_items, student_answers
        )
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
        # SSE data 字段中空行用特殊占位
        data_line = line if line else " "
        yield f"event: content\ndata: {data_line}\n\n"
        await asyncio.sleep(0.02)

    yield "event: done\ndata: \n\n"


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

    # 返回 SSE 流式响应
    return StreamingResponse(
        _stream_evaluate(content, student_name, checklist_id, file.filename),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )
