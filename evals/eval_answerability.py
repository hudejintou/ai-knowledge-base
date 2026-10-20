# eval_answerability.py
from rag.corpus import DOCS, EVAL_SET  # 语料和评估题
from rag.rag_v1 import answer_with_judgement  # 判断函数

refuse_correct = refuse_total = 0
answer_wrong_refuse = answerable_total = 0
calls = 0
details = []

for case in EVAL_SET:
    refused, text = answer_with_judgement(case["question"])
    calls += 1
    print(f"完成第 {calls} 题：{case['question']}", flush=True)
    should_refuse = not case["relevant"]
    if should_refuse:
        refuse_total += 1
        if refused:
            refuse_correct += 1
        else:
            details.append((case["question"], "应拒答但回答了", text))
    else:
        answerable_total += 1
        if refused:
            answer_wrong_refuse += 1
            details.append((case["question"], "可回答但被拒", text))

print(f"无关问题拒答正确率: {refuse_correct}/{refuse_total}")
print(f"可回答问题误拒率: {answer_wrong_refuse}/{answerable_total}")
print(f"智谱调用次数: {calls}")
print("\n错误样例:")
for q, reason, text in details:
    print(f"- {q} | {reason}")
    print(f"    {text[:80]}")