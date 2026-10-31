"""RAG 最小链路：LM Studio 本地 Embedding -> 余弦检索 -> 本地 Qwen 引用问答。

LM Studio 需要先在 Developer 页面启动本地服务器，默认地址是：
    http://127.0.0.1:1234/v1

脚本会通过 /v1/models 自动发现：
- 包含 embedding/nomic 的模型作为 Embedding 模型；
- 其余模型作为聊天模型。

如果自动发现结果不符合预期，可以用环境变量明确指定：
    LMSTUDIO_BASE_URL
    LMSTUDIO_EMBED_MODEL
    LMSTUDIO_CHAT_MODEL

不要把真实 API Key 写进代码。仅访问本机 LM Studio 时，默认使用非敏感占位值。
"""

import os

import numpy as np
from openai import OpenAI
from rag.corpus import DOCS  # 改为包内完整路径，从项目根目录运行时 Python 才能找到 rag 包

# 模型名、拒答标记与拒答 Prompt 的单一来源：backend/qa/config.py。
# rag_v1 与 backend 的 service/retrieval 共用同一份配置，避免多副本漂移。
from backend.qa.config import ANSWER_SYSTEM_PROMPT, CHAT_MODEL, NO_ANSWER


BASE_URL = os.getenv("LMSTUDIO_BASE_URL", "http://127.0.0.1:1234/v1")
client = OpenAI(
    api_key=os.getenv("LMSTUDIO_API_KEY", "lm-studio"),
    base_url=BASE_URL,
)
chat_client = OpenAI(
    api_key=os.environ["ZHIPU_API_KEY"],
    base_url="https://open.bigmodel.cn/api/paas/v4/",
)




def list_model_ids():
    """读取 LM Studio /v1/models，返回服务当前暴露的模型标识。"""
    return [model.id for model in client.models.list().data]


def choose_embedding_model():
    model_ids = list_model_ids()
    embedding_ids = [m for m in model_ids if "embedding" in m.lower() or "nomic" in m.lower()]
    model = os.getenv("LMSTUDIO_EMBED_MODEL") or (embedding_ids[0] if embedding_ids else None)
    if not model:
        raise RuntimeError(f"LM Studio 里没找到 Embedding 模型，当前返回：{model_ids}")
    return model, model_ids

EMB_MODEL = "text-embedding-qwen3-embedding-0.6b"
AVAILABLE_MODELS = list_model_ids()

def embed(texts):
    """调用本地 Embedding 模型，返回 [文本数, 向量维度] 矩阵。"""
    response = client.embeddings.create(model=EMB_MODEL, input=texts)
    return np.array([item.embedding for item in response.data], dtype=np.float32)


# 文档向量只计算一次，后续问题复用这份缓存
DOC_VECS = embed(DOCS)
SIM_THRESHOLD = 0.37  # Qwen3-Embedding 的经验值，分数只在同一模型内比较


def retrieve(query, top_k=2):
    """把问题向量化，用余弦相似度返回文本和真实分数。"""
    query_vec = embed([query])[0]
    denominator = np.linalg.norm(DOC_VECS, axis=1) * np.linalg.norm(query_vec)
    similarities = DOC_VECS @ query_vec / denominator
    indexes = similarities.argsort()[::-1][:top_k]
    return [(DOCS[index], float(similarities[index])) for index in indexes]

# NO_ANSWER 与 ANSWER_SYSTEM_PROMPT 已改为从 backend/qa/config.py 导入（文件头部），不再本地定义

def answer_with_judgement(query, top_k=3):
    hits = retrieve(query, top_k=top_k)
    context = "\n".join(document for document, _ in hits)
    response = chat_client.chat.completions.create(
        model=CHAT_MODEL,
        messages=[
            {"role": "system", "content": ANSWER_SYSTEM_PROMPT},
            {"role": "user", "content": f"资料：\n{context}\n\n问题：{query}"},
        ],
        temperature=0,
    )
    text = response.choices[0].message.content.strip()
    refused = NO_ANSWER in text
    return refused, text

def answer(query):
    hits = retrieve(query)
    print(f"[问题] {query}")
    for document, score in hits:
        print(f"[检索] score={score:.6f} text={document}")

    # 过滤掉低于阈值的文档
    relevant = [(doc, score) for doc, score in hits if score >= SIM_THRESHOLD]
    if not relevant:
        return "资料中没有相关信息，无法回答。（检索分数低于阈值，未调用模型）"

    context = "\n".join(document for document, _ in relevant)
    response = chat_client.chat.completions.create(
        model=CHAT_MODEL,
        messages=[
            {
                "role": "system",
                "content": "只根据提供的资料回答。资料没有答案时，明确说不知道，不要补充资料外的事实。",
            },
            {
                "role": "user",
                "content": f"资料：\n{context}\n\n问题：{query}",
            },
        ],
    )
    return response.choices[0].message.content

def run_case(query):
    print("=" * 72)
    answer_text = answer(query)
    print(f"[回答] {answer_text}")


if __name__ == "__main__":
    print(f"[配置] base_url={BASE_URL}")
    print(f"[配置] available_models={AVAILABLE_MODELS}")
    print(f"[配置] embedding_model={EMB_MODEL}")
    print(f"[配置] chat_model={CHAT_MODEL}")
    run_case("怎么做缓存？")
    run_case("后台异步跑任务用什么？")
    run_case("今天股市怎么样？")
