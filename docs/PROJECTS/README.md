# PROJECTS（项目状态）

> 用于保存不同 AI 项目的当前状态。建议每个项目一个子目录或一个 Markdown 文件，记录：目标、技术选型、当前进度、关键决策、待办。

## 当前项目组合

### 主项目：企业知识库 RAG 后端（进行中：检索与拒答已验证，阶段 A 冲刺可运行版）

- **目标**：构建可运行、可展示的知识库问答后端，优先贴合 Django 后端经验。
- **技术路线**：先用 Python 验证本地 Embedding + 余弦相似度检索；随后推进文档切分、向量索引、引用、流式问答、Django/DRF、Redis/Celery、Docker Compose 与小型评估集。
- **当前状态（2026-10-19）**：检索与拒答判断已定量验证，尚未接入后端；主线排期见 `docs/MEMORY/AI_ROADMAP.md`「接下来学习大纲」阶段 A~E。
- **当前进展（2026-10-19）**：
  - Embedding 定案 **Qwen3-Embedding-0.6B**（LM Studio 本地），对比 Nomic 5/5 全中（2026-10-17）。
  - 拒答方案定案：纯相似度阈值挡不住"同主题但语料无答案"（实验 2 证伪）；改由回答模型判断可答性，输出 `[NO_ANSWER]`（实验 3、4）。
  - 评估体系：EVAL_SET 36 题 + HOLDOUT_SET 10 题；`evals/eval_all.py` 自动化评估，支持多次运行统计稳定性，结果 JSON 存 `evals/runs/`。
  - 稳定性：RUNS=3 总体正确率 98.55%~100%，边界样本 1 条（"Function Calling 怎么做参数校验？"）。
  - 工程整理：目录分层 `rag/`、`evals/`、`experiments/`、`docs/`；根目录 `python -m` 运行，迁移后回归指标一致；`.env` 管理 Key 并已加入 `.gitignore`。
- **待办**：
  - [ ] 回归测试 `python -m evals.eval_all`，记录总体正确率（回填 EXPERIMENTS.md 实验 10）
  - [ ] 确认智谱旧 Key 已重置
  - [ ] 提交 Git，确认 `.env` 未被跟踪
- **下一步**：阶段 A（回归测试 → `rag/chat.py` 命令行入口 → Git + README），之后阶段 B 用 DRF 后端化。

### 小项目：轻量 Function Calling / Agent（原型已完成）

- `test.py` 已实现真实流式输出、天气/计算工具、多步工具调用循环；计算器使用 AST 安全求值，不使用 `eval`。
- 下一步以安全测试与可理解性完善为主；暂不引入重型 Agent 框架。

### 其他项目想法（暂缓）

- 微信小程序「汽车维修店客户管理」：车牌 OCR + 客户管理（微信云开发），可作为既有真实业务案例。
- 本地 AI 助手、自动化工具等暂不并行立项，避免偏离“1 个主项目 + 1 个小项目”的策略。

## 如何新增一个项目

1. 在 `PROJECTS/` 下新建目录，如 `PROJECTS/rag-knowledge-base/`。
2. 在该目录创建 `README.md`，写明：目标、技术栈、进度、关键决策、下一步。
3. 重要实验/过程记录同时写入 `LOGS/`。
