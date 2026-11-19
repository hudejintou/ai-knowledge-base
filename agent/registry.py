"""工具注册表：循环只通过这里调用工具，不直接 import 具体工具。"""

from dataclasses import dataclass
from typing import Callable


@dataclass(frozen=True)
class Tool:
    name: str
    schema: dict            # 给模型看的 JSON Schema（不含外层 type/function）
    run: Callable[..., dict]  # 执行函数，参数即模型给出的 arguments，返回 dict


class ToolRegistry:
    def __init__(self):
        self._tools = {}

    def register(self, tool: Tool):
        if tool.name in self._tools:
            raise ValueError(f"工具重复注册：{tool.name}")
        self._tools[tool.name] = tool

    def get(self, name):
        return self._tools.get(name)

    def schemas(self):
        """转成 OpenAI 兼容的 tools 参数格式。"""
        return [{"type": "function", "function": t.schema} for t in self._tools.values()]