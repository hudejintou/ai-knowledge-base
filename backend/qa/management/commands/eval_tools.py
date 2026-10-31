"""评估命令：用同一批问题对比"工具版"与"基线版"的拒答正确率。

运行：python manage.py eval_tools [--runs N]

注意：必须在容器中运行（见第八步），因为本机数据库混有测试文档（ID 22、27–30 等），
会干扰检索结果；容器数据库只有语料的 20 条。
"""

import json
import sys
from datetime import datetime
from pathlib import Path

from django.core.management.base import BaseCommand

from qa.agent import ask_with_tools
from qa.service import ask_with_db

# 把项目根加入路径，才能导入 rag.corpus（与 load_corpus 的做法一致）
PROJECT_ROOT = Path(__file__).resolve().parents[4]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from rag.corpus import EVAL_SET, HOLDOUT_SET  # noqa: E402


class Command(BaseCommand):
    help = "对比工具版与基线版在评估集上的拒答正确率"

    def add_arguments(self, parser):
        parser.add_argument("--runs", type=int, default=1, help="每题重复次数，用于观察稳定性")

    def handle(self, *args, **options):
        runs = options["runs"]
        cases = [("eval", c) for c in EVAL_SET] + [("holdout", c) for c in HOLDOUT_SET]

        records = []
        tool_correct = base_correct = 0
        for suite, case in cases:
            question = case["question"]
            should_refuse = not case["relevant"]

            tool_runs, base_runs = [], []
            for _ in range(runs):
                tool_runs.append(ask_with_tools(question)["refused"])
                base_runs.append(ask_with_db(question)[0])

            tool_correct += sum(r == should_refuse for r in tool_runs)
            base_correct += sum(r == should_refuse for r in base_runs)

            records.append({
                "suite": suite,
                "question": question,
                "should_refuse": should_refuse,
                "tools_refused_runs": tool_runs,
                "baseline_refused_runs": base_runs,
            })
            self.stdout.write(
                f"[{suite}] {question} 应拒答={should_refuse} 工具={tool_runs} 基线={base_runs}"
            )

        total = len(cases) * runs
        summary = {
            "time": datetime.now().isoformat(timespec="seconds"),
            "runs_per_question": runs,
            "total_questions": len(cases),
            "tools_accuracy": round(tool_correct / total, 4),
            "baseline_accuracy": round(base_correct / total, 4),
            "results": records,
        }

        out_dir = PROJECT_ROOT / "evals" / "runs"
        out_dir.mkdir(parents=True, exist_ok=True)
        path = out_dir / f"tools_vs_baseline_{datetime.now():%Y%m%d_%H%M%S}.json"
        path.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")

        self.stdout.write("")
        self.stdout.write(f"工具版正确率：{summary['tools_accuracy']:.2%}")
        self.stdout.write(f"基线版正确率：{summary['baseline_accuracy']:.2%}")
        self.stdout.write(f"结果已保存（容器内路径）：{path}")