"""阶段 C：检索参数实验（基线）。固定 top_k=3，跑一次全量评估，只为确认当前设置的正确率。

运行（项目根目录）：
    python -m experiments.topk_baseline

注意：会调用智谱约 46 次，耗时较长。
"""
import json
from datetime import datetime

from rag.corpus import EVAL_SET, HOLDOUT_SET
from rag.rag_v1 import answer_with_judgement, CHAT_MODEL

import os

# 通过环境变量指定 top_k，默认 3，便于做对照实验而不改代码
TOP_K = int(os.getenv("TOP_K", "3"))

def run(cases):
    records = []
    for case in cases:
        should_refuse = not case["relevant"]
        # 关键：top_k 通过参数传入，不修改 rag_v1.py 的任何代码
        refused, text = answer_with_judgement(case["question"], top_k=TOP_K)
        records.append({
            "question": case["question"],
            "should_refuse": should_refuse,
            "refused": refused,
            "correct": refused == should_refuse,
            "answer": text,
        })
        print(f"{case['question']} -> {'正确' if records[-1]['correct'] else '错误'}", flush=True)
    return records


if __name__ == "__main__":
    results = run(EVAL_SET) + run(HOLDOUT_SET)
    accuracy = sum(r["correct"] for r in results) / len(results)
    summary = {
        "time": datetime.now().isoformat(timespec="seconds"),
        "model": CHAT_MODEL,
        "top_k": TOP_K,
        "total_questions": len(results),
        "accuracy": round(accuracy, 4),
        "results": results,
    }
    path = f"evals/runs/topk_{TOP_K}_{datetime.now():%Y%m%d_%H%M%S}.json"
    with open(path, "w", encoding="utf-8") as f:
        json.dump(summary, f, ensure_ascii=False, indent=2)
    print(f"\n总体正确率: {accuracy:.2%}")
    print(f"结果已保存: {path}")