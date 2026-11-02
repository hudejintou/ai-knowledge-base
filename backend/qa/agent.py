"""阶段 E：工具调用版问答（Function Calling + RAG）。

与旧流程 service.ask_with_db 的区别：
- 旧流程：固定检索一次，把资料直接交给模型。
- 新流程：模型自己决定是否检索、检索什么（可改写查询、可并行调用）；
  后端执行检索并把结果回传，循环直到模型给出最终回答或达到轮数上限。

对外暴露 ask_with_tools(question)，返回：
    {
        "refused": bool,
        "answer": str,
        "sources": [{"n": 编号, "doc_id": 块id, "text": 资料正文}],  # 回答中实际引用的资料，接口返回这个
        "retrieved": [资料正文, ...],                  # 所有检索到的资料，仅评估用
        "queries": [检索语句, ...],                    # 模型发出的检索语句，仅评估用
    }
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
from qa.retrieval import search_documents
from qa.service import chat_client, embed_query

logger = logging.getLogger(__name__)

# 工具定义，按 OpenAI 兼容的 tools 格式描述。
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
    """调用一次模型，返回它的 message 对象。with_tools=False 时模型无法再调用工具。"""
    kwargs = {"model": CHAT_MODEL, "messages": messages, "temperature": 0}
    if with_tools:
        kwargs["tools"] = [SEARCH_TOOL]
    return chat_client.chat.completions.create(**kwargs).choices[0].message


def _run_search(call, sources, queries):
    """执行一次 search_knowledge 调用，返回要回传给模型的文本。

    sources：本次问答累计的资料列表，元素为 {"doc_id", "text"}。
             按 doc_id 去重：同一个块被多次检索到时只保留一份，编号保持不变。
    queries：本次问答模型发出的检索语句列表，仅用于评估记录。
    """
    try:
        args = json.loads(call.function.arguments)
        query = (args.get("query") or "").strip()
    except (ValueError, AttributeError):
        return "工具参数无效，请提供 query 字段。"
    if not query:
        return "query 不能为空。"

    queries.append(query)
    hits = search_documents(embed_query(query), top_k=TOP_K)
    if not hits:
        return "没有检索到相关资料。"

    lines = []
    for hit in hits:
        # 关键：按 doc_id 查找是否已有该块，而不是按正文。
        # 两个正文相同但 id 不同的块是两条记录，应当分别保留
        index = next(
            (i for i, s in enumerate(sources) if s["doc_id"] == hit["doc_id"]),
            None,
        )
        if index is None:
            sources.append({"doc_id": hit["doc_id"], "text": hit["content"]})
            index = len(sources) - 1
        # 编号 = 在 sources 中的位置 + 1，模型回答中的 [n] 据此对应到资料
        lines.append(f"[{index + 1}] {hit['content']}")
    return "\n".join(lines)


def _finish(text, sources, queries):
    """把模型的最终文本整理成返回结构。

    sources 中只保留回答里真正被引用的块，并保留 doc_id，
    便于调用方追溯到具体的块。
    """
    text = (text or "").strip()
    refused = NO_ANSWER in text or not text
    # retrieved 仍然只返回正文列表，评估脚本的覆盖率计算依赖它
    retrieved = [s["text"] for s in sources]
    if refused:
        return {"refused": True, "answer": text, "sources": [],
                "retrieved": retrieved, "queries": list(queries)}

    cited = {int(n) for n in re.findall(r"\[(\d+)\]", text)}
    used = [
        {"n": i + 1, "doc_id": s["doc_id"], "text": s["text"]}
        for i, s in enumerate(sources)
        if (i + 1) in cited
    ]
    return {"refused": False, "answer": text, "sources": used,
            "retrieved": retrieved, "queries": list(queries)}

def ask_with_tools(question):
    """工具调用问答主循环。"""
    sources = []
    queries = []
    messages = [
        {"role": "system", "content": TOOL_SYSTEM_PROMPT},
        {"role": "user", "content": question},
    ]

    for round_no in range(1, MAX_TOOL_ROUNDS + 1):
        msg = _chat(messages, with_tools=True)

        if not msg.tool_calls:
            logger.info("问答完成：共 %d 轮工具调用", round_no - 1)
            return _finish(msg.content, sources, queries)

        messages.append(msg)
        logger.info("工具调用第 %d 轮：模型请求 %d 次检索", round_no, len(msg.tool_calls))

        for i, call in enumerate(msg.tool_calls):
            if i >= MAX_CALLS_PER_ROUND:
                content = "本轮检索次数已达上限，未执行该调用。"
            else:
                content = _run_search(call, sources, queries)
            messages.append({"role": "tool", "tool_call_id": call.id, "content": content})

    logger.warning("达到工具调用轮数上限 %d，强制生成回答", MAX_TOOL_ROUNDS)
    msg = _chat(messages, with_tools=False)
    return _finish(msg.content, sources, queries)