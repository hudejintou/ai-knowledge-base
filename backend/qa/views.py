from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView

from qa.cache import get_cached_answer, set_cached_answer
from qa.service import ask_with_db

# 关键：缓存客户端集中在这里获取。目前用 fakeredis（内存模拟，进程重启即清空）。
# 以后有真实 Redis 时，只需要把这个函数改成 redis.Redis(...)，视图代码不用动。
_cache_client = None


def get_cache_client():
    global _cache_client
    if _cache_client is None:
        import fakeredis
        _cache_client = fakeredis.FakeRedis(decode_responses=True)
    return _cache_client


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

        client = get_cache_client()
        # 关键：先查缓存，命中则直接返回，不调用检索和智谱
        cached = get_cached_answer(client, question)
        if cached is not None:
            return Response(cached, status=status.HTTP_200_OK)

        refused, text = ask_with_db(question)
        answer = None if refused else text
        # 关键：可答和拒答都写入缓存
        set_cached_answer(client, question, refused, answer)
        return Response(
            {"refused": refused, "answer": answer},
            status=status.HTTP_200_OK,
        )
