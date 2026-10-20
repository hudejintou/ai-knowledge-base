# eval_all.py
import json
from datetime import datetime
from rag.corpus import EVAL_SET, HOLDOUT_SET  # 语料和评估题，现在位于 rag 包中
from rag.corpus import EVAL_SET, HOLDOUT_SET  # 语料和评估题，现在位于 rag 包中
from rag.rag_v1 import answer_with_judgement, CHAT_MODEL  # 判断函数和聊天模型名

RUNS = 1  # 之后改成 3，统计一致率

def run_suite(name, cases):
    records = []
    for case in cases:
        should_refuse = not case["relevant"]
        outcomes = []
        texts = []
        for _ in range(RUNS):
            refused, text = answer_with_judgement(case["question"])
            outcomes.append(refused)
            texts.append(text)
        correct = [r == should_refuse for r in outcomes]
        records.append({
            "suite": name,
            "question": case["question"],
            "should_refuse": should_refuse,
            "refused_runs": outcomes,
            "correct_runs": sum(correct),
            "all_answers": texts,
        })
        print(f"[{name}] {case['question']} -> 正确 {sum(correct)}/{RUNS}", flush=True)
    return records
if __name__ == "__main__":
    # 全量评估：EVAL_SET 与 HOLDOUT_SET 合并运行
    results = run_suite("eval", EVAL_SET) + run_suite("holdout", HOLDOUT_SET)
    total = len(results)
    # 每题的正确次数合计 / (题数 × RUNS) 即为总体正确率
    correct = sum(r["correct_runs"] for r in results) / RUNS
    summary = {
        "time": datetime.now().isoformat(timespec="seconds"),
        "model": CHAT_MODEL,
        "runs_per_question": RUNS,
        "total_questions": total,
        "accuracy": round(correct / total, 4),
        "results": results,

    }
    # 结果保存到 evals/runs/，原来的 eval_runs/ 已合并到这里
    path = f"evals/runs/run_{datetime.now():%Y%m%d_%H%M%S}.json"
    with open(path, "w", encoding="utf-8") as f:
        json.dump(summary, f, ensure_ascii=False, indent=2)
    print(f"\n总体正确率: {summary['accuracy']:.2%}")
    print(f"结果已保存: {path}")