"""检索健康检查：确认扩充语料中每段都能被 top-k 召回。

只做检索，不调用智谱，不比较两种问答模式。
题目与标准段号来自切分实验（实验 18/19 的设计），早于本次扩充，未针对结果调整。
标准段号是扩充段落的序号（0 到 23），对应 ALL_DOCS 的下标为 20 + 序号。

运行（容器内）：python manage.py retrieval_check
"""

from django.core.management.base import BaseCommand

from qa.config import TOP_K
from qa.retrieval import retrieve_from_db
from qa.service import embed_query
from rag.corpus import ALL_DOCS

OFFSET = 20  # 扩充段落在 ALL_DOCS 中的起始下标

# (问题, 扩充段落序号)，共 12 题，覆盖 4 篇来源
CHECK_SET = [
    ("RAG 这个词最早出现在哪篇论文中？", 0),
    ("RAG-Token 更适合什么类型的问题？", 2),
    ("替换知识索引为什么能更新模型掌握的知识？", 5),
    ("余弦相似度的取值范围是多少？", 7),
    ("dimensions 参数的作用是什么？", 9),
    ("BM25 适合检索什么类型的查询？", 12),
    ("仅用上下文化嵌入时，top-20 失败率从多少降到多少？", 15),
    ("RAG 对 LLM 响应的接地是什么意思？", 18),
    ("代理式检索由谁负责查询规划？", 20),
    ("混合检索指的是什么，它为什么能提高召回？", 21),
    ("Foundry IQ 是什么？", 23),
    ("经典 RAG 模式适合什么场景？", 20),
]


class Command(BaseCommand):
    help = "检查扩充语料的检索召回：每题是否在 top-k 中找到标准段落"

    def handle(self, *args, **options):
        hits = 0
        for question, seg in CHECK_SET:
            target = ALL_DOCS[OFFSET + seg]
            results = retrieve_from_db(embed_query(question), top_k=TOP_K)
            texts = [t for t, _ in results]
            rank = texts.index(target) + 1 if target in texts else None
            ok = rank is not None
            hits += ok
            status = f"命中，排名第 {rank}" if ok else "未命中"
            self.stdout.write(f"[段{seg:>2}] {question} -> {status}")

        self.stdout.write("")
        self.stdout.write(f"top-{TOP_K} 召回：{hits}/{len(CHECK_SET)} = {hits / len(CHECK_SET):.2%}")