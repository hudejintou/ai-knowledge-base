import os

from openai import OpenAI

from qa.retrieval import retrieve_from_db
from qa.config import CHAT_MODEL, EMB_MODEL, NO_ANSWER, ANSWER_SYSTEM_PROMPT, LMSTUDIO_BASE_URL

# 本地 embedding 客户端：与 rag_v1.py 使用同一个 LM Studio 服务和模型
embed_client = OpenAI(
    api_key=os.getenv("LMSTUDIO_API_KEY", "lm-studio"),
    base_url=LMSTUDIO_BASE_URL,
)

# 云端回答客户端：智谱。Key 从环境变量读取，不写进代码
chat_client = OpenAI(
    api_key=os.environ["ZHIPU_API_KEY"],
    base_url="https://open.bigmodel.cn/api/paas/v4/",
)
# 注意：这里复制了 rag_v1.py 的模型名和 Prompt，需与其保持一致。


def embed_query(text):
    """计算单条问题的向量。这一步需要 LM Studio 在运行。"""
    response = embed_client.embeddings.create(model=EMB_MODEL, input=[text])
    return response.data[0].embedding


def ask_with_db(question, top_k=3):
    """从数据库检索资料，再让回答模型判断可答性。

    返回 (refused, text)，与 rag_v1.answer_with_judgement 的返回结构一致。
    """
    # 关键：检索只读数据库，不再依赖 corpus.py 或导入时计算的 DOC_VECS
    hits = retrieve_from_db(embed_query(question), top_k=top_k)
    context = "\n".join(content for content, _ in hits)

    response = chat_client.chat.completions.create(
        model=CHAT_MODEL,
        messages=[
            {"role": "system", "content": ANSWER_SYSTEM_PROMPT},
            {"role": "user", "content": f"资料：\n{context}\n\n问题：{question}"},
        ],
        temperature=0,
    )
    text = response.choices[0].message.content.strip()
    # 拒答判断仍然只看标记是否出现，与旧逻辑一致
    return NO_ANSWER in text, text