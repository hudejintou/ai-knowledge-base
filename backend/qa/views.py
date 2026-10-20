import sys
from pathlib import Path

from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework import status

# 让 Django 能导入项目根目录下的 rag 包：
# 当前文件在 backend/qa/views.py，项目根是往上两级
PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

# 注意：导入 rag_v1 时会立即连接 LM Studio 并计算文档向量。
# 所以 LM Studio 没启动时，Django 启动（或首次请求）就会报错。
from rag.rag_v1 import answer_with_judgement  # noqa: E402


class AskView(APIView):
    """POST /api/ask/  请求体：{"question": "..."}"""

    def post(self, request):
        question = (request.data.get("question") or "").strip()
        # 异常输入：空问题直接返回 400，不调用模型，节省额度
        if not question:
            return Response(
                {"error": "question 不能为空"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        refused, text = answer_with_judgement(question)
        # 拒答与可答使用同一个结构，前端只看 refused 字段即可
        return Response(
            {"refused": refused, "answer": None if refused else text},
            status=status.HTTP_200_OK,
        )