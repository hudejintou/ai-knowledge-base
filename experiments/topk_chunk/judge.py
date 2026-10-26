"""判定检索结果是否命中标准段落（更严格版本）。

判定规则：
- 块与标准段落的重叠字符数 / 标准段落长度 >= 0.5，记为命中（原为 0.3）。
- 同时统计 top-1 是否命中：只看排名第一的块，更能反映块大小本身的影响。
"""


def overlap_ratio(chunk_start, chunk_end, para_start, para_end):
    # 关键：用区间交集计算重叠长度，区间均为原文中的字符位置
    inter = max(0, min(chunk_end, para_end) - max(chunk_start, para_start))
    para_len = para_end - para_start
    return inter / para_len if para_len else 0.0


def is_hit(chunks, para_span, threshold=0.5):
    # 注意：chunks 按检索排名排序，列表第一个即 top-1
    ps, pe = para_span
    return any(
        overlap_ratio(c["start"], c["end"], ps, pe) >= threshold
        for c in chunks
    )


def is_top1_hit(chunks, para_span, threshold=0.5):
    # 关键：只判断排名第一的块，不看 top-3 中的其他块
    ps, pe = para_span
    first = chunks[0]
    return overlap_ratio(first["start"], first["end"], ps, pe) >= threshold