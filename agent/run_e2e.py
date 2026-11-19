"""三工具端到端验证：真实智谱模型，固定 4 条问题，trace 写入 agent/e2e_runs/。

运行（容器内）：
    python -m agent.run_e2e

注意：首次运行结果保留，不因不满足判断标准而覆盖重跑。
每次运行写入带时间戳的新文件。
"""

import json
from datetime import datetime
from pathlib import Path

from agent.loop import run_agent
from agent.model import chat
from agent.registry import Tool, ToolRegistry
from agent.tools.calculator import CALC_SCHEMA, calculate
from agent.tools.file_reader import READ_SCHEMA, read_file
from agent.tools.weather import WEATHER_SCHEMA, get_weather

OUT_DIR = Path(__file__).resolve().parent / "e2e_runs"

QUESTIONS = [
    "北京现在多少度？",
    "帮我算一下 (12 + 8) * 3 等于多少？",
    "读一下 notes.txt 里写了什么？",
    "火星城现在天气怎么样？",
]


def build_registry():
    reg = ToolRegistry()
    reg.register(Tool("get_weather", WEATHER_SCHEMA, get_weather))
    reg.register(Tool("calculate", CALC_SCHEMA, calculate))
    reg.register(Tool("read_file", READ_SCHEMA, read_file))
    return reg


def main():
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    registry = build_registry()
    summary = []

    for i, q in enumerate(QUESTIONS, 1):
        result = run_agent(q, registry, chat)
        record = {"index": i, "question": q, **result}
        path = OUT_DIR / f"e2e_{stamp}_q{i}.json"
        path.write_text(json.dumps(record, ensure_ascii=False, indent=2), encoding="utf-8")
        summary.append((i, result["status"], [c["tool"] for s in result["trace"] for c in s["calls"]]))
        print(f"[{i}] status={result['status']} 工具={summary[-1][2]}")
        print(f"    回答：{result['answer']}")

    print(f"\n结果写入：{OUT_DIR}（时间戳 {stamp}）")


if __name__ == "__main__":
    main()