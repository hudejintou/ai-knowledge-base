import logging

from kombu.exceptions import OperationalError as BrokerError
from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView

from qa.models import Document
from qa.tasks import embed_document_task

logger = logging.getLogger(__name__)


class DocumentCreateView(APIView):
    """POST /api/documents/  请求体：{"content": "..."}

    只保存文本并提交后台任务，立即返回 202。向量由 Celery worker 异步计算。
    """

    def post(self, request):
        content = request.data.get("content")
        # 类型和空白都要检查：非字符串或只有空格的内容都拒绝
        if not isinstance(content, str) or not content.strip():
            return Response(
                {"error": "content 不能为空"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        doc = Document.objects.create(content=content.strip())

        try:
            embed_document_task.delay(doc.id)
        except BrokerError:
            # Redis 不可用时任务无法入队。文档已保存但没有向量，
            # 这种状态可以之后用 embedding__isnull=True 找出来补算
            logger.error("任务提交失败：无法连接 broker（Redis），文档 %s 尚未计算向量", doc.id)
            return Response(
                {"error": "任务队列暂时不可用，请稍后重试", "id": doc.id},
                status=status.HTTP_503_SERVICE_UNAVAILABLE,
            )

        return Response(
            {"id": doc.id, "status": "pending"},
            status=status.HTTP_202_ACCEPTED,
        )
class DocumentDetailView(APIView):
    """GET /api/documents/<id>/

    查询单条文档的入库状态，不返回正文和向量，只返回状态信息。

    响应：
    - 200：找到文档，返回 {"id", "status", "content_length"}
      - status 为 "ready"：已有向量，可以被检索
      - status 为 "pending"：还没有向量（排队中，或任务失败后尚未补算）
    - 404：文档不存在

    局限：目前只区分 ready 和 pending。任务重试耗尽后，文档同样显示 pending，
    无法和"仍在排队"区分。要区分需要单独记录任务状态，留到以后再做。
    """

    def get(self, request, doc_id):
        # first() 找不到时返回 None，而不是抛异常，便于统一返回 404
        doc = Document.objects.filter(id=doc_id).first()
        if doc is None:
            return Response({"error": "文档不存在"}, status=status.HTTP_404_NOT_FOUND)

        # 向量为空即视为 pending；有向量即 ready。状态由数据推导，不另存一个字段
        state = "pending" if doc.embedding is None else "ready"
        return Response(
            {
                "id": doc.id,
                "status": state,
                # 只返回正文长度，避免接口响应过大，也避免无意间暴露文档内容
                "content_length": len(doc.content),
            },
            status=status.HTTP_200_OK,
        )