"""真实模型调用，只在运行时读取环境变量，导入本模块不会报错。"""

import os

from openai import OpenAI

from agent import config

_client = None


def chat(messages, tools=None):
    """调用智谱，返回 message 对象（含 content 与 tool_calls）。"""
    global _client
    if _client is None:
        _client = OpenAI(
            api_key=os.environ["ZHIPU_API_KEY"],
            base_url="https://open.bigmodel.cn/api/paas/v4/",
            timeout=config.MODEL_CALL_TIMEOUT,
            max_retries=1,
        )
    kwargs = {"model": config.CHAT_MODEL, "messages": messages, "temperature": 0}
    if tools:
        kwargs["tools"] = tools
    return _client.chat.completions.create(**kwargs).choices[0].message