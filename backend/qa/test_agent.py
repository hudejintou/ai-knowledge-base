"""工具调用循环的单元测试。

通过 patch 替换模型客户端、检索函数和向量函数，只验证循环逻辑本身。
"""

import json
from types import SimpleNamespace as NS
from unittest.mock import MagicMock, patch

from django.test import TestCase

from qa.agent import ask_with_tools
from qa.config import MAX_TOOL_ROUNDS


def _call(query, call_id="call_1"):
    """构造一个假的 tool call，结构与 SDK 返回的一致。"""
    return NS(id=call_id, function=NS(name="search_knowledge",
                                      arguments=json.dumps({"query": query}, ensure_ascii=False)))


def _msg(content=None, tool_calls=None):
    """构造一个假的模型 message。"""
    return NS(content=content, tool_calls=tool_calls)


def _resp(msg):
    """包装成 chat.completions.create 的返回结构。"""
    return NS(choices=[NS(message=msg)])


FAKE_HITS = [("缓存资料A：用 Redis 做缓存", 0.9), ("无关资料B", 0.2)]


class AskWithToolsTests(TestCase):
    def setUp(self):
        # 替换三个外部依赖：模型客户端、向量函数、检索函数
        client_patcher = patch("qa.agent.chat_client")
        self.client = client_patcher.start()
        self.addCleanup(client_patcher.stop)

        embed_patcher = patch("qa.agent.embed_query", return_value=[0.1, 0.2])
        embed_patcher.start()
        self.addCleanup(embed_patcher.stop)

        search_patcher = patch("qa.agent.retrieve_from_db", return_value=FAKE_HITS)
        search_patcher.start()
        self.addCleanup(search_patcher.stop)

    def _script(self, *messages):
        """让模型按顺序返回这些 message。"""
        self.client.chat.completions.create.side_effect = [_resp(m) for m in messages]

    def test_tool_round_then_cited_answer(self):
        # 第一次请求检索，第二次给出带引用的回答
        self._script(
            _msg(tool_calls=[_call("怎么做缓存")]),
            _msg(content="使用 Redis 做缓存 [1]。"),
        )
        result = ask_with_tools("怎么做缓存？")

        self.assertFalse(result["refused"])
        self.assertEqual(result["answer"], "使用 Redis 做缓存 [1]。")
        # 只返回被引用的资料，无关资料 B 不在结果中
        self.assertEqual(result["sources"], [{"n": 1, "text": "缓存资料A：用 Redis 做缓存"}])

    def test_no_answer_marker_means_refused(self):
        self._script(
            _msg(tool_calls=[_call("股市")]),
            _msg(content="[NO_ANSWER]"),
        )
        result = ask_with_tools("今天股市怎么样？")
        self.assertTrue(result["refused"])
        self.assertEqual(result["sources"], [])

    def test_answer_without_tool_call_is_returned(self):
        self._script(_msg(content="直接回答，没有引用"))
        result = ask_with_tools("问题")
        self.assertFalse(result["refused"])
        self.assertEqual(result["sources"], [])  # 没有引用编号，不返回资料

    def test_round_limit_forces_final_answer_without_tools(self):
        # 模型每次都请求工具，直到轮数用完；最后一次调用不应携带 tools 参数
        always_tool = _msg(tool_calls=[_call("缓存")])
        final = _msg(content="[NO_ANSWER]")
        self._script(*([always_tool] * MAX_TOOL_ROUNDS), final)

        result = ask_with_tools("问题")

        self.assertEqual(self.client.chat.completions.create.call_count, MAX_TOOL_ROUNDS + 1)
        last_kwargs = self.client.chat.completions.create.call_args.kwargs
        self.assertNotIn("tools", last_kwargs)
        self.assertTrue(result["refused"])

    def test_extra_calls_beyond_limit_get_a_reply(self):
        # 一轮里请求 3 次检索，上限是 2 次：第 3 次不执行，但必须收到回复
        three_calls = _msg(tool_calls=[_call("a", "c1"), _call("b", "c2"), _call("c", "c3")])
        self._script(three_calls, _msg(content="回答 [1]"))

        ask_with_tools("问题")

        second_request = self.client.chat.completions.create.call_args_list[1].kwargs["messages"]
        tool_replies = [m for m in second_request if isinstance(m, dict) and m.get("role") == "tool"]
        self.assertEqual(len(tool_replies), 3)
        self.assertIn("上限", tool_replies[2]["content"])