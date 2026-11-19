"""计算工具：安全计算四则运算表达式，不使用 eval。"""

import ast
import operator

CALC_SCHEMA = {
    "name": "calculate",
    "description": "计算数学表达式，只支持数字、加减乘除、括号和负号，如 3 + 5 * 2。",
    "parameters": {
        "type": "object",
        "properties": {
            "expression": {"type": "string", "description": "要计算的表达式，如 (4 + 5) / 3"},
        },
        "required": ["expression"],
    },
}

MAX_LEN = 200

_OPS = {
    ast.Add: operator.add,
    ast.Sub: operator.sub,
    ast.Mult: operator.mul,
    ast.Div: operator.truediv,
}


class _Invalid(Exception):
    pass


def _eval(node):
    if isinstance(node, ast.Expression):
        return _eval(node.body)
    if isinstance(node, ast.Constant) and type(node.value) in (int, float):
        return node.value
    if isinstance(node, ast.BinOp) and type(node.op) in _OPS:
        return _OPS[type(node.op)](_eval(node.left), _eval(node.right))
    if isinstance(node, ast.UnaryOp) and isinstance(node.op, ast.USub):
        return -_eval(node.operand)
    raise _Invalid("不允许的表达式成分")


def calculate(expression):
    if not isinstance(expression, str) or not expression.strip():
        return {"error": "invalid_expression", "message": "表达式不能为空"}
    if len(expression) > MAX_LEN:
        return {"error": "invalid_expression", "message": f"表达式不能超过 {MAX_LEN} 个字符"}
    try:
        tree = ast.parse(expression.strip(), mode="eval")
        value = _eval(tree)
    except (SyntaxError, _Invalid, ValueError):
        return {"error": "invalid_expression", "message": "表达式不合法"}
    except ZeroDivisionError:
        return {"error": "division_by_zero", "message": "除数不能为零"}
    return {"expression": expression.strip(), "result": value}
