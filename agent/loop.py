"""通用工具调用循环。

约定：
- 工具的任何失败都转成结构化错误字典，作为 tool 消息回传给模型，不中断循环；
- trace 保存每一步的完整内容（工具参数、完整返回值），日志输出时再截断。
"""

import json
import time

from agent import config

SYSTEM_PROMPT = (
    "你是一个助手。需要外部信息时调用工具。"
    "如果工具返回错误，如实告诉用户失败原因，不要编造结果。"
)


def _execute(call, registry):
    """执行一次工具调用。返回 (回传给模型的字符串, trace 记录)。"""
    name = call.function.name
    tool = registry.get(name)
    if tool is None:
        result = {"error": "unknown_tool", "message": f"不存在的工具：{name}"}
        return _dump(result), {"tool": name, "args": None, "result": result}

    try:
        args = json.loads(call.function.arguments or "{}")
        if not isinstance(args, dict):
            raise ValueError("arguments 不是 JSON 对象")
    except ValueError:
        result = {"error": "invalid_arguments", "message": "工具参数不是合法的 JSON 对象"}
        return _dump(result), {"tool": name, "args": call.function.arguments, "result": result}

    try:
        result = tool.run(**args)
    except TypeError:
        # 参数名或个数与 schema 不符。注意：这里也会吞掉工具内部的 TypeError，
        # 因此工具内部应自行处理可预期的错误，见 weather.py 的做法
        result = {"error": "invalid_arguments", "message": f"工具 {name} 的参数不符合要求"}
    except Exception:
        result = {"error": "internal", "message": f"工具 {name} 执行出错"}
    return _dump(result), {"tool": name, "args": args, "result": result}


def _dump(obj):
    return json.dumps(obj, ensure_ascii=False)


def _assistant_message(msg):
    """把模型返回的 tool_calls 转回下一轮请求需要的字典格式。"""
    return {
        "role": "assistant",
        "content": msg.content or "",
        "tool_calls": [
            {
                "id": c.id,
                "type": "function",
                "function": {"name": c.function.name, "arguments": c.function.arguments},
            }
            for c in msg.tool_calls
        ],
    }


def _finish(status, answer, trace):
    return {"status": status, "answer": answer, "trace": trace}


def run_agent(
    question,
    registry,
    chat,
    clock=time.monotonic,
    max_steps=config.MAX_STEPS,
    overall_timeout=config.OVERALL_TIMEOUT,
):
    """运行 Agent。返回 {"status", "answer", "trace"}。

    status：
    - done：模型给出最终回答
    - max_steps：步数用完，已撤掉工具做最后一次回答
    - timeout：整体超时，未再发起模型调用
    """
    start = clock()
    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": question},
    ]
    trace = []
    tools = registry.schemas()

    for step in range(1, max_steps + 1):
        if clock() - start > overall_timeout:
            return _finish("timeout", None, trace)

        msg = chat(messages, tools)
        if not msg.tool_calls:
            return _finish("done", msg.content, trace)

        messages.append(_assistant_message(msg))
        step_record = {"step": step, "calls": []}
        for call in msg.tool_calls:
            content, record = _execute(call, registry)
            messages.append({"role": "tool", "tool_call_id": call.id, "content": content})
            step_record["calls"].append(record)
        trace.append(step_record)

    if clock() - start > overall_timeout:
        return _finish("timeout", None, trace)
    # 步数用完：撤掉工具，强制模型基于已有结果作答
    msg = chat(messages, None)
    return _finish("max_steps", msg.content, trace)