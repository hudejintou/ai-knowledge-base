# eval_retrieval.py
import numpy as np
from rag.corpus import DOCS, EVAL_SET  # 语料和评估题
from rag.rag_v1 import embed, DOC_VECS  # 向量函数和文档向量
from rag.rag_v1 import SIM_THRESHOLD  # 相似度阈值


def search_indexes(query, top_k=3):
    query_vec = embed([query])[0]
    sims = DOC_VECS @ query_vec / (np.linalg.norm(DOC_VECS, axis=1) * np.linalg.norm(query_vec))
    order = sims.argsort()[::-1][:top_k]
    return [(int(i), float(sims[i])) for i in order]

top1 = top3 = answerable = 0
refuse_correct = refuse_total = 0
failures = []

for case in EVAL_SET:
    hits = search_indexes(case["question"])
    ids = [i for i, _ in hits]
    relevant = set(case["relevant"])

    if relevant:
        answerable += 1
        if ids[0] in relevant:
            top1 += 1
        else:
            failures.append((case["question"], "top1 未命中", hits))
        if relevant & set(ids):
            top3 += 1
    else:
        refuse_total += 1
        passed_threshold = [i for i, s in hits if s >= SIM_THRESHOLD]
        if not passed_threshold:
            refuse_correct += 1
        else:
            failures.append((case["question"], "应拒答但分数过阈值", hits))

print(f"可回答问题数: {answerable}")
print(f"top-1 命中率: {top1 / answerable:.2%}")
print(f"top-3 命中率: {top3 / answerable:.2%}")
print(f"无关问题拒答正确率: {refuse_correct}/{refuse_total}")
print("\n失败样例:")
for q, reason, hits in failures:
    print(f"- {q} | {reason}")
    for i, s in hits:
        print(f"    {s:.3f} {DOCS[i][:30]}...")

# ---- 阈值分析 ----
answerable_top1 = []   # 可回答问题：top-1 分数
refuse_top1 = []       # 无关问题：top-1 分数

for case in EVAL_SET:
    hits = search_indexes(case["question"])
    top1_score = hits[0][1]
    if case["relevant"]:
        answerable_top1.append((top1_score, case["question"]))
    else:
        refuse_top1.append((top1_score, case["question"]))

answerable_top1.sort()   # 从低到高
refuse_top1.sort(reverse=True)  # 从高到低

print("\n===== 阈值分析 =====")
print(f"可回答问题，top-1 最低分 5 个：")
for s, q in answerable_top1[:5]:
    print(f"  {s:.3f}  {q}")

print(f"\n无关问题，top-1 最高分 4 个：")
for s, q in refuse_top1:
    print(f"  {s:.3f}  {q}")

print(f"\n可回答最低分 = {answerable_top1[0][0]:.3f}")
print(f"无关最高分   = {refuse_top1[0][0]:.3f}")
gap = answerable_top1[0][0] - refuse_top1[0][0]
print(f"分差 = {gap:.3f}（为正表示两组可以用阈值分开）")