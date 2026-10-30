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