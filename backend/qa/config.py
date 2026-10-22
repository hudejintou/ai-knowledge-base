"""集中存放问答相关的配置，避免 service.py 与 rag_v1.py 各写一份而漂移。"""

import os

# 回答模型名：可用环境变量覆盖，默认值与 rag_v1.py 保持一致
CHAT_MODEL = os.getenv("CHAT_MODEL", "glm-5.3-flash")

# 本地 embedding 配置：LM Studio 的 OpenAI 兼容接口
LMSTUDIO_BASE_URL = os.getenv("LMSTUDIO_BASE_URL", "http://127.0.0.1:1234/v1")
EMB_MODEL = "text-embedding-qwen3-embedding-0.6b"

# 拒答标记：模型在资料不足时输出它，代码据此拒答
NO_ANSWER = "[NO_ANSWER]"

ANSWER_SYSTEM_PROMPT = (
    "你是严谨的问答助手。只能依据用户提供的资料回答。"
    "只要资料中包含与问题直接相关的信息，就应作答，"
    "不要因为缺少细节或措辞不同而拒答。"
    f"只有资料与问题完全无关，或完全无法推出答案时，才只输出 {NO_ANSWER}。"
    "作答时用中文简洁回答，不要补充资料之外的事实。"
)