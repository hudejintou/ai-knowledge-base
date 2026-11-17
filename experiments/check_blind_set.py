"""检查预注册题集 BLIND_SET：合法性、与旧题集的重复、扩充段覆盖情况。

运行（项目根目录）：
    python -m experiments.check_blind_set

只读脚本：不修改任何文件，不调用模型。
"""
from difflib import SequenceMatcher

from rag.blind_set import BLIND_SET
from rag.corpus import ALL_DOCS, EVAL_SET, HOLDOUT_SET, MULTI_SET

# 相似度达到该值的题目对，需要人工判断是否保留
NEAR_THRESHOLD = 0.6
OLD_SETS = {"eval": EVAL_SET, "holdout": HOLDOUT_SET, "multi": MULTI_SET}


def check_validity():
    """检查下标合法性与题目文本是否重复。"""
    problems = []
    questions = [c["question"] for c in BLIND_SET]
    for i, case in enumerate(BLIND_SET):
        rel = case["relevant"]
        if len(set(rel)) != len(rel):
            problems.append(f"#{i} relevant 有重复下标：{rel}")
        for idx in rel:
            if not isinstance(idx, int) or not (0 <= idx < len(ALL_DOCS)):
                problems.append(f"#{i} 下标不合法：{idx}")
    for q in sorted(set(questions)):
        if questions.count(q) > 1:
            problems.append(f"BLIND_SET 内部重复题目：{q}")
    return problems


def check_against_old():
    """与旧题集比对：完全相同的题目，以及相似度达到阈值的题目。"""
    exact, near = [], []
    for case in BLIND_SET:
        q = case["question"]
        for name, old_set in OLD_SETS.items():
            for old in old_set:
                oq = old["question"]
                if q == oq:
                    exact.append((q, name, oq))
                    continue
                ratio = SequenceMatcher(None, q, oq).ratio()
                if ratio >= NEAR_THRESHOLD:
                    near.append((round(ratio, 2), q, name, oq))
    return exact, sorted(near, reverse=True)


def coverage():
    """统计扩充段（下标 20–43）被题目引用的次数。"""
    counts = {i: 0 for i in range(20, len(ALL_DOCS))}
    for case in BLIND_SET:
        for idx in case["relevant"]:
            if idx in counts:
                counts[idx] += 1
    return counts


if __name__ == "__main__":
    print(f"BLIND_SET 题数：{len(BLIND_SET)}")
    print(f"拒答题数：{sum(1 for c in BLIND_SET if not c['relevant'])}")
    print()

    print("== 1. 合法性检查 ==")
    problems = check_validity()
    if problems:
        for p in problems:
            print("  问题：", p)
    else:
        print("  通过")
    print()

    print("== 2. 与旧题集完全相同的题目 ==")
    exact, near = check_against_old()
    if exact:
        for q, name, oq in exact:
            print(f"  [{name}] {q}")
    else:
        print("  无")
    print()

    print(f"== 3. 与旧题集相似度 ≥ {NEAR_THRESHOLD} 的题目（需人工判断）==")
    if near:
        for ratio, q, name, oq in near:
            print(f"  {ratio}  新：{q}")
            print(f"        旧[{name}]：{oq}")
    else:
        print("  无")
    print()

    print("== 4. 扩充段覆盖（下标 20–43）==")
    cov = coverage()
    unused = [i for i, n in cov.items() if n == 0]
    for i in sorted(cov):
        print(f"  下标 {i}：{cov[i]} 次")
    print(f"  未覆盖下标：{unused if unused else '无'}")