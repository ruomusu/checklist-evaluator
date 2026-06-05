# 新人 Checklist 自动评估系统 — 架构与数据流

## 一、系统总览

```
┌─────────────────────────────────────────────────────────────────────┐
│                        CLI 命令行入口 (main.py)                      │
│   python main.py <答卷.md> [checklist_id] [姓名]                     │
└────────────────────────────────┬────────────────────────────────────┘
                                 │
                                 ▼
┌─────────────────────────────────────────────────────────────────────┐
│                         流程编排层 (main.py)                         │
│                                                                     │
│  1. 获取知识库  →  2. 解析答卷  →  3. 大模型评估（含 Tool Calling）   │
└───┬────────────────────┬───────────────────────────────┬────────────┘
    │                    │                               │
    ▼                    ▼                               ▼
┌────────┐      ┌──────────────┐              ┌──────────────────┐
│Knowledge│      │  答卷解析器   │              │    Evaluator     │
│Provider │      │ (Markdown/   │              │   评估引擎        │
│ (动态)  │      │   TXT 解析)  │              │ (Tool Calling)   │
└────────┘      └──────────────┘              └────────┬─────────┘
                                                       │
                                          ┌────────────┼────────────┐
                                          │            │            │
                                          ▼            ▼            ▼
                                   ┌──────────┐ ┌──────────┐ ┌──────────┐
                                   │  LLM API │ │ 内部知识库 │ │ AWS 官方 │
                                   │(OpenAI/  │ │  检索工具  │ │ 文档检索 │
                                   │ Qwen/    │ │(Tool Call)│ │(Tool Call)│
                                   │ DeepSeek)│ └──────────┘ └──────────┘
                                   └────┬─────┘
                                        │
                                        ▼
                                 ┌──────────────┐
                                 │    Report    │
                                 │  Generator   │
                                 │ (Markdown)   │
                                 └──────────────┘
```

---

## 二、文件结构与职责

```
project/
├── main.py                  # CLI 主入口，流程编排
├── api.py                   # FastAPI 服务入口（HTTP 接口）
├── config.py                # 全局配置（环境变量动态读取）
├── logger.py                # 结构化日志（终端彩色 + 文件记录）
├── models.py                # Pydantic 数据模型定义
├── prompts.py               # LLM System Prompt 与 User Prompt 模板
├── evaluator.py             # 核心评估引擎（Tool Calling + LLM 调用 + 响应解析）
├── search_tools.py          # 搜索工具模块（内部知识库 + AWS 官方文档）
├── knowledge_provider.py    # 知识库抽象层（本地/API/数据库）
├── report_generator.py      # 报告生成器（极简 Markdown 输出）
├── internal_kb/             # 内部知识库 Mock 目录（放入 .md/.txt 文件）
├── sample_knowledge_base.json  # 示例知识库数据
├── sample_answers.md        # 示例新人答卷
├── requirements.txt         # Python 依赖
├── .env.example             # 环境变量模板（安全，可提交）
├── .env                     # 实际环境变量（不提交）
├── .gitignore               # Git 忽略规则
└── ARCHITECTURE.md          # 本文档
```

---

## 三、核心数据流

```
          ┌──────────────────────────┐
          │   输入数据源（两路输入）   │
          └────────────┬─────────────┘
                       │
          ┌────────────┼────────────┐
          │                         │
          ▼                         ▼
┌──────────────────┐       ┌────────────────┐
│  标准知识库       │       │  新人答卷       │
│                  │       │                │
│ · question_id    │       │ · question_id  │
│ · question       │       │ · answer_text  │
│ · reference_answer│       │               │
│ · reference_links│       │                │
└────────┬─────────┘       └───────┬────────┘
         │                         │
         └────────────┬────────────┘
                      │
                      ▼
          ┌───────────────────────┐
          │    Prompt 组装        │
          │                       │
          │  System Prompt        │
          │  (判卷专家 + 工具指引) │
          │         +             │
          │  User Prompt          │
          │  (标准答案 + 新人回答) │
          └───────────┬───────────┘
                      │
                      ▼
          ┌───────────────────────┐
          │   LLM API 调用        │
          │  (支持 Tool Calling)  │
          └───────────┬───────────┘
                      │
            ┌─────────┼─────────┐
            │ Tool Calls?        │
            │                    │
            ▼ Yes                ▼ No
  ┌──────────────────┐   ┌──────────────────┐
  │ 执行搜索工具      │   │  直接返回 JSON   │
  │                  │   │  评估结果         │
  │ · search_internal│   └────────┬─────────┘
  │ · search_aws_docs│            │
  └────────┬─────────┘            │
           │ 结果注入对话          │
           └──────┬───────────────┘
                  │
                  ▼
          ┌───────────────────────┐
          │    JSON 响应解析      │
          │  JSON → Pydantic 模型 │
          └───────────┬───────────┘
                      │
                      ▼
          ┌───────────────────────┐
          │  EvaluationReport     │
          │                       │
          │  · question_evaluations│
          │    (判定 + 缺失点)     │
          └───────────┬───────────┘
                      │
                      ▼
          ┌───────────────────────┐
          │  极简 Markdown 报告   │
          │                       │
          │  → 终端打印           │
          │  → output/*.md 文件   │
          └───────────────────────┘
```

---

## 四、搜索工具架构（Tool Calling）

```
                    Evaluator (评估引擎)
                         │
                    LLM 主动决策
                    是否需要补充资料
                         │
            ┌────────────┼────────────┐
            │                         │
            ▼                         ▼
┌───────────────────────┐  ┌───────────────────────┐
│  search_internal_kb   │  │  search_aws_docs      │
│  内部私有知识库检索    │  │  AWS 官方文档检索      │
├───────────────────────┤  ├───────────────────────┤
│ 当前: 本地文件关键词   │  │ 当前: 搜索 API 调用   │
│       匹配 (Mock)     │  │       (需配置 API Key)│
│                       │  │                       │
│ 未来: 向量数据库      │  │ 未来: Tavily/SerpAPI  │
│       Bedrock KB      │  │       Amazon Kendra   │
│       内部 REST API   │  │       自建爬虫        │
├───────────────────────┤  ├───────────────────────┤
│ 数据源:               │  │ 强制搜索源:           │
│   ./internal_kb/*.md  │  │   · User Guide       │
│   ./internal_kb/*.txt │  │   · Knowledge Center │
│                       │  │   · Prescriptive     │
│                       │  │     Guidance         │
│                       │  │   · Developer Guide  │
│                       │  │   · 官方 FAQ         │
└───────────────────────┘  └───────────────────────┘
```

### Tool Calling 工作流程

1. Evaluator 将标准答案 + 新人回答发送给 LLM，同时附带工具定义
2. LLM 判断是否需要补充信息：
   - 标准答案充分 → 直接输出评估 JSON
   - 需要补充 → 发起 tool_call（可同时调多个工具）
3. 系统执行工具函数，将结果以 tool message 返回给 LLM
4. LLM 综合全部信息输出最终评估（最多循环 5 轮）

---

## 五、知识库 Provider 架构

```
           KnowledgeProvider (抽象基类)
                    │
        ┌───────────┼───────────┐
        │           │           │
        ▼           ▼           ▼
┌──────────┐ ┌──────────┐ ┌──────────────┐
│  Local   │ │   API    │ │  Database    │
│  File    │ │ Provider │ │  Provider    │
│ Provider │ │          │ │              │
└──────────┘ └──────────┘ └──────────────┘
     │             │              │
     ▼             ▼              ▼
  本地 JSON    HTTP REST API   SQL 数据库
  文件          (内部知识库      (PostgreSQL/
               微服务)          MySQL/SQLite)
```

切换方式：修改 `.env` 中的 `KNOWLEDGE_PROVIDER` 变量即可。

---

## 六、LLM 提供者架构（动态切换）

```
         .env 中 LLM_PROVIDER=xxx
                    │
                    ▼
         自动读取环境变量：
         {XXX}_API_KEY
         {XXX}_BASE_URL
         {XXX}_MODEL
                    │
        ┌───────────┼───────────┐
        │           │           │
        ▼           ▼           ▼
┌──────────┐ ┌──────────┐ ┌──────────┐
│  OpenAI  │ │   Qwen   │ │ DeepSeek │  ... 任意扩展
│  gpt-4o  │ │ qwen-plus│ │deepseek- │
│          │ │(DashScope)│ │  chat    │
└──────────┘ └──────────┘ └──────────┘
```

新增模型只需在 `.env` 中加三行，代码无需改动：
```bash
LLM_PROVIDER=glm
GLM_API_KEY=your-key
GLM_BASE_URL=https://open.bigmodel.cn/api/paas/v4
GLM_MODEL=glm-4
```

---

## 七、模块调用关系

```
main.py (CLI 入口)
  ├── config.py              (读取 .env 配置，动态 LLM 选择)
  ├── logger.py              (全局日志)
  ├── knowledge_provider.py  → create_provider()
  ├── evaluator.py           → Evaluator.evaluate()
  └── report_generator.py    → generate_markdown() / save_report()

api.py (FastAPI HTTP 入口)
  ├── config.py
  ├── logger.py
  ├── knowledge_provider.py  → create_provider()
  ├── evaluator.py           → Evaluator.evaluate()
  └── report_generator.py    → generate_markdown() / save_report()

evaluator.py
  ├── _format_knowledge_base()     → 知识库 → 文本
  ├── _format_student_answers()    → 答案 → 文本
  ├── _call_llm_with_tools()       → LLM + Tool Calling 循环
  ├── _call_llm_simple()           → LLM 简单调用（fallback）
  └── _parse_response()            → JSON → Pydantic

search_tools.py
  ├── search_internal_kb()         → 内部知识库检索
  ├── search_aws_docs()            → AWS 官方文档检索
  ├── TOOL_DEFINITIONS             → OpenAI Function 定义
  └── TOOL_FUNCTIONS               → 工具名 → 函数映射

knowledge_provider.py
  ├── create_provider()            → 工厂函数
  ├── LocalFileProvider            → json.load()
  ├── APIProvider                  → httpx.Client.get()
  └── DatabaseProvider             → sqlite3
```

---

## 八、数据模型关系

```
KnowledgeItem          StudentAnswer         EvaluationReport
┌──────────────┐      ┌──────────────┐      ┌───────────────────────┐
│ question_id  │      │ question_id  │      │ student_name          │
│ question     │      │ answer_text  │      │ total_questions       │
│ ref_answer   │      └──────────────┘      │ mastered_count        │
│ ref_links[]  │                            │ ambiguous_count       │
└──────────────┘                            │ weak_count            │
                                            │ question_evaluations[]│
QuestionEvaluation                          └───────────────────────┘
┌──────────────────┐
│ question_id      │
│ mastery_level    │   MasteryLevel (Enum)
│ missing_points[] │   ├── 掌握
│ notes            │   ├── 模棱两可
└──────────────────┘   └── 薄弱
```

---

## 九、日志体系

### 终端输出（彩色，按阶段标识）

| 阶段 | 图标 | 含义 |
|------|------|------|
| INIT | 🚀 | 系统初始化、参数确认 |
| KB | 📖 | 知识库加载 |
| ANSWER | 📝 | 答卷读取与解析 |
| SEARCH | 🔍 | 搜索工具调用（Tool Calling） |
| LLM | 🤖 | 大模型调用（含耗时和 token 统计） |
| REPORT | 📊 | 报告生成 |
| DONE | ✅ | 流程完成 |
| ERROR | ❌ | 错误与异常 |

### 文件日志

- 位置：`logs/eval_YYYYMMDD_HHMMSS.log`
- 级别：DEBUG（记录完整细节，含工具调用参数和返回值）

---

## 十、安全与协作设计

```
┌─────────────────────────────────────────────┐
│              Git 仓库（共享）                 │
│                                             │
│  ✅ 可提交：所有 .py / .md / .json / .txt    │
│  ✅ 可提交：.env.example（模板）             │
│  ✅ 可提交：requirements.txt                │
│  ✅ 可提交：.gitignore                      │
│                                             │
│  ❌ 不提交：.env（含 API Key）               │
│  ❌ 不提交：output/（生成的报告）            │
│  ❌ 不提交：logs/（运行日志）                │
│  ❌ 不提交：__pycache__/                    │
│  ❌ 不提交：internal_kb/（内部资料）         │
└─────────────────────────────────────────────┘
```

---

## 十一、运行命令速查

```bash
# ========================
# 环境准备
# ========================
pip install -r requirements.txt
cp .env.example .env  # 编辑填入真实 API Key

# ========================
# 方式一：命令行直接执行
# ========================
python main.py sample_answers.md                    # 最简调用
python main.py answers.md ec2-basics                # 指定 checklist
python main.py answers.md ec2-basics 张三           # 完整参数

# ========================
# 方式二：启动 FastAPI 服务
# ========================
# 开发模式（自动重载）
uvicorn api:app --host 0.0.0.0 --port 8000 --reload

# 生产模式
uvicorn api:app --host 0.0.0.0 --port 8000 --workers 2

# 新人使用前端页面：
#   http://<EC2公网IP>:8000/
#
# 开发者 Swagger UI：
#   http://<EC2公网IP>:8000/api/docs

# 健康检查
curl http://localhost:8000/health

# curl 上传评估
curl -X POST http://localhost:8000/evaluate \
  -F "file=@sample_answers.md" \
  -F "student_name=张三" \
  -F "checklist_id=ec2-basics"

# ========================
# 查看日志
# ========================
cat logs/eval_20260605_143201.log
```

---

## 十二、FastAPI 接口说明

| 路径 | 方法 | 用途 | 面向 |
|------|------|------|------|
| `/` | GET | 新人友好的可视化前端页面 | 新人 |
| `/evaluate` | POST | 后端评估 API（前端通过 Fetch 调用） | 前端/开发者 |
| `/health` | GET | 健康检查（容器探针） | 运维 |
| `/api/docs` | GET | Swagger UI（开发者调试用） | 开发者 |

### 前端交互流程

```
浏览器访问 /
  → 展示极简上传页面（标题 + 文件框 + 按钮）
  → 用户选择文件，点击"开始评估"
  → 前端 Fetch POST /evaluate（带 FormData）
  → 显示 Loading 动画
  → 拿到 Markdown 文本结果
  → 直接渲染到页面，无任何技术细节暴露
```

---

## 十三、配置项速查

| 环境变量 | 说明 | 默认值 |
|----------|------|--------|
| `LLM_PROVIDER` | LLM 提供者名称 | `openai` |
| `{PROVIDER}_API_KEY` | 对应 LLM 的 API Key | — |
| `{PROVIDER}_BASE_URL` | 对应 LLM 的 API 地址 | — |
| `{PROVIDER}_MODEL` | 对应 LLM 的模型名 | — |
| `TEMPERATURE` | 生成温度 | `0.2` |
| `MAX_TOKENS` | 最大输出 token | `4096` |
| `KNOWLEDGE_PROVIDER` | 知识库来源 | `local` |
| `KNOWLEDGE_LOCAL_FILE` | 本地知识库文件 | `sample_knowledge_base.json` |
| `ENABLE_TOOL_CALLING` | 是否启用 Tool Calling | `true` |
| `INTERNAL_KB_DIR` | 内部知识库目录 | `./internal_kb` |
| `SEARCH_API_KEY` | 外部搜索 API Key | 空（禁用） |
| `SEARCH_API_URL` | 外部搜索 API 地址 | 空（禁用） |
| `OUTPUT_DIR` | 报告输出目录 | `./output` |

---

## 十四、扩展点

| 扩展方向 | 修改位置 | 说明 |
|----------|----------|------|
| 新增 LLM | `.env` | 加三行配置即可，代码不动 |
| 内部知识库正式接入 | `search_tools.py` → `search_internal_kb()` | 替换 Mock 为向量数据库调用 |
| AWS 文档搜索正式接入 | `search_tools.py` → `search_aws_docs()` | 配置 SEARCH_API_KEY/URL |
| 新增数据源 | `knowledge_provider.py` | 继承 `KnowledgeProvider` |
| 修改评估标准 | `prompts.py` | 调整 System Prompt |
| 报告格式 | `report_generator.py` | 新增 PDF / HTML 等输出 |
| 批量评估 | `main.py` | 循环读取多份答卷 |
