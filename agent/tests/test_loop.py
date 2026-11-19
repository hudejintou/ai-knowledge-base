from types import SimpleNamespace
import json
from unittest import TestCase

from agent.loop import run_agent
from agent.registry import Tool, ToolRegistry


def msg(content=None, calls=None):
    return SimpleNamespace(content=content, tool_calls=calls)


def call(name, args=None, cid="c1", raw=None):
    arguments = raw if raw is not None else json.dumps(args or {}, ensure_ascii=False)
    return SimpleNamespace(id=cid, function=SimpleNamespace(name=name, arguments=arguments))


class ScriptedChat:
    """按顺序返回预设的 message，并记录每次收到的 messages 与 tools。"""

    def __init__(self, *msgs):
        self.msgs = list(msgs)
        self.seen = []

    def __call__(self, messages, tools=None):
        self.seen.append((list(messages), tools))
        return self.msgs.pop(0)


def make_registry(run=None):
    reg = ToolRegistry()
    reg.register(Tool(
        name="echo",
        schema={"name": "echo", "description": "原样返回", "parameters": {
            "type": "object", "properties": {"text": {"type": "string"}}, "required": ["text"]}},
        run=run or (lambda text: {"text": text}),
    ))
    return reg


class RegistryTests(TestCase):
    def test_duplicate_registration_rejected(self):
        reg = make_registry()
        with self.assertRaises(ValueError):
            reg.register(Tool("echo", {}, lambda: {}))

    def test_schemas_wrapped_as_function(self):
        schemas = make_registry().schemas()
        self.assertEqual(schemas[0]["type"], "function")
        self.assertEqual(schemas[0]["function"]["name"], "echo")


class RunAgentTests(TestCase):
    def test_direct_answer_without_tools(self):
        chat = ScriptedChat(msg(content="你好"))
        result = run_agent("你好", make_registry(), chat)
        self.assertEqual(result["status"], "done")
        self.assertEqual(result["answer"], "你好")
        self.assertEqual(result["trace"], [])

    def test_tool_call_then_answer_records_full_content(self):
        chat = ScriptedChat(
            msg(calls=[call("echo", {"text": "hi"})]),
            msg(content="结果是 hi"),
        )
        result = run_agent("问", make_registry(), chat)
        self.assertEqual(result["status"], "done")
        step = result["trace"][0]
        self.assertEqual(step["step"], 1)
        self.assertEqual(step["calls"][0]["args"], {"text": "hi"})
        self.assertEqual(step["calls"][0]["result"], {"text": "hi"})  # 完整内容，不是摘要

    def test_tool_error_is_passed_back_to_model(self):
        reg = make_registry(run=lambda text: {"error": "city_not_found", "message": "未找到"})
        chat = ScriptedChat(msg(calls=[call("echo", {"text": "x"})]), msg(content="查不到该城市"))
        result = run_agent("问", reg, chat)
        self.assertEqual(result["status"], "done")
        tool_msgs = [m for m in chat.seen[1][0] if m.get("role") == "tool"]
        self.assertIn("city_not_found", tool_msgs[0]["content"])

    def test_unknown_tool_does_not_stop_loop(self):
        chat = ScriptedChat(msg(calls=[call("nope")]), msg(content="无法完成"))
        result = run_agent("问", make_registry(), chat)
        self.assertEqual(result["status"], "done")
        self.assertEqual(result["trace"][0]["calls"][0]["result"]["error"], "unknown_tool")

    def test_invalid_json_arguments(self):
        chat = ScriptedChat(msg(calls=[call("echo", raw="{坏json")]), msg(content="参数有误"))
        result = run_agent("问", make_registry(), chat)
        self.assertEqual(result["trace"][0]["calls"][0]["result"]["error"], "invalid_arguments")

    def test_wrong_argument_names_are_invalid(self):
        chat = ScriptedChat(msg(calls=[call("echo", {"wrong": 1})]), msg(content="参数有误"))
        result = run_agent("问", make_registry(), chat)
        self.assertEqual(result["trace"][0]["calls"][0]["result"]["error"], "invalid_arguments")

    def test_tool_exception_becomes_internal_error(self):
        def boom(text):
            raise RuntimeError("secret detail")
        chat = ScriptedChat(msg(calls=[call("echo", {"text": "x"})]), msg(content="出错了"))
        result = run_agent("问", make_registry(run=boom), chat)
        self.assertEqual(result["status"], "done")
        err = result["trace"][0]["calls"][0]["result"]
        self.assertEqual(err["error"], "internal")
        self.assertNotIn("secret detail", json.dumps(err))  # 内部细节不泄露给模型

    def test_max_steps_then_final_answer_without_tools(self):
        always_call = msg(calls=[call("echo", {"text": "x"})])
        chat = ScriptedChat(*([always_call] * 5), msg(content="已尽力，结果如下"))
        result = run_agent("问", make_registry(), chat, clock=lambda: 0.0, max_steps=5)
        self.assertEqual(result["status"], "max_steps")
        self.assertEqual(len(result["trace"]), 5)
        self.assertIsNone(chat.seen[-1][1])  # 最后一次调用没有 tools

    def test_overall_timeout_stops_before_next_model_call(self):
        times = iter([0, 0, 100, 100, 100])
        chat = ScriptedChat(msg(calls=[call("echo", {"text": "x"})]), msg(content="不应到达"))
        result = run_agent("问", make_registry(), chat,
                           clock=lambda: next(times), overall_timeout=60)
        self.assertEqual(result["status"], "timeout")
        self.assertEqual(len(chat.seen), 1)  # 只调用过一次模型