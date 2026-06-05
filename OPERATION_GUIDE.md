# 操作指南

## 一、环境准备

### 1.1 安装依赖

```bash
pip install -r requirements.txt
```

### 1.2 配置环境变量

```bash
cp .env.example .env
```

编辑 `.env` 文件，至少填写以下内容：

```bash
# 选择 LLM 提供者（openai / qwen / deepseek 等）
LLM_PROVIDER=qwen

# 对应的 API 配置
QWEN_API_KEY=sk-your-real-key
QWEN_BASE_URL=https://dashscope.aliyuncs.com/compatible-mode/v1
QWEN_MODEL=qwen-plus
```

### 1.3 准备知识库

默认使用本地 JSON 文件：

```bash
KNOWLEDGE_PROVIDER=local
KNOWLEDGE_LOCAL_FILE=sample_knowledge_base.json
```

---

## 二、运行方式

### 方式一：命令行（快速测试）

```bash
# 最简调用
python main.py sample_answers.md

# 指定 checklist 和姓名
python main.py answers.md ec2-basics 张三
```

### 方式二：FastAPI 服务（推荐，可视化测试）

#### 启动服务

```bash
# 开发模式（文件变动自动重载）
uvicorn api:app --host 0.0.0.0 --port 8000 --reload

# 生产模式（多 worker）
uvicorn api:app --host 0.0.0.0 --port 8000 --workers 2
```

#### 新人使用（前端页面）

浏览器打开 `http://<你的EC2公网IP>:8000/`，即可看到极简上传页面：

1. 输入姓名
2. 选择答卷文件（.md / .txt）
3. 点击"开始评估"
4. 等待加载动画完成，结果直接显示在页面上

#### 开发者调试（Swagger UI）

浏览器打开 `http://<你的EC2公网IP>:8000/api/docs`

#### 使用 curl 测试

```bash
# 健康检查
curl http://localhost:8000/health

# 上传文件评估
curl -X POST http://localhost:8000/evaluate \
  -F "file=@sample_answers.md" \
  -F "student_name=张三" \
  -F "checklist_id=ec2-basics"
```

---

## 三、配置说明

### 3.1 LLM 模型切换

只需修改 `.env` 中的 `LLM_PROVIDER` 和对应的三行配置：

```bash
# 切换到 OpenAI
LLM_PROVIDER=openai
OPENAI_API_KEY=sk-xxx
OPENAI_BASE_URL=https://api.openai.com/v1
OPENAI_MODEL=gpt-4o

# 切换到千问
LLM_PROVIDER=qwen
QWEN_API_KEY=sk-xxx
QWEN_BASE_URL=https://dashscope.aliyuncs.com/compatible-mode/v1
QWEN_MODEL=qwen-plus

# 切换到 DeepSeek
LLM_PROVIDER=deepseek
DEEPSEEK_API_KEY=sk-xxx
DEEPSEEK_BASE_URL=https://api.deepseek.com/v1
DEEPSEEK_MODEL=deepseek-chat
```

新增任意模型只需加三行，代码不动。

### 3.2 Tool Calling 开关

```bash
# 启用（大模型可主动搜索补充资料）
ENABLE_TOOL_CALLING=true

# 禁用（仅基于标准答案评估，速度更快）
ENABLE_TOOL_CALLING=false
```

### 3.3 搜索工具配置

**内部知识库（Mock 模式）：**

在 `./internal_kb/` 目录下放入 `.md` 或 `.txt` 文件即可。大模型判断需要时会自动检索。

```bash
INTERNAL_KB_DIR=./internal_kb
```

**外部 AWS 文档搜索（需搜索 API）：**

```bash
# 接入 Tavily 搜索 API（示例）
SEARCH_API_KEY=tvly-your-key
SEARCH_API_URL=https://api.tavily.com
```

留空则该工具返回空结果，大模型将仅依赖自身知识。

---

## 四、答卷文件格式

支持 `.md`、`.txt` 和 `.docx` 格式，推荐以下结构：

```markdown
## Q1
这是第一题的回答内容...

## Q2
这是第二题的回答内容...

## Q3
这是第三题的回答内容...
```

也支持纯数字编号：

```markdown
## 1
回答...

## 2
回答...
```

如果文件没有明确的题号标记，系统会按段落顺序与知识库题目一一对应。

---

## 五、输出说明

### 报告格式

评估报告为极简 Markdown，示例：

```markdown
# Checklist 评估报告 — 张三

评估时间: 2026-06-05 15:30
总计 5 题 | ✅ 掌握 2 | ⚠️ 模棱两可 2 | ❌ 薄弱 1

---

**Q1** ✅ 掌握

**Q2** ⚠️ 模棱两可
- 未提及 EBS 快照的跨区域复制
- 混淆了实例存储（Instance Store）与 EBS 的持久性差异

**Q3** ❌ 薄弱
- 完全漏掉安全组（Security Group）是有状态的
- 错误描述网络 ACL（Network ACL）为有状态防火墙
💡 建议将全球区链接替换为中国区链接
```

### 报告存储

- 终端直接打印（CLI 模式）
- API 模式直接返回文本
- 同时保存到 `./output/evaluation_report_YYYYMMDD_HHMMSS.md`

### 日志

- 终端：彩色带图标
- 文件：`./logs/eval_YYYYMMDD_HHMMSS.log`（DEBUG 级别完整记录）

---

## 六、常见问题

| 问题 | 解决 |
|------|------|
| `ValueError: LLM_PROVIDER=xxx，但未找到环境变量...` | `.env` 中缺少对应的 API_KEY/BASE_URL/MODEL |
| `文件编码错误` | 确保答卷文件为 UTF-8 编码 |
| `不支持旧版 .doc 格式` | 用 Word 另存为 .docx 后重新上传 |
| `无法从文件中解析出任何回答` | 检查答卷格式，需要 `## Q1` 或 `## 1` 作为分隔 |
| Tool Calling 不生效 | 确认 `ENABLE_TOOL_CALLING=true`，且 LLM 支持 function calling |
| 搜索工具返回空 | 正常情况——未配置 SEARCH_API 时工具返回空，大模型用自身知识判定 |

---

## 七、安全注意事项

- `.env` 文件包含 API Key，已在 `.gitignore` 中排除，绝不提交
- `internal_kb/` 目录包含内部资料，也不应提交
- API 服务当前无鉴权，仅供内部测试使用。生产部署前需加入认证机制
