"""问答缓存：用 Redis 保存"问题 -> 完整问答结果"。

设计要点：
- key 用问题的 SHA256，避免中文和特殊字符直接作为 key。
- 缓存的是完整结果 dict（refused、answer、sources），命中时不需要重新检索。
- 拒答结果也缓存，无关问题不必每次都调用模型。
- Redis 不可用时降级：缓存失效但问答接口仍可用，只记日志，不抛异常。
"""

import hashlib
import json
import logging
import os

import redis

logger = logging.getLogger(__name__)

# 缓存有效期 1 小时（秒）
CACHE_TTL = 3600

# 可用环境变量覆盖；默认连本机 Redis 的 0 号库（Celery 用的是 1 号库）
REDIS_URL = os.getenv("REDIS_URL", "redis://127.0.0.1:6379/0")

# 所有问答缓存的键名前缀，清理时只删这个前缀下的键
KEY_PREFIX = "qa:answer:"

# 模块级单例：连接池由 redis-py 内部管理，不需要每次请求都新建
_client = None


def get_cache_client():
    """返回 Redis 客户端（单例）。

    socket_timeout 设为 1 秒：Redis 挂了时最多等 1 秒，不让问答接口卡住。
    """
    global _client
    if _client is None:
        _client = redis.Redis.from_url(
            REDIS_URL,
            socket_connect_timeout=1,
            socket_timeout=1,
        )
    return _client


def cache_key(question):
    """问题 + 模式 -> Redis key。模式不同，答案可能不同，必须分开缓存。"""
    from qa.config import QA_MODE  # 局部导入，避免循环依赖
    digest = hashlib.sha256(f"{QA_MODE}|{question}".encode("utf-8")).hexdigest()
    return KEY_PREFIX + digest

def get_cached_answer(question):
    """命中返回完整结果 dict；未命中、Redis 出错或旧格式数据返回 None。"""
    try:
        raw = get_cache_client().get(cache_key(question))
    except redis.RedisError as exc:
        # 降级：Redis 不可用时当作未命中，继续走检索和生成
        logger.warning("缓存读取失败，降级为直接调用模型: %s", exc)
        return None

    if raw is None:
        return None

    try:
        data = json.loads(raw)
    except ValueError as exc:
        logger.warning("缓存内容无法解析，已忽略: %s", exc)
        return None

    # 旧版本缓存格式（refused + text）不再识别，视为未命中
    if not isinstance(data, dict) or "refused" not in data or "answer" not in data:
        return None
    return data


def set_cached_answer(question, result):
    """写入完整结果。写入失败只记日志，不影响本次返回给用户的结果。"""
    payload = json.dumps(result, ensure_ascii=False)
    try:
        get_cache_client().set(cache_key(question), payload, ex=CACHE_TTL)
    except redis.RedisError as exc:
        logger.warning("缓存写入失败，本次结果未缓存: %s", exc)


def clear_answer_cache():
    """删除所有问答缓存，返回删除的条数。

    用于新文档入库后，让旧答案不再被返回。
    - 用 SCAN 分批遍历，不用 KEYS（KEYS 会阻塞 Redis）。
    - 只匹配 KEY_PREFIX，不会误删 Celery 或其他业务键。
    - 出错只记日志并返回 0，清理失败不应影响入库任务本身。
    """
    try:
        client = get_cache_client()
        deleted = 0
        for key in client.scan_iter(match=KEY_PREFIX + "*", count=500):
            client.delete(key)
            deleted += 1
        return deleted
    except redis.RedisError as exc:
        logger.warning("清空问答缓存失败，旧答案将保留至 TTL 过期: %s", exc)
        return 0