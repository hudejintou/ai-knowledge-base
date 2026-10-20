import json
import os
import ast
import operator
from openai import OpenAI

client = OpenAI(
    api_key=os.environ["ZHIPU_API_KEY"],
    base_url="https://open.bigmodel.cn/api/paas/v4/",
)
MODEL = "glm-4.5-air"  # 以你账号里实际可用的模型名为准


# ---------- 1. 真实流式输出 ----------
def stream_chat(prompt: str) -> None:
    stream = client.chat.completions.create(
        model=MODEL,
        messages=[{"role": "user", "content": prompt}],
        stream=True,
    )
    for chunk in stream:
        delta = chunk.choices[0].delta.content
        if delta:
            print(delta, end="", flush=True)
    print()


# ---------- 2. Function Calling ----------
def get_weather(location: str) -> dict:
    return {"location": location, "temp": 25, "condition": "晴"}  # 先用假数据

_OPS = {
    ast.Add: operator.add,
    ast.Sub: operator.sub,
    ast.Mult: operator.mul,
    ast.Div: operator.truediv,
}

def _eval(node):
    if isinstance(node, ast.Expression):
        return _eval(node.body)
    if isinstance(node, ast.Constant) and type(node.value) in (int, float):
        return node.value
    if isinstance(node, ast.BinOp) and type(node.op) in _OPS:
        return _OPS[type(node.op)](_eval(node.left), _eval(node.right))
    if isinstance(node, ast.UnaryOp) and isinstance(node.op, ast.USub):
        return -_eval(node.operand)
    raise ValueError(f"不允许的表达式: {type(node).__name__}")

def calculate(expression: str) -> dict:
    """安全计算数学表达式，只支持数字和 + - * / 以及括号、负号"""
    try:
        tree = ast.parse(expression, mode="eval")
        return {"expression": expression, "result": _eval(tree)}
    except Exception as e:
        return {"expression": expression, "error": str(e)}

TOOLS = [{
    "type": "function",
    "function": {
        "name": "get_weather",
        "description": "查询某个城市的当前天气",
        "parameters": {
            "type": "object",
            "properties": {"location": {"type": "string", "description": "城市名，如 北京"}},
            "required": ["location"],
        },
    },
},
{
    "type": "function",
    "function": {
        "name": "calculate",
        "description": "计算数学表达式，支持加减乘除",
        "parameters": {
            "type": "object",
            "properties": {
                "expression": {
                    "type": "string",
                    "description": "要计算的表达式，如：3 + 5 * 2，(4 + 5) / 3"
                }
            },
            "required": ["expression"],
        },
    },
}]
FUNCS = {"get_weather": get_weather, "calculate": calculate}


def chat_with_tools(question: str, max_rounds: int = 5) -> str:
    messages = [{"role": "user", "content": question}]

    for _ in range(max_rounds):
        resp = client.chat.completions.create(
            model=MODEL, messages=messages, tools=TOOLS
        )
        msg = resp.choices[0].message

        if not msg.tool_calls:      # 没有工具调用 → 这就是最终回答
            return msg.content

        messages.append(msg)
        for call in msg.tool_calls:
            args = json.loads(call.function.arguments)
            print(f"[模型决定调用] {call.function.name}({args})")
            result = FUNCS[call.function.name](**args)
            messages.append({
                "role": "tool",
                "tool_call_id": call.id,
                "content": json.dumps(result, ensure_ascii=False),
            })

    return "超过最大调用轮数，已停止"

if __name__ == "__main__":
    stream_chat("用三句话解释什么是 RAG")
    print("---")
    print(chat_with_tools("北京现在天气怎么样？"))
    print("---")
    print(chat_with_tools("你好"))  # 对比：不需要工具时模型不会调用
    print("---")
    print(chat_with_tools("3 * (4 + 5) 等于多少"))
    print("---")
    print(chat_with_tools("北京温度乘以 2 是多少"))  # 多步调用测试
    print("---")
    print(chat_with_tools("3 * (4 + 5) 等于多少"))
    print("---")

