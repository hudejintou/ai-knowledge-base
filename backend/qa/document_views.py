"""文档接口：提交文档（切块后异步入库）与查询入库状态。

- POST /api/documents/：保存文本（长文本切成多块），提交 Celery 任务，返回 202 与 ids。
- GET  /api/documents/<id>/：查询单块的入库状态。
"""

import logging

from kombu.exceptions import OperationalError as BrokerError
from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView

from qa.chunker import split_text
from qa.models import Document
from qa.tasks import embed_document_task

logger = logging.getLogger(__name__)


class DocumentCreateView(APIView):
    """POST /api/documents/  请求体：{"content": "..."}

    响应：
    - 202：{"ids": [...], "chunks": N, "status": "pending"}，每个 id 对应一块，向量由 worker 异步计算。
    - 400：content 为空、不是字符串。
    - 503：无法连接任务队列（Redis）。文档块已保存但可能未入队，ids 随响应返回，
      之后可用 backfill_embeddings 补算。
    """

    def post(self, request):
        content = request.data.get("content")
        # 类型和空白都要检查：非字符串或只有空格的内容都拒绝
        if not isinstance(content, str) or not content.strip():
            return Response(
                {"error": "content 不能为空"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        chunks = split_text(content)
        # 逐块保存，拿到每块的 id。块数通常很少，逐条写入即可
        ids = [Document.objects.create(content=chunk).id for chunk in chunks]

        try:
            for doc_id in ids:
                embed_document_task.delay(doc_id)
        except BrokerError:
            # 部分块可能已入队，部分未入队；任务是幂等的，补算时可以安全重投
            logger.error("任务提交失败：无法连接 broker（Redis），%d 块中部分未计算向量", len(ids))
            return Response(
                {"error": "任务队列暂时不可用，请稍后重试", "ids": ids},
                status=status.HTTP_503_SERVICE_UNAVAILABLE,
            )

        return Response(
            {"ids": ids, "chunks": len(ids), "status": "pending"},
            status=status.HTTP_202_ACCEPTED,
        )


class DocumentDetailView(APIView):
    """GET /api/documents/<id>/

    查询单块文档的入库状态，不返回正文和向量。
    - 200：{"id", "status", "content_length"}；ready 表示已有向量，pending 表示尚无向量。
    - 404：文档不存在。
    局限：pending 同时包含"排队中"和"任务失败后尚未补算"，无法区分。
    """

    def get(self, request, doc_id):
        doc = Document.objects.filter(id=doc_id).first()
        if doc is None:
            return Response({"error": "文档不存在"}, status=status.HTTP_404_NOT_FOUND)

        # 状态由数据推导：有向量即 ready，不另存字段
        state = "pending" if doc.embedding is None else "ready"
        return Response(
            {
                "id": doc.id,
                "status": state,
                # 只返回正文长度，避免响应过大
                "content_length": len(doc.content),
            },
            status=status.HTTP_200_OK,
        )