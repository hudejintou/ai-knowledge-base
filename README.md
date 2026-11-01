# 企业知识库 RAG 后端

基于本地 Embedding（LM Studio）与智谱大模型的知识库问答后端。检索到的资料能支撑回答时才作答，否则拒答；回答中的 `[n]` 标注对应的引用来源。

## 功能

- **本地 Embedding 检索**：LM Studio 运行 `text-embedding-qwen3-embedding-0.6b`，余弦相似度检索，向量存于 SQLite。
- **两种问答模式**（由环境变量 `QA_MODE` 控制）：
  - `tools`（默认）：模型自主决定是否检索、可改写查询，后端执行检索并回传，最多 3 轮，每轮最多 2 次检索，超限强制作答。
  - `baseline`：固定检索一次（top-3）后直接作答，不返回引用。
- **可答性判断**：资料不足时模型输出 `[NO_ANSWER]`，由代码识别并拒答。
- **引用来源**：回答中的 `[n]` 与 `sources` 字段对应，只返回回答中实际引用的资料。
- **缓存**：Redis 缓存完整结果，TTL 1 小时，拒答结果也缓存；缓存键包含模式，切换模式不会串答案。新文档入库后清空问答缓存。
- **异步入库**：文档入库由 Celery 计算向量，支持指数退避重试；失败的文档可用 `backfill_embeddings` 补算。
- **错误处理**：上游鉴权失败返回 502，连接失败、超时、限流返回 503，未预期错误返回 500 且只返回通用信息，完整堆栈写入日志。

## 架构

```
客户端
  │  POST /api/ask/
  ▼
AskView ──► Redis 缓存（命中则直接返回）
  │ 未命中
  ▼
按 QA_MODE 分发
  ├─ tools    ：agent.ask_with_tools（模型 ⇄ search_knowledge 工具，循环）
  └─ baseline ：service.ask_with_db（固定检索一次）
                    │
                    ▼
        embedding（LM Studio）→ 余弦检索（SQLite Document 表）→ 智谱 glm-5.3-flash
```

文档入库：`POST /api/documents/` 保存文本并返回 202 → Celery worker 计算向量 → 清空问答缓存。

## 接口

| 方法 | 路径 | 请求 | 响应 |
| --- | --- | --- | --- |
| POST | `/api/ask/` | `{"question": "..."}` | 200：`{"refused", "answer", "sources": [{"n", "text"}]}`；400：问题为空；502/503/500：上游或内部错误 |
| POST | `/api/documents/` | `{"content": "..."}` | 202：`{"id", "status": "pending"}`；400：内容为空；503：任务队列不可用（文档已保存） |
| GET | `/api/documents/<id>/` | — | 200：`{"id", "status": "ready" \| "pending", "content_length"}`；404：文档不存在 |

注意：`baseline` 模式下 `sources` 恒为空列表。

## 快速开始（Docker）

1. 在项目根目录创建 `.env`，写入 `ZHIPU_API_KEY=你的密钥`。`.env` 已被 `.gitignore` 和 `.dockerignore` 排除，不会进入镜像或仓库。
2. 在 LM Studio 中加载 `text-embedding-qwen3-embedding-0.6b` 并启动服务，开启 **Serve on Local Network**。容器通过 `host.docker.internal:1234` 访问宿主机，若 LM Studio 只监听 `127.0.0.1`，容器内无法连接。
3. 启动全部服务：

   ```bash
   docker compose up --build -d
   ```

4. 首次启动后导入语料并计算向量（**会清空 Document 表，只在初始化时执行**）：

   ```bash
   docker compose exec web python manage.py load_corpus
   docker compose exec web python manage.py embed_documents
   ```

5. 测试：

   ```bash
   curl -s -X POST http://127.0.0.1:8000/api/ask/ -H "Content-Type: application/json" -d '{"question":"Redis 数据怎么持久化？"}'
   ```

**切换问答模式**：改用基线模式时执行 `QA_MODE=baseline docker compose up -d --force-recreate web`。改动 `docker-compose.yml` 后需要重建容器；仅改 shell 环境变量时 compose 不一定会重建，所以加 `--force-recreate`。恢复默认执行 `docker compose up -d --force-recreate web`。

## 本机开发

```bash
cd backend && python manage.py test qa     # 运行单元测试
```

本机运行服务时需先加载 `.env`，再启动：

```bash
set -a && source ../.env && set +a && python manage.py runserver 8000
```

本机 Redis 与 Celery 的用法与容器相同，地址由 `REDIS_URL` 与 `CELERY_BROKER_URL` 控制，默认指向 `127.0.0.1`。

## 评估

评估命令需在容器内运行，因为容器数据库只包含语料（本机数据库可能混有测试文档，会影响结果）：

```bash
docker compose exec web python manage.py eval_tools --runs 1
```

按套件或题号筛选：

```bash
docker compose exec web python manage.py eval_tools --suite multi --ids 1,3,4 --runs 3
```

结果写入容器内 `/app/evals/runs/`，取回本机：

```bash
docker compose cp web:/app/evals/runs/. ./evals/runs/
```

### 主要结果

| 实验 | 条件 | 结果 | 局限 |
| --- | --- | --- | --- |
| 25 | TOP_K=3，eval 36 题 + holdout 10 题，两种模式 | 拒答正确率均为 100% | 单次运行；holdout 非盲测 |
| 26 | 加入多跳/间接说法题 14 题（multi），TOP_K=3 | 三个套件拒答正确率均为 100%，覆盖率均为 1.0 | 题目设计时未测基线上限，区分度不足 |
| 27 | 同上，TOP_K=1 | eval 100%/100%；holdout 90%/90%；multi 拒答 92.86%（工具）/ 85.71%（基线），覆盖率 0.85 / 0.75 | 单次运行，差异约为一题 |
| 27 补充 | multi 差异题 #1、#3、#4，各 3 次 | 工具拒答 9/9，基线 5/9；覆盖率 0.83 / 0.50 | 题目由差异结果挑选，非独立检验 |
| 28 | 语料扩充为 44 条，仅检索的健康检查（12 题） | top-3 召回 11/12（91.67%） | 整段入库未切块；检查集仅 12 题 |
| 28 | 扩充语料后回归 eval 36 题 | 两种模式均为 100% | 单次运行 |
| 29 | 默认模式切换为 `tools` | 依据实验 28 的回归结果 | 只有 eval 一组回归；工具模式每题多一次模型调用，成本更高 |

以上结果都是小样本、单次运行，不能证明工具调用在一般情况下优于基线。工具模式的主要价值体现在需要多次检索才能拿全资料的问题上（实验 27 补充），但题目是人工设计并筛选的。

## 已知限制

- 候选默认值（块大小 400、重叠 50、top_k 3）尚未固定到代码，仅在 24 段语料上验证过。
- 文档只接受纯文本，不支持 PDF、Word 等文件解析。
- 不支持流式输出。
- SQLite 不适合多进程并发写入；正式部署应改用 PostgreSQL。
- 没有用户体系和权限控制，接口无鉴权。
- `DEBUG` 默认开启，部署前需通过 `DJANGO_DEBUG=0` 关闭。
- 管理后台没有静态文件，样式缺失，不影响 API。
- 语料由 AI 改写，内容已人工核对，但仍建议抽查。

## 项目结构

| 路径 | 说明 |
| --- | --- |
| `backend/` | Django 工程：`config/`（配置、Celery、WSGI）、`qa/`（问答、缓存、Agent、任务、管理命令、测试） |
| `rag/` | 核心模块与语料：`corpus.py`（DOCS 20 条、ALL_DOCS 44 条、评估题集）、`rag_v1.py`、`chat.py`、`data/` |
| `evals/` | 评估脚本与结果（`runs/` 为 JSON 结果） |
| `experiments/` | 一次性实验脚本（切分实验、检索实验、早期 Function Calling Demo） |
| `docs/` | 学习与实验记录：`EXPERIMENTS.md`、`LOGS/`、`MEMORY/`、`PROJECTS/` |
| `Dockerfile`、`docker-compose.yml`、`requirements.txt` | 容器化部署 |