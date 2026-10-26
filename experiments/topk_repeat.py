"""阶段 C：检索数量稳定性验证。固定一个 top_k，每题跑 RUNS 次，统计一致率。

运行（项目根目录，一次只跑一个取值）：
    TOP_K=1 python -m experiments.topk_repeat
    TOP_K=2 python -m experiments.topk_repeat
    TOP_K=3 python -m experiments.topk_repeat
"""
import json
import os
from datetime import datetime

from rag.corpus import EVAL_SET, HOLDOUT_SET
from rag.rag_v1 import answer_with_judgement, CHAT_MODEL

# 通过环境变量指定 top_k 与重复次数，不修改代码就能切换对照
TOP_K = int(os.getenv("TOP_K", "3"))
RUNS = int(os.getenv("RUNS", "3"))  # 关键：每题重复次数，用来统计稳定性


def run(cases, suite):
    records = []
    for case in cases:
        should_refuse = not case["relevant"]  # 无关题（relevant 为空）应当拒答
        outcomes = []
        for _ in range(RUNS):
            # 关键：每题独立调用 RUNS 次，LLM 输出有随机性，单次结果不可靠
            refused, _text = answer_with_judgement(case["question"], top_k=TOP_K)
            outcomes.append(refused)
        correct_runs = sum(r == should_refuse for r in outcomes)
        records.append({
            "suite": suite,
            "question": case["question"],
            "should_refuse": should_refuse,
            "refused_runs": outcomes,
            "correct_runs": correct_runs,
        })
        print(f"[{suite}] {case['question']} -> 正确 {correct_runs}/{RUNS}", flush=True)
    return records


if __name__ == "__main__":
    results = run(EVAL_SET, "eval") + run(HOLDOUT_SET, "holdout")
    total_runs = len(results) * RUNS
    # 关键：正确率的分母是 题数 × RUNS，而不是题数
    correct = sum(r["correct_runs"] for r in results)
    summary = {
        "time": datetime.now().isoformat(timespec="seconds"),
        "model": CHAT_MODEL,
        "top_k": TOP_K,
        "runs_per_question": RUNS,
        "total_questions": len(results),
        "accuracy": round(correct / total_runs, 4),
        "results": results,
    }
    path = f"evals/runs/topk_repeat_k{TOP_K}_{datetime.now():%Y%m%d_%H%M%S}.json"
    with open(path, "w", encoding="utf-8") as f:
        json.dump(summary, f, ensure_ascii=False, indent=2)
    print(f"\n总体正确率: {summary['accuracy']:.2%}")
    print(f"结果已保存: {path}")