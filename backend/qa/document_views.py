"""文档接口：提交、查询状态、删除。

- POST   /api/documents/           提交文本（长文本切块），返回 202 与 ids
- GET    /api/documents/<id>/      查询单块入库状态
- DELETE /api/documents/<id>/      删除单块，成功返回 204，并清空问答缓存
- DELETE /api/documents/batch/     请求体 {"ids": [...]} 批量删除，返回删除数量与未找到的 id

注意：DELETE 带请求体在部分代理和浏览器中可能被丢弃，调用方需要支持 DELETE with body。
"""

import logging

from kombu.exceptions import OperationalError as BrokerError
from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView

from qa.cache import clear_answer_cache
from qa.chunker import split_text
from qa.models import Document
from qa.tasks import embed_document_task

logger = logging.getLogger(__name__)


class DocumentCreateView(APIView):
    """POST /api/documents/  请求体：{"content": "..."}

    响应：
    - 202：{"ids": [...], "chunks": N, "status": "pending"}，每个 id 对应一块，向量由 worker 异步计算。
    - 400：content 为空、不是字符串。
    - 503：无法连接任务队列（Redis）。文档块已保存，ids 随响应返回，之后可用 backfill_embeddings 补算。
    """

    def post(self, request):
        content = request.data.get("content")
        # 类型和空白都要检查：非字符串或只有空格的内容都拒绝
        if not isinstance(content, str) or not content.strip():
            return Response({"error": "content 不能为空"}, status=status.HTTP_400_BAD_REQUEST)

        chunks = split_text(content)
        # 逐块保存，拿到每块的 id
        ids = [Document.objects.create(content=chunk).id for chunk in chunks]

        try:
            for doc_id in ids:
                embed_document_task.delay(doc_id)
        except BrokerError:
            # 部分块可能已入队；任务是幂等的，补算时可以安全重投
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
    """/api/documents/<id>/：GET 查询状态，DELETE 删除单块。"""

    def get(self, request, doc_id):
        """查询单块入库状态，不返回正文和向量。

        - 200：{"id", "status", "content_length"}；ready 有向量，pending 尚无向量。
        - 404：文档不存在。
        局限：pending 同时包含"排队中"和"任务失败未补算"，无法区分。
        """
        doc = Document.objects.filter(id=doc_id).first()
        if doc is None:
            return Response({"error": "文档不存在"}, status=status.HTTP_404_NOT_FOUND)

        # 状态由数据推导：有向量即 ready，不另存字段
        state = "pending" if doc.embedding is None else "ready"
        return Response(
            {"id": doc.id, "status": state, "content_length": len(doc.content)},
            status=status.HTTP_200_OK,
        )

    def delete(self, request, doc_id):
        """删除单块。删除后清空问答缓存，因为旧答案可能引用了这一块。

        - 204：删除成功，无响应体。
        - 404：文档不存在。
        """
        deleted, _ = Document.objects.filter(id=doc_id).delete()
        if deleted == 0:
            return Response({"error": "文档不存在"}, status=status.HTTP_404_NOT_FOUND)

        # 缓存清理失败只记日志（函数内部降级），不影响删除结果
        clear_answer_cache()
        return Response(status=status.HTTP_204_NO_CONTENT)


class DocumentBatchDeleteView(APIView):
    """DELETE /api/documents/batch/  请求体：{"ids": [1, 2, 3]}

    用于删除一篇长文档切出的全部块。
    - 200：{"deleted": N, "not_found": [...]}，明确告知哪些 id 不存在。
    - 400：ids 缺失、不是列表、为空，或包含非整数。
    只清一次缓存。
    """

    def delete(self, request):
        ids = request.data.get("ids")
        # 类型校验：必须是非空列表，且元素全为整数（bool 也排除，因为 True 是 int 的子类）
        if (
            not isinstance(ids, list)
            or not ids
            or not all(isinstance(i, int) and not isinstance(i, bool) for i in ids)
        ):
            return Response(
                {"error": "ids 必须是非空的整数列表"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # 去重后再查询，避免同一个 id 重复计数
        unique_ids = set(ids)
        existing = set(
            Document.objects.filter(id__in=unique_ids).values_list("id", flat=True)
        )
        Document.objects.filter(id__in=existing).delete()

        clear_answer_cache()
        return Response(
            {
                "deleted": len(existing),
                "not_found": sorted(unique_ids - existing),
            },
            status=status.HTTP_200_OK,
        )