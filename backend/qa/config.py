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
    "你是严谨的问答助手，只能依据用户提供的资料回答。"
    "回答前先判断：资料中是否有明确写出问题所问的答案。"
    "如果资料直接包含答案，用中文简洁作答，不要补充资料之外的事实。"
    "如果资料只涉及相关主题，但没有直接回答问题，或需要你自行推测、组合推理才能得出结论，"
    f"必须只输出 {NO_ANSWER}，不要给出推测性的建议。"
    "如果资料与问题无关，同样只输出 " + NO_ANSWER + "。"
)
# ===== 阶段 E：工具调用（Function Calling）配置 =====

# 每次检索返回的资料条数
TOP_K = int(os.getenv("TOP_K", "3"))

# 最多允许模型发起几轮工具调用；超过后撤掉工具，强制给出回答，防止死循环
MAX_TOOL_ROUNDS = 3

# 每轮最多执行几次检索；超出的调用会收到"未执行"的回复，但仍要回应
MAX_CALLS_PER_ROUND = 2

# 工具模式的系统提示：先检索，再严格依据资料作答，并标注引用编号
TOOL_SYSTEM_PROMPT = (
    "你是企业知识库问答助手。回答任何问题前，必须先调用 search_knowledge 检索资料。"
    "只依据检索到的资料回答，不使用资料之外的知识，也不要推测。"
    "资料中没有直接写出问题答案时，只输出 " + NO_ANSWER + "。"
    "回答时用中文简洁作答，并在引用某段资料的句末标注其编号，如 [1]。"
)
# ===== 问答模式开关 =====
# tools：模型自主决定是否检索（工具调用流程）；baseline：固定检索一次后作答
# 未识别的取值一律回退到 baseline，避免拼写错误导致行为不明
QA_MODE = os.getenv("QA_MODE", "tools")
if QA_MODE not in ("tools", "baseline"):
    QA_MODE = "tools"
# ===== 文档切块 =====
# 长文本入库时按字符切块：每块最多 CHUNK_SIZE 字，相邻块重叠 CHUNK_OVERLAP 字，
# 重叠用于避免关键句恰好落在块边界上被切断。
# 默认值与实验记录中的候选值一致（400/50），但仍是候选，可用环境变量覆盖。
CHUNK_SIZE = int(os.getenv("CHUNK_SIZE", "400"))
CHUNK_OVERLAP = int(os.getenv("CHUNK_OVERLAP", "50"))
if not 0 <= CHUNK_OVERLAP < CHUNK_SIZE:
    raise ValueError("CHUNK_OVERLAP 必须满足 0 <= CHUNK_OVERLAP < CHUNK_SIZE")
