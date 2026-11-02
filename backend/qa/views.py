"""问答接口 POST /api/ask/。

流程：校验参数 -> 查缓存 -> 未命中则调用工具版问答 -> 写缓存 -> 返回。
响应：
- 200：{"refused": bool, "answer": str|null, "sources": [{"n", "doc_id", "text"}]}
- 400：问题为空
- 502：上游鉴权失败（智谱 Key 错误）或上游返回错误
- 503：上游不可达、超时或限流
- 500：未预期的内部错误（只返回通用信息，完整堆栈写入日志）
"""

import logging

import openai
from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView

from qa.agent import ask_with_tools
from qa.config import QA_MODE
from qa.service import ask_with_db
from qa.cache import get_cached_answer, set_cached_answer

logger = logging.getLogger(__name__)

def _run_mode(question):
    """按 QA_MODE 选择流程，统一返回 {"refused", "answer", "sources"}。"""
    if QA_MODE == "tools":
        return ask_with_tools(question)
    refused, text = ask_with_db(question)
    # 基线流程返回的是 (refused, text)，没有引用信息，sources 为空
    return {"refused": refused, "answer": text, "sources": []}

def _error(http_status, message):
    """统一的错误响应格式：{"error": "..."}"""
    return Response({"error": message}, status=http_status)


class AskView(APIView):
    """POST /api/ask/  请求体：{"question": "..."}"""

    def post(self, request):
        question = (request.data.get("question") or "").strip()
        if not question:
            return _error(status.HTTP_400_BAD_REQUEST, "question 不能为空")

        # 先查缓存：命中则不调用模型
        result = get_cached_answer(question)
        if result is None:
            try:
                result = _run_mode(question)
            # 注意顺序：子类必须写在父类前面。
            # AuthenticationError、RateLimitError 都是 APIStatusError 的子类；
            # APITimeoutError 是 APIConnectionError 的子类。
            except openai.AuthenticationError:
                # 只记录类型和提示，不记录异常内容，避免 Key 误入日志
                logger.error("上游模型鉴权失败（401），请检查服务进程的 ZHIPU_API_KEY")
                return _error(status.HTTP_502_BAD_GATEWAY, "上游模型鉴权失败，请检查服务配置")
            except openai.APITimeoutError:
                logger.error("上游服务请求超时")
                return _error(status.HTTP_503_SERVICE_UNAVAILABLE, "上游服务响应超时，请稍后重试")
            except openai.APIConnectionError:
                logger.error("无法连接上游服务（检查 LM Studio 或网络）")
                return _error(status.HTTP_503_SERVICE_UNAVAILABLE, "上游服务暂时不可用")
            except openai.RateLimitError:
                logger.error("上游服务限流（429）")
                return _error(status.HTTP_503_SERVICE_UNAVAILABLE, "上游服务繁忙，请稍后重试")
            except openai.APIError as exc:
                logger.error("上游服务返回错误: %s", type(exc).__name__)
                return _error(status.HTTP_502_BAD_GATEWAY, "上游服务返回错误")
            except Exception:
                # 兜底：未预料的错误记录完整堆栈，但只向用户返回通用信息
                logger.exception("问答接口发生未预期的错误")
                return _error(status.HTTP_500_INTERNAL_SERVER_ERROR, "服务内部错误")

            # 只有成功时才写缓存，错误结果不缓存
            set_cached_answer(question, result)

        refused = result["refused"]
        return Response(
            {
                "refused": refused,
                "answer": None if refused else result["answer"],
                "sources": result["sources"],
            },
            status=status.HTTP_200_OK,
        )