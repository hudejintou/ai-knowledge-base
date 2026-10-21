import numpy as np

from qa.models import Document


def retrieve_from_db(query_vec, top_k=3):
    """从数据库读取已计算好的文档向量，用余弦相似度返回 top_k 条。

    query_vec: 问题的 embedding（一维列表或数组），由调用方提供。
    返回: [(文档内容, 相似度分数), ...]，按分数从高到低。
    """
    # 只取已经有向量的文档。没有向量的文档不参与检索，避免报错
    docs = list(Document.objects.filter(embedding__isnull=False))
    if not docs:
        return []

    # 关键：把数据库里的 JSON 列表转成矩阵，之后用矩阵运算一次算完所有相似度
    doc_vecs = np.array([d.embedding for d in docs], dtype=np.float32)
    q = np.asarray(query_vec, dtype=np.float32)

    # 余弦相似度 = 点积 / (两个向量的模长乘积)
    denominator = np.linalg.norm(doc_vecs, axis=1) * np.linalg.norm(q)
    similarities = doc_vecs @ q / denominator

    # argsort 从小到大排序，[::-1] 反转成从大到小，再取前 top_k 个
    indexes = similarities.argsort()[::-1][:top_k]
    return [(docs[i].content, float(similarities[i])) for i in indexes]