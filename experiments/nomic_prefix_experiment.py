"""Nomic Embedding 前缀对比实验：search_document: / search_query: 前缀 vs 无前缀。

验证 2026-10 路线待办：对比 Nomic 官方推荐前缀对检索排序的影响。
只依赖 LM Studio 本地服务（http://127.0.0.1:1234/v1），不需要云端 API Key。

指标：
- Rank：正确文档的排名（1 为最好）
- Margin：正确文档分数与最高分文档的差（>0 表示正确文档排第一）
"""

import numpy as np
from openai import OpenAI

client = OpenAI(api_key="lm-studio", base_url="http://127.0.0.1:1234/v1")
EMB_MODEL = "text-embedding-nomic-embed-text-v1.5@q8_0"

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


def embed(texts):
    resp = client.embeddings.create(model=EMB_MODEL, input=texts)
    return np.array([d.embedding for d in resp.data], dtype=np.float32)


def cosine_matrix(a, b):
    return a @ b / (np.linalg.norm(a, axis=1)[:, None] * np.linalg.norm(b)[None, :])


def evaluate(doc_texts, query_texts):
    """返回每个查询的正确文档排名和 top1/正确文档分数。"""
    doc_vecs = embed(doc_texts)
    results = []
    for (query, correct_key) in QUERIES:
        q_vec = embed([query_texts(query)])[0]
        sims = doc_vecs @ q_vec / (np.linalg.norm(doc_vecs, axis=1) * np.linalg.norm(q_vec))
        order = sims.argsort()[::-1]
        correct_idx = DOC_KEYS.index(correct_key)
        rank = int(np.where(order == correct_idx)[0][0]) + 1
        margin = float(sims[correct_idx] - sims[order[0]])
        results.append((query, correct_key, rank, float(sims[correct_idx]), margin))
    return results


PREFIXED_DOCS = ["search_document: " + d for d in DOCS]
prefix_query = lambda q: "search_query: " + q

no_prefix = evaluate(DOCS, lambda q: q)
with_prefix = evaluate(PREFIXED_DOCS, prefix_query)

print(f"{'问题':<22}{'正确文档':<8} | {'无前缀 rank':<10}{'分数':<7} | {'有前缀 rank':<11}{'分数':<7}")
print("-" * 78)
for (q, k, r1, s1, _), (_, _, r2, s2, _) in zip(no_prefix, with_prefix):
    mark1 = "OK" if r1 == 1 else "x"
    mark2 = "OK" if r2 == 1 else "x"
    print(f"{q:<22}{k:<8} | rank={r1} {mark1:<3}{s1:.4f} | rank={r2} {mark2:<3}{s2:.4f}")

hit1 = sum(1 for r in no_prefix if r[2] == 1)
hit2 = sum(1 for r in with_prefix if r[2] == 1)
m1 = sum(r[4] for r in no_prefix) / len(no_prefix)
m2 = sum(r[4] for r in with_prefix) / len(with_prefix)
print("-" * 78)
print(f"Top1 命中：无前缀 {hit1}/{len(QUERIES)}  vs  有前缀 {hit2}/{len(QUERIES)}")
print(f"平均 margin（正确文档-最高分，>0 为排第一）：无前缀 {m1:+.4f}  vs  有前缀 {m2:+.4f}")
