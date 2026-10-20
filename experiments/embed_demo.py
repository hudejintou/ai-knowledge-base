import os
import numpy as np
from openai import OpenAI

client = OpenAI(
    api_key=os.environ["ZHIPU_API_KEY"],
    base_url="https://open.bigmodel.cn/api/paas/v4/",
)
EMB_MODEL = "embedding-3"  # 智谱的 Embedding 模型（glm-4.5-air 是聊天模型，不能用于向量化）

DOCS = [
    "Django 的 ORM 可以把数据库表映射成 Python 类。",
    "Redis 是基于内存的键值数据库，常用于缓存。",
    "RAG 先检索相关文档，再让大模型基于文档回答。",
    "Docker 用容器打包应用及其依赖。",
    "Celery 用于执行异步任务和定时任务。",
]

def embed(texts):
    resp = client.embeddings.create(model=EMB_MODEL, input=texts)
    return np.array([d.embedding for d in resp.data])

def search(query, doc_vecs, top_k=2):
    q = embed([query])[0]
    sims = doc_vecs @ q / (np.linalg.norm(doc_vecs, axis=1) * np.linalg.norm(q))
    for i in sims.argsort()[::-1][:top_k]:
        print(f"{sims[i]:.3f}  {DOCS[i]}")

if __name__ == "__main__":
    vecs = embed(DOCS)
    search("怎么做缓存？", vecs)
    print("---")
    search("后台异步跑任务用什么？", vecs)