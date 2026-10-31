import logging
import os

import openai
from celery import shared_task
from openai import OpenAI

from qa.config import EMB_MODEL, LMSTUDIO_BASE_URL
from qa.models import Document
from qa.cache import clear_answer_cache

logger = logging.getLogger(__name__)

# worker 进程内的本地 Embedding 客户端，与 qa/service.py 指向同一个 LM Studio 服务。
# 创建客户端不会建立连接，所以 import 时不会因为 LM Studio 未启动而报错。
_embed_client = OpenAI(
    api_key=os.getenv("LMSTUDIO_API_KEY", "lm-studio"),
    base_url=LMSTUDIO_BASE_URL,
)


@shared_task(
    # 只对"可能暂时恢复"的错误自动重试：连接失败、超时、限流。
    # 鉴权错误（401）等重试也没用，直接失败。
    autoretry_for=(
        openai.APIConnectionError,
        openai.APITimeoutError,
        openai.RateLimitError,
    ),
    retry_backoff=True,      # 指数退避：第 1 次等约 1 秒，之后翻倍
    retry_backoff_max=60,    # 单次等待最多 60 秒
    retry_jitter=True,       # 加随机抖动，避免多个任务同时重试
    max_retries=3,           # 最多重试 3 次，即最多执行 4 次
)
def embed_document_task(doc_id):
    """为一条 Document 计算 embedding 并写回数据库。"""
    doc = Document.objects.filter(id=doc_id).first()
    if doc is None:
        # 文档可能在任务执行前被删除，这种情况不需要重试
        logger.warning("embed_document_task: 文档 %s 不存在，跳过", doc_id)
        return None

    # 幂等：已经有向量就直接返回。任务被重复投递时不会重复计算
    if doc.embedding is not None:
        return doc_id

    response = _embed_client.embeddings.create(model=EMB_MODEL, input=[doc.content])

    # 只更新需要的字段，避免覆盖并发修改的其他字段
    doc.embedding = response.data[0].embedding
    doc.embedding_model = EMB_MODEL
    doc.save(update_fields=["embedding", "embedding_model", "updated_at"])

    # 新文档已可被检索，之前的问答缓存可能已经过时，全部清空
    cleared = clear_answer_cache()
    logger.info("文档 %s 向量计算完成，已清除 %s 条问答缓存", doc_id, cleared)
    return doc_id