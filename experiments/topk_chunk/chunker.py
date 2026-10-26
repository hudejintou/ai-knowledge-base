"""固定字符数切块，相邻块保留重叠。

关键点：
- 切块按字符而不是按词，中文没有空格，按字符最直接。
- 相邻块之间重叠 overlap 个字符，避免语义在边界处被切断。
"""


def split_chunks(text, chunk_size, overlap=50):
    # 关键：步长 = 块大小 - 重叠，保证相邻块有 overlap 个字符重复
    step = chunk_size - overlap
    chunks = []
    start = 0
    while start < len(text):
        chunks.append({
            "text": text[start:start + chunk_size],  # 当前块的内容
            "start": start,                          # 在原文中的起始位置
            "end": min(start + chunk_size, len(text)),
        })
        if start + chunk_size >= len(text):
            break  # 已经覆盖到文末，结束
        start += step
    return chunks