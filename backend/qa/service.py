import os

from openai import OpenAI

from qa.retrieval import retrieve_from_db

# 本地 embedding 客户端：与 rag_v1.py 使用同一个 LM Studio 服务和模型
LMSTUDIO_BASE_URL = os.getenv("LMSTUDIO_BASE_URL", "http://127.0.0.1:1234/v1")
EMB_MODEL = "text-embedding-qwen3-embedding-0.6b"
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
CHAT_MODEL = os.getenv("CHAT_MODEL", "glm-5.3-flash")
NO_ANSWER = "[NO_ANSWER]"
ANSWER_SYSTEM_PROMPT = (
    "你是严谨的问答助手。只能依据用户提供的资料回答。"
    "只要资料中包含与问题直接相关的信息，就应作答，"
    "不要因为缺少细节或措辞不同而拒答。"
    f"只有资料与问题完全无关，或完全无法推出答案时，才只输出 {NO_ANSWER}。"
    "作答时用中文简洁回答，不要补充资料之外的事实。"
)


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