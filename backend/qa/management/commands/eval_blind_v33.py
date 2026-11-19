"""实验 33：blind 题集评估，仅增加单次调用的错误隔离。

与 eval_tools.py（实验 32，哈希 a4304539…）的唯一差异：
- 每次模型或检索调用包在 _attempt() 中，异常记为 error，不中止整个运行；
- error 不计入正确率与覆盖率的分母，单独报告数量与异常类型。
题集、模型、超时（service.py 的 20 秒）、TOP_K、判断逻辑均与实验 32 相同。

用法（容器内）：
    python manage.py eval_blind_v33 --runs 3
"""

import json
import sys
from datetime import datetime
from pathlib import Path

from django.core.management.base import BaseCommand

from qa.agent import ask_with_tools
from qa.config import TOP_K
from qa.retrieval import retrieve_from_db
from qa.service import ask_with_db, embed_query

PROJECT_ROOT = Path(__file__).resolve().parents[4]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from rag.blind_set import BLIND_SET  # noqa: E402
from rag.corpus import ALL_DOCS  # noqa: E402


def _attempt(fn):
    """执行一次调用。成功返回 (结果, None)；失败返回 (None, 异常类型名)。"""
    try:
        return fn(), None
    except Exception as exc:  # 有意宽泛：失败只记录，不中止运行
        return None, type(exc).__name__


def _coverage(required, retrieved_texts):
    """所需资料中被检索到的比例。required 为空时返回 None。"""
    if not required:
        return None
    hit = sum(1 for i in required if ALL_DOCS[i] in retrieved_texts)
    return hit / len(required)


def _base_retrieved(question):
    return [t for t, _ in retrieve_from_db(embed_query(question), top_k=TOP_K)]


class Command(BaseCommand):
    help = "实验 33：blind 套件，单次调用错误隔离"

    def add_arguments(self, parser):
        parser.add_argument("--runs", type=int, default=3)

    def handle(self, *args, **options):
        runs = options["runs"]
        records = []
        stats = {
            mode: {"valid": 0, "errors": {}, "ref_correct": 0, "ref_total": 0, "cov": []}
            for mode in ("tool", "base")
        }

        for idx, case in enumerate(BLIND_SET):
            question = case["question"]
            required = case["relevant"]
            should_refuse = not required

            for run_no in range(1, runs + 1):
                tool, tool_err = _attempt(lambda: ask_with_tools(question))
                base, base_err = _attempt(lambda: ask_with_db(question))
                base_hits, hits_err = _attempt(lambda: _base_retrieved(question))
                base_err = base_err or hits_err

                tool_refused = tool["refused"] if tool else None
                base_refused = base[0] if base else None
                tool_cov = _coverage(required, tool["retrieved"]) if tool else None
                base_cov = _coverage(required, base_hits) if base_hits is not None else None

                records.append({
                    "idx": idx,
                    "question": question,
                    "run": run_no,
                    "required": required,
                    "should_refuse": should_refuse,
                    "tool_refused": tool_refused,
                    "base_refused": base_refused,
                    "tool_coverage": tool_cov,
                    "base_coverage": base_cov,
                    "tool_error": tool_err,
                    "base_error": base_err,
                })
                self.stdout.write(
                    f"[blind#{idx}] run{run_no} {question} 应拒答={should_refuse} "
                    f"工具拒答={tool_refused} 基线拒答={base_refused} "
                    f"工具覆盖={tool_cov} 基线覆盖={base_cov} "
                    f"工具错误={tool_err} 基线错误={base_err}"
                )

                for mode, refused, err, cov in (
                    ("tool", tool_refused, tool_err, tool_cov),
                    ("base", base_refused, base_err, base_cov),
                ):
                    s = stats[mode]
                    if err:
                        s["errors"][err] = s["errors"].get(err, 0) + 1
                        continue
                    s["valid"] += 1
                    if should_refuse:
                        s["ref_total"] += 1
                        if refused == should_refuse:
                            s["ref_correct"] += 1
                    if cov is not None:
                        s["cov"].append(cov)

        summary = {}
        for mode, s in stats.items():
            summary[mode] = {
                "valid_calls": s["valid"],
                "error_calls": sum(s["errors"].values()),
                "error_types": s["errors"],
                "refusal_correct": s["ref_correct"],
                "refusal_total": s["ref_total"],
                "mean_coverage": round(sum(s["cov"]) / len(s["cov"]), 4) if s["cov"] else None,
            }

        out = {
            "experiment": 33,
            "time": datetime.now().isoformat(timespec="seconds"),
            "runs_per_question": runs,
            "top_k": TOP_K,
            "questions": len(BLIND_SET),
            "summary": summary,
            "results": records,
        }
        out_dir = PROJECT_ROOT / "evals" / "runs"
        out_dir.mkdir(parents=True, exist_ok=True)
        path = out_dir / f"blind_v33_{datetime.now():%Y%m%d_%H%M%S}.json"
        path.write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")

        self.stdout.write("")
        for mode, s in summary.items():
            self.stdout.write(
                f"[{mode}] 有效 {s['valid_calls']} | 错误 {s['error_calls']} {s['error_types']} | "
                f"拒答正确 {s['refusal_correct']}/{s['refusal_total']} | 平均覆盖 {s['mean_coverage']}"
            )
        self.stdout.write(f"结果已保存（容器内）：{path}")