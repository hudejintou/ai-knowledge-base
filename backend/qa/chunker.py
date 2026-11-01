"""文档切块：把长文本按固定字符数切成多段，相邻段保留重叠。

作用：文档入库前调用。一段过长的文本整体入库时，检索粒度太粗，
无关内容会稀释关键句的相似度，因此需要切成小块分别计算向量。
注意：按字符切（中文没有空格），不会考虑句子边界，句中切断由重叠缓解。
"""

from qa.config import CHUNK_OVERLAP, CHUNK_SIZE


def split_text(text, size=CHUNK_SIZE, overlap=CHUNK_OVERLAP):
    """把文本切成若干块，返回去掉首尾空白后的非空块列表。

    - 空文本返回 []；长度不超过 size 的文本整体作为一块。
    - 步长 = size - overlap，因此相邻两块恰好有 overlap 个字符重复。
    """
    if not 0 <= overlap < size:
        raise ValueError("overlap 必须满足 0 <= overlap < size")

    text = text.strip()
    if not text:
        return []
    if len(text) <= size:
        return [text]

    step = size - overlap
    chunks = []
    start = 0
    while True:
        piece = text[start:start + size].strip()
        if piece:
            chunks.append(piece)
        # 已经覆盖到文末，结束；否则按步长前进
        if start + size >= len(text):
            break
        start += step
    return chunks