import numpy as np

from qa.config import TOP_K
from qa.models import Document


def search_documents(query_vec, top_k=TOP_K):
    """从数据库检索最相似的 top_k 个块，返回带 id 的结构化结果。

    query_vec: 问题的 embedding（一维列表或数组）。
    返回: [{"doc_id": 块的 id, "content": 正文, "score": 余弦相似度}, ...]，
          按分数从高到低排列。

    引用追溯依赖 doc_id：正文可能重复，id 才是块的唯一身份。
    """
    # 只取已经有向量的文档
    docs = list(Document.objects.filter(embedding__isnull=False))
    if not docs:
        return []

    # 将数据库里的 JSON 列表转成矩阵
    doc_vecs = np.array([d.embedding for d in docs], dtype=np.float32)
    q = np.asarray(query_vec, dtype=np.float32)

    # 计算余弦相似度
    denominator = np.linalg.norm(doc_vecs, axis=1) * np.linalg.norm(q)
    similarities = doc_vecs @ q / denominator

    # 按相似度从高到低，取前 top_k 个
    indexes = similarities.argsort()[::-1][:top_k]
    return [
        {
            "doc_id": docs[i].id,
            "content": docs[i].content,
            "score": float(similarities[i]),
        }
        for i in indexes
    ]


def retrieve_from_db(query_vec, top_k=TOP_K):
    """旧接口：返回 [(文档内容, 相似度分数), ...]。

    保留它是为了让基线流程、评估脚本和检索健康检查不必同时改动。
    需要 doc_id 的地方请直接用 search_documents。
    """
    return [
        (hit["content"], hit["score"])
        for hit in search_documents(query_vec, top_k)
    ]
