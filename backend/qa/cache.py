"""问答缓存：相同问题直接返回已缓存的回答，避免重复调用智谱。"""

import hashlib
import json

# 缓存有效期（秒）。知识库更新后，旧缓存最多保留这么久
CACHE_TTL_SECONDS = 3600


def cache_key(question):
    # 关键：用问题的哈希作为 key，避免过长或包含特殊字符的问题文本直接成为 key。
    # 注意：这里对问题做了 strip，和视图里的预处理保持一致
    digest = hashlib.sha256(question.strip().encode("utf-8")).hexdigest()
    return f"qa:answer:{digest}"


def get_cached_answer(client, question):
    """命中返回 dict，未命中返回 None。"""
    raw = client.get(cache_key(question))
    # 关键：decode_responses=True 时 get 返回字符串，这里直接解析 JSON
    return json.loads(raw) if raw else None


def set_cached_answer(client, question, refused, answer):
    # 关键：拒答结果也要缓存，否则同一个拒答问题每次都会重新调用模型
    payload = json.dumps({"refused": refused, "answer": answer}, ensure_ascii=False)
    client.set(cache_key(question), payload, ex=CACHE_TTL_SECONDS)
