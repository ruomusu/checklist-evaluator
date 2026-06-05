# 新人 Checklist 自动评估系统 — 架构与数据流

## 一、系统总览

```
┌─────────────────────────────────────────────────────────────────────┐
│                        CLI 命令行入口 (main.py)                      │
│   python main.py <答卷.md> [checklist_id] [搜索上下文.txt] [姓名]    │
└────────────────────────────────┬────────────────────────────────────┘
                                 │
                                 ▼
┌─────────────────────────────────────────────────────────────────────┐
│                         流程编排层 (main.py)                         │
│                                                                     │
│  1. 获取知识库  →  2. 解析答卷  →  3. 加载搜索上下文  →  4. 评估     │
└───┬────────────────────┬───────────────────┬────────────────┬───────┘
    │                    │                   │                │
    ▼                    ▼                   ▼                ▼
┌────────┐      ┌──────────────┐    ┌──────────────┐  ┌────────────┐
│Knowledge│      │  答卷解析器   │    │ 搜索上下文   │  │  Evaluator │
│Provider │      │ (Markdown/   │    │  注入接口    │  │  评估引擎   │
│ (动态)  │      │   TXT 解析)  │    │  (预留)      │  │            │
└────────┘      └──────────────┘    └──────────────┘  └─────┬──────┘
                                                            │
                                                            ▼
                                                    ┌──────────────┐
                                                    │   OpenAI /   │
                                                    │  LLM API     │
                                                    └──────┬───────┘
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
project/checkList/
├── main.py                  # 主入口，流程编排，CLI 参数解析
├── config.py                # 全局配置（环境变量读取）
├── logger.py                # 结构化日志（终端彩色 + 文件记录）
├── models.py                # Pydantic 数据模型定义
├── prompts.py               # LLM System Prompt 与 User Prompt 模板
├── evaluator.py             # 核心评估引擎（LLM 调用 + 响应解析）
├── knowledge_provider.py    # 知识库抽象层（本地/API/数据库）
├── report_generator.py      # 报告生成器（Markdown 输出）
├── sample_knowledge_base.json  # 示例知识库数据
├── sample_answers.md        # 示例新人答卷
├── requirements.txt         # Python 依赖
├── .env.example             # 环境变量模板（安全，可提交）
├── .gitignore               # Git 忽略规则
└── ARCHITECTURE.md          # 本文档
```

---

## 三、核心数据流

```
                    ┌───────────────────────────┐
                    │   输入数据源（三路输入）     │
                    └─────────┬─────────────────┘
                              │
          ┌───────────────────┼───────────────────┐
          │                   │                   │
          ▼                   ▼                   ▼
┌──────────────────┐ ┌────────────────┐ ┌─────────────────────┐
│  标准知识库       │ │  新人答卷       │ │  外部搜索上下文      │
│                  │ │                │ │  (RAG/Kendra/插件)   │
│ · question_id    │ │ · question_id  │ │                     │
│ · question       │ │ · answer_text  │ │  纯文本注入          │
│ · reference_answer│ │               │ │                     │
│ · reference_links│ │                │ │                     │
└────────┬─────────┘ └───────┬────────┘ └──────────┬──────────┘
         │                   │                     │
         └───────────────────┼─────────────────────┘
                             │
                             ▼
                 ┌───────────────────────┐
                 │    Prompt 组装        │
                 │                       │
                 │  System Prompt        │
                 │  (判卷专家角色)        │
                 │         +             │
                 │  User Prompt          │
                 │  (题目+答案+搜索资料)  │
                 └───────────┬───────────┘
                             │
                             ▼
                 ┌───────────────────────┐
                 │    LLM API 调用       │
                 │  (OpenAI / Bedrock)   │
                 └───────────┬───────────┘
                             │
                             ▼ JSON 响应
                 ┌───────────────────────┐
                 │    响应解析            │
                 │  JSON → Pydantic 模型 │
                 └───────────┬───────────┘
                             │
                             ▼
                 ┌───────────────────────┐
                 │  EvaluationReport     │
                 │                       │
                 │  · question_evaluations│
                 │  · focus_areas        │
                 │  · follow_up_questions│
                 │  · overall_summary    │
                 └───────────┬───────────┘
                             │
                             ▼
                 ┌───────────────────────┐
                 │  Markdown 报告输出    │
                 │                       │
                 │  → 终端打印           │
                 │  → output/*.md 文件   │
                 └───────────────────────┘
```

---

## 四、知识库 Provider 架构

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

切换方式：修改 `.env` 中的 `KNOWLEDGE_PROVIDER` 变量即可，代码无需改动。

| 环境变量 | 值 | 说明 |
|----------|-----|------|
| `KNOWLEDGE_PROVIDER` | `local` | 读取本地 JSON 文件（开发调试用） |
| `KNOWLEDGE_PROVIDER` | `api` | 调用外部 REST API 获取 |
| `KNOWLEDGE_PROVIDER` | `database` | 从关系型数据库查询 |

---

## 五、模块调用关系

```
main.py
  ├── config.py          (读取 .env 配置)
  ├── logger.py          (全局日志)
  ├── knowledge_provider.py
  │     ├── create_provider()     → 工厂函数
  │     ├── LocalFileProvider     → json.load()
  │     ├── APIProvider           → httpx.Client.get()
  │     └── DatabaseProvider      → sqlite3 / pymysql
  ├── evaluator.py
  │     ├── _format_knowledge_base()   → 知识库 → 文本
  │     ├── _format_student_answers()  → 答案 → 文本
  │     ├── _call_llm()               → OpenAI API
  │     └── _parse_response()         → JSON → Pydantic
  └── report_generator.py
        ├── generate_markdown()        → Report → MD 文本
        └── save_report()              → 写入文件
```

---

## 六、数据模型关系

```
KnowledgeItem          StudentAnswer         EvaluationReport
┌──────────────┐      ┌──────────────┐      ┌───────────────────────┐
│ question_id  │      │ question_id  │      │ student_name          │
│ question     │      │ answer_text  │      │ total_questions       │
│ ref_answer   │      └──────────────┘      │ mastered_count        │
│ ref_links[]  │                            │ ambiguous_count       │
└──────────────┘                            │ weak_count            │
                                            │ question_evaluations[]│
QuestionEvaluation     FocusArea            │ focus_areas[]         │
┌──────────────────┐  ┌──────────────────┐  │ follow_up_questions[] │
│ question_id      │  │ topic            │  │ overall_summary       │
│ question         │  │ related_questions│  └───────────────────────┘
│ mastery_level    │  │ suggestion       │
│ strengths[]      │  └──────────────────┘  FollowUpQuestion
│ missing_points[] │                        ┌──────────────────┐
│ comment          │                        │ question_id      │
└──────────────────┘                        │ follow_up        │
                                            │ purpose          │
MasteryLevel (Enum)                         └──────────────────┘
├── 掌握
├── 模棱两可
└── 薄弱
```

---

## 七、日志体系

### 终端输出（彩色，按阶段标识）

| 阶段 | 图标 | 颜色 | 含义 |
|------|------|------|------|
| INIT | 🚀 | 绿色 | 系统初始化、参数确认 |
| KB | 📖 | 绿色 | 知识库加载 |
| ANSWER | 📝 | 绿色 | 答卷读取与解析 |
| SEARCH | 🔍 | 绿色 | 外部搜索上下文加载 |
| LLM | 🤖 | 绿色 | 大模型调用（含耗时和 token 统计） |
| REPORT | 📊 | 绿色 | 报告生成 |
| DONE | ✅ | 绿色 | 流程完成 |
| ERROR | ❌ | 红色 | 错误与异常 |

### 文件日志

- 位置：`logs/eval_YYYYMMDD_HHMMSS.log`
- 级别：DEBUG（记录完整细节，含 Prompt 长度、解析过程等）
- 用途：事后追溯问题、对比多次执行结果

---

## 八、安全与协作设计

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
│  ❌ 不提交：*.pem / *.key                   │
└─────────────────────────────────────────────┘
```

每位开发者在各自的 EC2 上维护自己的 `.env` 文件，机密信息不会通过 Git 传播。

---

## 九、运行命令速查

```bash
# 环境准备（EC2 + Miniconda）
conda activate checklist-eval
pip install -r requirements.txt
cp .env.example .env  # 编辑填入真实 API Key

# 执行评估
python main.py sample_answers.md                          # 最简调用
python main.py answers.md ec2-basics                      # 指定 checklist
python main.py answers.md ec2-basics search.txt 张三      # 完整参数

# 查看历史日志
cat logs/eval_20260605_143201.log
```

---

## 十、扩展点

| 扩展方向 | 修改位置 | 说明 |
|----------|----------|------|
| 新增数据源 | `knowledge_provider.py` | 继承 `KnowledgeProvider`，实现新 Provider |
| 替换 LLM | `config.py` + `evaluator.py` | 修改 `OPENAI_BASE_URL` 指向 Bedrock/本地模型 |
| 集成 RAG | `main.py` 的 `load_search_context()` | 替换为 RAG 检索逻辑 |
| 修改评估标准 | `prompts.py` | 调整 System Prompt 中的判定阈值 |
| 报告格式 | `report_generator.py` | 新增 PDF / HTML 等输出格式 |
| 批量评估 | `main.py` | 循环读取多份答卷，批量生成报告 |
