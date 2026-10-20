"""Embedding 模型对比：Nomic-embed-v1.5 vs Qwen3-Embedding-0.6B（同一中文小语料）。

目的：验证 2026-10-16 的结论——Nomic 中文语义排序弱，Qwen3-Embedding 是否更好。
两个模型各按官方推荐用法：
- Nomic：文档加 search_document: 前缀，查询加 search_query: 前缀
- Qwen3-Embedding：文档不加前缀，查询加 Instruct/Query 指令前缀

指标：正确文档的排名（rank，1 最好）与 margin（正确文档分数 - 最高分，>0 即排第一）。
只依赖 LM Studio 本地服务，不需要云端 API Key。
"""

import numpy as np
from openai import OpenAI

client = OpenAI(api_key="lm-studio", base_url="http://127.0.0.1:1234/v1")

NOMIC_INSTRUCT = "search_document: "
NOMIC_QUERY = "search_query: "
QWEN_INSTRUCT = (
    "Instruct: Given a web search query, retrieve relevant passages that answer the query\nQuery: "
)

MODELS = {
    "nomic-v1.5": {
        "id": "text-embedding-nomic-embed-text-v1.5@q8_0",
        "doc": lambda d: NOMIC_INSTRUCT + d,
        "query": lambda q: NOMIC_QUERY + q,
    },
    "qwen3-emb-0.6b": {
        "id": "text-embedding-qwen3-embedding-0.6b",
        "doc": lambda d: d,
        "query": lambda q: QWEN_INSTRUCT + q,
    },
}

DOCS = [
    "Redis 是基于内存的键值数据库。常见用途是做缓存：把热点数据放进 Redis，设置过期时间，减少数据库查询压力。",
    "Celery 是 Python 的分布式任务队列。适合处理耗时任务，如发送邮件、生成报表，通过 Redis 或 RabbitMQ 作为消息中间件异步执行。",
    "Django ORM 把数据库表映射成 Python 类。通过 Model 定义字段，用 QuerySet 查询，避免手写 SQL。",
    "Docker 用容器打包应用及其依赖。通过 Dockerfile 构建镜像，docker-compose 可以一键启动多个服务。",
    "RAG 先检索相关文档，再让大模型基于文档回答，用来减少幻觉并接入私有知识。",
]
DOC_KEYS = ["Redis", "Celery", "Django", "Docker", "RAG"]

QUERIES = [
    ("怎么做缓存？", "Redis"),
    ("后台异步跑任务用什么？", "Celery"),
    ("怎么把数据库表映射成 Python 类？", "Django"),
    ("怎么打包应用和依赖？", "Docker"),
    ("什么是 RAG？", "RAG"),
]


def embed(model_id, texts):
    resp = client.embeddings.create(model=model_id, input=texts)
    return np.array([d.embedding for d in resp.data], dtype=np.float32)


def evaluate(cfg):
    doc_vecs = embed(cfg["id"], [cfg["doc"](d) for d in DOCS])
    results = []
    for query, correct_key in QUERIES:
        q_vec = embed(cfg["id"], [cfg["query"](query)])[0]
        sims = doc_vecs @ q_vec / (np.linalg.norm(doc_vecs, axis=1) * np.linalg.norm(q_vec))
        order = sims.argsort()[::-1]
        correct_idx = DOC_KEYS.index(correct_key)
        rank = int(np.where(order == correct_idx)[0][0]) + 1
        # margin：正确文档与"最强的其他文档"的分差（rank=1 时和第 2 名比，否则和第 1 名比）
        top_other = order[1] if rank == 1 else order[0]
        margin = float(sims[correct_idx] - sims[top_other])
        results.append((query, correct_key, rank, float(sims[correct_idx]), margin))
    return results


evaluations = {name: evaluate(cfg) for name, cfg in MODELS.items()}

print(f"{'问题':<24}{'正确文档':<8} | " + " | ".join(f"{name:<24}" for name in MODELS))
print("-" * 90)
for i, (query, correct_key) in enumerate(QUERIES):
    parts = []
    for name in MODELS:
        _, _, rank, score, _ = evaluations[name][i]
        parts.append(f"rank={rank} {'OK ' if rank == 1 else 'x  '}{score:.4f}")
    print(f"{query:<24}{correct_key:<8} | " + " | ".join(f"{p:<24}" for p in parts))

print("-" * 90)
for name in MODELS:
    hits = sum(1 for r in evaluations[name] if r[2] == 1)
    margin = sum(r[4] for r in evaluations[name]) / len(QUERIES)
    print(f"{name:<16} Top1 命中 {hits}/{len(QUERIES)}  平均 margin {margin:+.4f}")
