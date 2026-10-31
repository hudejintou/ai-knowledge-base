# 企业知识库 RAG 后端

基于本地 Embedding 与智谱大模型的知识库问答原型。检索到的资料能支撑回答时才作答，否则拒答。

## 功能

- **本地 Embedding 检索**：LM Studio 运行 `text-embedding-qwen3-embedding-0.6b`，余弦相似度检索。
- **可答性判断**：回答模型（智谱 `glm-5.3-flash`）在资料不足时输出 `[NO_ANSWER]`，由代码识别并拒答。
- **评估体系**：46 题评估集（EVAL_SET 36 题 + HOLDOUT_SET 10 题），支持多次运行统计稳定性。

## 环境要求

- macOS（Apple Silicon，16GB 内存）
- Python 3.13
- [LM Studio](https://lmstudio.ai/)，已加载 `text-embedding-qwen3-embedding-0.6b` 并启动本地服务（默认 `http://127.0.0.1:1234/v1`）
- 智谱 AI API Key

## 安装

```bash
pip install openai numpy
```

## 配置

```bash
export ZHIPU_API_KEY="你的智谱 API Key"
```

也可以写入项目根目录的 `.env`（已被 `.gitignore` 忽略，**不要提交**）。

## 运行问答

在项目根目录执行，必须用 `python -m`：

```bash
python -m rag.chat
```

输入问题回车即可，输入 `q` 退出。例如：

- `怎么做缓存？`：会给出基于资料的回答。
- `今天股市怎么样？`：会显示 `[拒答]`。

## Docker 启动（可选）

一条命令启动 Redis + Django（web）+ Celery worker 全栈：

```bash
docker compose up --build
```

- 启动前确认项目根目录有 `.env`（含 `ZHIPU_API_KEY`），会以环境变量注入容器，不进镜像。
- **LM Studio 需开启局域网访问**（设置里勾选 Serve on Local Network）：容器通过 `host.docker.internal:1234` 访问宿主机的 LM Studio，它只监听 `127.0.0.1` 时容器内连不上。
- 启动后 `web` 会自动执行数据库迁移，接口在 `http://localhost:8000/api/ask/`。

## 运行评估

```bash
python -m evals.eval_all
```

结果保存在 `evals/runs/`。

## 项目结构

| 路径 | 说明 |
| --- | --- |
| `rag/corpus.py` | 知识库语料与评估题 |
| `rag/rag_v1.py` | 检索、判断与回答核心函数 |
| `rag/chat.py` | 命令行问答入口 |
| `evals/` | 评估脚本与结果 |
| `experiments/` | 一次性实验脚本（早期 Function Calling Demo 见 `experiments/test.py`，说明见 `experiments/README.md`） |
| `docs/` | 学习与实验记录 |