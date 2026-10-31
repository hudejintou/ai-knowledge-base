"""阶段 E：工具调用版问答（Function Calling + RAG）。

与旧流程 service.ask_with_db 的区别：
- 旧流程：固定检索一次，把资料直接交给模型。
- 新流程：模型自己决定是否检索、检索什么（可改写查询、可并行调用）；
  后端执行检索并把结果回传，循环直到模型给出最终回答或达到轮数上限。

对外只暴露 ask_with_tools(question)，返回：
    {"refused": bool, "answer": str, "sources": [{"n": 编号, "text": 资料正文}]}
"""

import json
import logging
import re

from qa.config import (
    CHAT_MODEL,
    MAX_CALLS_PER_ROUND,
    MAX_TOOL_ROUNDS,
    NO_ANSWER,
    TOOL_SYSTEM_PROMPT,
    TOP_K,
)
from qa.retrieval import retrieve_from_db
from qa.service import chat_client, embed_query

logger = logging.getLogger(__name__)

# 工具定义，按 OpenAI 兼容的 tools 格式描述。
# 模型根据 description 决定何时调用，根据 parameters 决定传什么参数。
SEARCH_TOOL = {
    "type": "function",
    "function": {
        "name": "search_knowledge",
        "description": "检索企业知识库，返回与查询最相关的资料片段。回答知识类问题前应先调用。",
        "parameters": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "检索用的查询语句，可以是关键词或完整问题",
                },
            },
            "required": ["query"],
        },
    },
}


def _chat(messages, with_tools):
    """调用一次模型，返回它的 message 对象。

    with_tools=False 时不传 tools 参数，模型无法再调用工具，只能直接作答。
    temperature=0 让输出尽量稳定，便于评估对比。
    """
    kwargs = {"model": CHAT_MODEL, "messages": messages, "temperature": 0}
    if with_tools:
        kwargs["tools"] = [SEARCH_TOOL]
    return chat_client.chat.completions.create(**kwargs).choices[0].message


def _run_search(call, sources):
    """执行一次 search_knowledge 调用，返回要回传给模型的文本。

    参数：
        call: 模型返回的一个 tool call，包含 id 和 function.arguments（JSON 字符串）
        sources: 本次问答累计的资料列表，函数会原地追加新资料

    注意：用资料正文作为去重标识。语料中正文互不相同，所以可行；
    正式版应让检索直接返回文档 id。
    """
    # 模型给出的参数是 JSON 字符串，解析失败时直接告诉模型，而不是抛异常
    try:
        args = json.loads(call.function.arguments)
        query = (args.get("query") or "").strip()
    except (ValueError, AttributeError):
        return "工具参数无效，请提供 query 字段。"
    if not query:
        return "query 不能为空。"

    hits = retrieve_from_db(embed_query(query), top_k=TOP_K)
    if not hits:
        return "没有检索到相关资料。"

    lines = []
    for content, _score in hits:
        # 同一段资料只记录一次，编号按首次出现顺序分配（从 1 开始）
        if content not in sources:
            sources.append(content)
        lines.append(f"[{sources.index(content) + 1}] {content}")
    return "\n".join(lines)


def _finish(text, sources):
    """把模型的最终文本整理成返回结构。

    - 文本含 [NO_ANSWER] 或为空：判为拒答，不返回资料。
    - 否则只保留回答中实际引用的编号（如 [1]、[2]）对应的资料。
      注意：如果模型回答了但没有写任何编号，sources 会为空。
    """
    text = (text or "").strip()
    refused = NO_ANSWER in text or not text
    if refused:
        return {"refused": True, "answer": text, "sources": []}

    cited = {int(n) for n in re.findall(r"\[(\d+)\]", text)}
    used = [
        {"n": i + 1, "text": s}
        for i, s in enumerate(sources)
        if (i + 1) in cited
    ]
    return {"refused": False, "answer": text, "sources": used}


def ask_with_tools(question):
    """工具调用问答主循环。

    流程：
    1. 发送系统提示和问题；
    2. 若模型请求工具，执行检索，把结果以 tool 消息回传，回到第 1 步；
    3. 若模型不再请求工具，它的文本即为最终回答；
    4. 达到轮数上限仍未结束，撤掉工具，强制模型基于已有资料作答。
    """
    sources = []
    messages = [
        {"role": "system", "content": TOOL_SYSTEM_PROMPT},
        {"role": "user", "content": question},
    ]

    for round_no in range(1, MAX_TOOL_ROUNDS + 1):
        msg = _chat(messages, with_tools=True)

        # 模型没有再请求工具，它的文本就是最终回答
        if not msg.tool_calls:
            logger.info("问答完成：共 %d 轮工具调用", round_no - 1)
            return _finish(msg.content, sources)

        # 必须先把模型的 tool_calls 消息放回上下文，后面的 tool 结果才能与之对应
        messages.append(msg)
        logger.info("工具调用第 %d 轮：模型请求 %d 次检索", round_no, len(msg.tool_calls))

        for i, call in enumerate(msg.tool_calls):
            # 每个 tool_call 都必须有对应的 tool 消息，超限的也要回应，只是不执行
            if i >= MAX_CALLS_PER_ROUND:
                content = "本轮检索次数已达上限，未执行该调用。"
            else:
                content = _run_search(call, sources)
            messages.append({"role": "tool", "tool_call_id": call.id, "content": content})

    # 轮数用完仍未给出回答：撤掉工具，让模型只基于已有资料作答
    logger.warning("达到工具调用轮数上限 %d，强制生成回答", MAX_TOOL_ROUNDS)
    msg = _chat(messages, with_tools=False)
    return _finish(msg.content, sources)