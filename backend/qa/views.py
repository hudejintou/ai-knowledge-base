from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView

# 只从 qa.service 导入。service 不导入 rag_v1，
# 所以启动 Django 时不会连接 LM Studio，也不会计算全部文档向量。
from qa.service import ask_with_db


class AskView(APIView):
    """POST /api/ask/  请求体：{"question": "..."}"""

    def post(self, request):
        question = (request.data.get("question") or "").strip()
        # 空问题直接返回 400，不调用模型，节省额度
        if not question:
            return Response(
                {"error": "question 不能为空"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # 检索改为读数据库，拒答判断逻辑与之前一致
        refused, text = ask_with_db(question)
        # 响应结构不变：拒答时 answer 为 null
        return Response(
            {"refused": refused, "answer": None if refused else text},
            status=status.HTTP_200_OK,
        )