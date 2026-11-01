"""评估命令：对比工具版与基线版，指标包括拒答正确率和检索覆盖率。

用法（在容器内运行）：
    # 全量
    docker compose exec web python manage.py eval_tools --runs 1
    # 只跑 multi 套件的第 0、3、5 题（题号从 0 开始，指当前套件内的顺序）
    docker compose exec web python manage.py eval_tools --suite multi --ids 0,3,5 --runs 3
    # 多个套件
    docker compose exec web python manage.py eval_tools --suite holdout --suite multi
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

from rag.corpus import DOCS, EVAL_SET, HOLDOUT_SET, MULTI_SET  # noqa: E402

SUITES = {"eval": EVAL_SET, "holdout": HOLDOUT_SET, "multi": MULTI_SET}


def _coverage(required, retrieved_texts):
    """所需资料中被检索到的比例。required 为空时返回 None。"""
    if not required:
        return None
    hit = sum(1 for i in required if DOCS[i] in retrieved_texts)
    return hit / len(required)


class Command(BaseCommand):
    help = "对比工具版与基线版的拒答正确率、检索覆盖率，可按套件与题号筛选"

    def add_arguments(self, parser):
        parser.add_argument("--runs", type=int, default=1, help="每题重复次数")
        parser.add_argument(
            "--suite", action="append", choices=list(SUITES),
            help="只跑指定套件，可重复指定；默认全部",
        )
        parser.add_argument(
            "--ids", type=str, default=None,
            help="只跑指定题号（从 0 开始，指套件内顺序），逗号分隔，如 0,3,5",
        )

    def handle(self, *args, **options):
        runs = options["runs"]
        suites = options["suite"] or list(SUITES)
        wanted_ids = None
        if options["ids"]:
            wanted_ids = {int(x) for x in options["ids"].split(",") if x.strip()}

        cases = []
        for suite in suites:
            for idx, case in enumerate(SUITES[suite]):
                if wanted_ids is not None and idx not in wanted_ids:
                    continue
                cases.append((suite, idx, case))

        if not cases:
            self.stdout.write("没有匹配的题目，请检查 --suite 与 --ids")
            return

        records = []
        stats = {}

        for suite, idx, case in cases:
            question = case["question"]
            required = case["relevant"]
            should_refuse = not required

            for run_no in range(1, runs + 1):
                tool = ask_with_tools(question)
                base_refused, _ = ask_with_db(question)
                base_hits = [t for t, _ in retrieve_from_db(embed_query(question), top_k=TOP_K)]

                tool_cov = _coverage(required, tool["retrieved"])
                base_cov = _coverage(required, base_hits)

                s = stats.setdefault(suite, {
                    "n": 0, "tool_correct": 0, "base_correct": 0,
                    "tool_cov": [], "base_cov": [],
                })
                s["n"] += 1
                s["tool_correct"] += tool["refused"] == should_refuse
                s["base_correct"] += base_refused == should_refuse
                if tool_cov is not None:
                    s["tool_cov"].append(tool_cov)
                    s["base_cov"].append(base_cov)

                records.append({
                    "suite": suite,
                    "index": idx,
                    "question": question,
                    "run": run_no,
                    "required": required,
                    "should_refuse": should_refuse,
                    "tool_refused": tool["refused"],
                    "base_refused": base_refused,
                    "tool_coverage": tool_cov,
                    "base_coverage": base_cov,
                    "tool_queries": tool.get("queries", []),
                })
                self.stdout.write(
                    f"[{suite}#{idx}] {question} 应拒答={should_refuse} "
                    f"工具拒答={tool['refused']} 基线拒答={base_refused} "
                    f"工具覆盖={tool_cov} 基线覆盖={base_cov} 工具query={tool.get('queries', [])}"
                )

        summary = {}
        for suite, s in stats.items():
            summary[suite] = {
                "questions_x_runs": s["n"],
                "tool_refusal_accuracy": round(s["tool_correct"] / s["n"], 4),
                "baseline_refusal_accuracy": round(s["base_correct"] / s["n"], 4),
                "tool_coverage": round(sum(s["tool_cov"]) / len(s["tool_cov"]), 4) if s["tool_cov"] else None,
                "baseline_coverage": round(sum(s["base_cov"]) / len(s["base_cov"]), 4) if s["base_cov"] else None,
            }

        out = {
            "time": datetime.now().isoformat(timespec="seconds"),
            "runs_per_question": runs,
            "top_k": TOP_K,
            "suites": suites,
            "ids": sorted(wanted_ids) if wanted_ids is not None else None,
            "by_suite": summary,
            "results": records,
        }
        out_dir = PROJECT_ROOT / "evals" / "runs"
        out_dir.mkdir(parents=True, exist_ok=True)
        path = out_dir / f"tools_vs_baseline_v3_{datetime.now():%Y%m%d_%H%M%S}.json"
        path.write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")

        self.stdout.write("")
        for suite, s in summary.items():
            self.stdout.write(
                f"[{suite}] 拒答正确率 工具={s['tool_refusal_accuracy']:.2%} 基线={s['baseline_refusal_accuracy']:.2%}"
                f" | 覆盖率 工具={s['tool_coverage']} 基线={s['baseline_coverage']}"
            )
        self.stdout.write(f"结果已保存（容器内路径）：{path}")