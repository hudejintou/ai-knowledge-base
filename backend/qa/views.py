from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView

from qa.cache import get_cached_answer, set_cached_answer
from qa.service import ask_with_db


class AskView(APIView):
    """POST /api/ask/  请求体：{"question": "..."}"""

    def post(self, request):
        question = (request.data.get("question") or "").strip()
        # 空问题直接返回 400，不查缓存，不调模型
        if not question:
            return Response(
                {"error": "question 不能为空"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # 先查缓存：命中则不检索、不调智谱
        cached = get_cached_answer(question)
        if cached is not None:
            refused, text = cached
        else:
            refused, text = ask_with_db(question)
            set_cached_answer(question, refused, text)

        # 响应结构不变：拒答时 answer 为 null
        return Response(
            {"refused": refused, "answer": None if refused else text},
            status=status.HTTP_200_OK,
        )