"""切分实验：比较块大小 200 / 400 / 800 对检索命中率的影响。

运行（项目根目录）：
    python -m experiments.topk_chunk.run_chunk_exp

本脚本只调用 LM Studio 的 embedding，不调用智谱，因此不消耗额度。
需要 LM Studio 已开启并加载 text-embedding-qwen3-embedding-0.6b。
"""
import json
from pathlib import Path

import numpy as np
from openai import OpenAI

from experiments.topk_chunk.chunker import split_chunks
from experiments.topk_chunk.judge import is_hit, is_top1_hit

EMB_MODEL = "text-embedding-qwen3-embedding-0.6b"
client = OpenAI(api_key="lm-studio", base_url="http://127.0.0.1:1234/v1")

TEXT_PATH = Path("experiments/topk_chunk/corpus_v3_all.txt")
TOP_K = 3
CHUNK_SIZES = [200, 400, 800]
OVERLAP = 50

# 标准段落的字符区间，由脚本根据段落顺序自动计算，不需要手写位置
def paragraph_spans(text):
    spans, cursor = [], 0
    for para in text.split("\n\n"):
        para = para.strip()
        if not para:
            continue
        start = text.index(para, cursor)  # 从上一段之后开始查找，避免重复匹配
        spans.append((start, start + len(para)))
        cursor = start + len(para)
    return spans

# 题目与标准段号（None 表示无关题，无标准段落）
# 标准段号：单个整数表示单段可答；列表表示跨段题，需要命中列表中的所有段落

# 全局段号 0–23：0–5 为文档1（RAG论文），6–11 为文档2（OpenAI嵌入），
# 12–17 为文档3（Anthropic上下文检索），18–23 为文档4（Microsoft RAG）。
# 无关题的标准段号为 None，不参与命中率计算。
QUESTIONS = [
    # 文档 1：RAG 原始论文（段 0–5）
    ("RAG 这个词最早出现在哪篇论文中？", 0),
    ("大型预训练语言模型在知识访问上存在什么局限？", 0),
    ("RAG 中的参数化记忆和非参数化记忆分别是什么？", 1),
    ("RAG 的检索器和生成器分别采用什么模型？", 1),
    ("RAG-Sequence 和 RAG-Token 的区别是什么？", 2),
    ("RAG-Token 更适合什么类型的问题？", 2),
    ("论文中维基百科的知识源是如何切分的？", 3),
    ("论文用什么索引结构做最大内积搜索？", 3),
    ("RAG 在 TriviaQA 上相比哪类方法有明显提升？", 4),
    ("替换知识索引为什么能更新模型掌握的知识？", 5),
    # 文档 2：OpenAI 嵌入指南（段 6–11）
    ("嵌入是把什么映射成什么的技术？", 6),
    ("嵌入向量之间的距离通常用来刻画什么？", 6),
    ("余弦相似度的取值范围是多少？", 7),
    ("为什么余弦相似度对文本长短不敏感？", 7),
    ("text-embedding-3-small 的输出维度和价格是多少？", 8),
    ("text-embedding-3-large 相比 small 有什么特点？", 8),
    ("第三代嵌入模型的最大输入长度是多少，超长文本怎么办？", 8),
    ("dimensions 参数的作用是什么？", 9),
    ("嵌入在检索之外还有哪些典型应用？", 10),
    ("为什么查询和文档必须使用同一个嵌入模型？", 11),
    # 文档 3：Anthropic 上下文检索（段 12–17）
    ("标准 RAG 的预处理流程包括哪几步？", 12),
    ("为什么嵌入模型常需要配合 BM25 使用？", 12),
    ("BM25 适合检索什么类型的查询？", 12),
    ("传统 RAG 的上下文难题指什么？", 13),
    ("上下文化嵌入和上下文化 BM25 分别是什么？", 14),
    ("生成块上下文说明时，Anthropic 用什么方法降低成本？", 14),
    ("文中的评估指标 1 减 recall@20 指什么？", 15),
    ("仅用上下文化嵌入时，top-20 失败率从多少降到多少？", 15),
    ("重排序在流程中处于什么位置，文中用了多少候选和保留数量？", 16),
    ("文中测试出的最佳组合是什么？", 17),
    # 文档 4：Microsoft Learn RAG（段 18–23）
    ("RAG 对 LLM 响应的接地是什么意思？", 18),
    ("RAG 主要能缓解 LLM 的哪两类问题？", 18),
    ("查询理解的挑战是什么，举例说明？", 19),
    ("RAG 实现中的五类主要挑战有哪些？", 19),
    ("代理式检索由谁负责查询规划？", 20),
    ("经典 RAG 模式适合什么场景？", 20),
    ("混合检索指的是什么，它为什么能提高召回？", 21),
    ("页面列出的内容准备支持能力有哪些？", 22),
    ("页面建议在哪些情况下优先选择代理式检索？", 23),
    ("Foundry IQ 是什么？", 23),
    # 无关题
    ("AI 能否预测明天的股价？", None),
    ("今天中午吃什么比较好？", None),
    ("北京今天的天气怎么样？", None),
    ("介绍一下猫的饮食习惯。", None),
    # 跨段题：需要同时依据相邻两段信息（段号用列表表示，要求每段都命中）
    ("RAG 的检索器和生成器分别采用什么模型，它们如何联合训练？", [1, 2]),
    ("Anthropic 的上下文化处理和重排序分别解决什么问题？", [14, 16]),
    ("Microsoft 的混合检索和代理式检索各自的作用是什么？", [20, 21]),
    ("OpenAI 的余弦相似度与嵌入维度选择之间有什么关系？", [7, 9]),
]

def embed(texts):
    resp = client.embeddings.create(model=EMB_MODEL, input=texts)
    return np.array([d.embedding for d in resp.data], dtype=np.float32)

def cosine_top_k(query_vec, doc_vecs, k):
    sims = doc_vecs @ query_vec / (np.linalg.norm(doc_vecs, axis=1) * np.linalg.norm(query_vec))
    return sims.argsort()[::-1][:k]

def run_one(text, chunk_size, para_spans):
    chunks = split_chunks(text, chunk_size, OVERLAP)
    chunk_vecs = embed([c["text"] for c in chunks])
    results = []
    for question, para_idx in QUESTIONS:
        q_vec = embed([question])[0]
        top = cosine_top_k(q_vec, chunk_vecs, TOP_K)
        hit_chunks = [chunks[i] for i in top]
        if para_idx is None:
            results.append({"question": question, "type": "无关", "hit": None, "top1": None})
            continue
        # 关键：跨段题要求每个目标段落都被命中，单段题则只有一个目标段
        targets = para_idx if isinstance(para_idx, list) else [para_idx]
        hit = all(is_hit(hit_chunks, para_spans[i]) for i in targets)
        top1 = all(is_top1_hit([chunks[top[0]]], para_spans[i]) for i in targets)
        results.append({"question": question, "type": "可答", "hit": hit, "top1": top1})
    return results

if __name__ == "__main__":
    text = TEXT_PATH.read_text(encoding="utf-8")
    spans = paragraph_spans(text)
    print(f"段落数：{len(spans)}")  # 应输出 7
    summary = {}
    for size in CHUNK_SIZES:
        res = run_one(text, size, spans)
        answerable = [r for r in res if r["type"] == "可答"]
        hit_rate = sum(r["hit"] for r in answerable) / len(answerable)
        top1_rate = sum(r["top1"] for r in answerable) / len(answerable)
        summary[size] = {"top3命中率": round(hit_rate, 4), "top1命中率": round(top1_rate, 4), "明细": res}
        print(f"块大小 {size}：top-3 命中率 {hit_rate:.2%}，top-1 命中率 {top1_rate:.2%}")
    out = Path(f"evals/runs/chunk_exp_18_{'_'.join(map(str, CHUNK_SIZES))}.json")
    out.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"结果已保存: {out}")