# PROJECTS（项目状态）

> 用于保存不同 AI 项目的当前状态。建议每个项目一个子目录或一个 Markdown 文件，记录：目标、技术选型、当前进度、关键决策、待办。

## 当前项目组合

### 主项目：企业知识库 RAG 后端（阶段 A/B/C 已完成，阶段 D 工程化进行中）

- **目标**：构建可运行、可展示的知识库问答后端，优先贴合 Django 后端经验。
- **技术路线**：本地 Qwen3-Embedding + 余弦检索 + 模型判断拒答 → DRF 后端化 → 切分与检索参数实验 → Redis/Celery/Docker 工程化。
- **仓库**：GitHub `hudejintou/ai-knowledge-base`（main 分支）。
- **当前状态（2026-10-31）**：阶段 D 进行中——Redis 缓存（实验 20/21 命中毫秒级）、日志错误处理、Celery 异步入库（实验 22 验证不阻塞）均完成；**仅余 Docker Compose 一键编排**。
- **当前进展**：
  - 2026-10-21：阶段 A 收官、首次推送 GitHub；阶段 B 起步（backend/ Django、/api/ask/、Document 入库、检索切数据库、接口测试，实验 11 基线 100%）。
  - 2026-10-22：config.py 解耦完成、401 解决；阶段 C 开工——实验 12~14（top_k 3/1 对照、严格 Prompt 收紧，RUNS=3 稳定验证）。
  - 2026-10-26：阶段 C 收尾（实验 15~19，候选默认值 400/50/3）；Prompt 漂移修复；/api/ask/ 端到端回归通过。
  - 2026-10-31：阶段 D 推进——问答缓存上真实 Redis（e151eba，命中约快三个数量级）、接口错误处理与日志（b3d54ea）、文档入库改 Celery 异步任务（f9cb70e，POST /api/documents/ 202 即返回，broker 故障 503 保留文档）；实验 22 测得接口 202 响应 318ms < 任务执行 592ms（详见 `LOGS/2026-10-31-阶段D-Celery异步入库.md`）。
- **待办（阶段 D）**：
  - [x] Redis 缓存相同问题回答（实验 20/21）
  - [x] Celery 异步文档入库（f9cb70e + 实验 22）
  - [x] Docker + docker-compose 一键启动（编排 runserver + worker + Redis；容器内访问宿主机 LM Studio 需 host.docker.internal）
  - [x] 日志与错误处理（b3d54ea）
- **遗留（阶段 B/C 带过来）**：
  - [x] Prompt 漂移修复（2026-10-26 晚：config.py 已与 rag_v1.py 严格版同步）
  - [x] /api/ask/ 端到端 curl 三场景回归（2026-10-26 通过）
  - [ ] 候选默认值（400/50/3）待更大规模语料验证后固定到代码参数
- **下一步**：Docker Compose 一键启动全栈（含 celery worker 与 Redis 服务编排），完成后阶段 D 验收，进入阶段 E。

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
