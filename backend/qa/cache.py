"""问答缓存：用 Redis 保存"问题 -> (拒答标记, 回答)"的结果。

设计要点：
- key 用问题的 SHA256，避免中文和特殊字符直接作为 key。
- 拒答结果也缓存：同一个无关问题不必每次都调用智谱。
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

# 可用环境变量覆盖；默认连本机 Redis 的 0 号库
REDIS_URL = os.getenv("REDIS_URL", "redis://127.0.0.1:6379/0")

KEY_PREFIX = "qa:answer:"

# 模块级单例：连接池由 redis-py 内部管理，不需要每次请求都新建
_client = None


def get_cache_client():
    """返回 Redis 客户端。换库或换地址只改 REDIS_URL 环境变量即可。

    socket_timeout 设成 1 秒：Redis 挂了时最多等 1 秒，不让问答接口卡住。
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
    """问题 -> Redis key。注意：问题要先 strip，否则前后空格会产生不同 key。"""
    digest = hashlib.sha256(question.encode("utf-8")).hexdigest()
    return KEY_PREFIX + digest


def get_cached_answer(question):
    """命中返回 (refused, text)，未命中或 Redis 出错返回 None。"""
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
        return data["refused"], data["text"]
    except (ValueError, KeyError) as exc:
        # 缓存内容损坏时删除这条记录，避免反复出错
        logger.warning("缓存内容损坏，已忽略: %s", exc)
        return None


def set_cached_answer(question, refused, text):
    """写入缓存。写入失败只记日志，不影响本次返回给用户的结果。"""
    payload = json.dumps({"refused": refused, "text": text}, ensure_ascii=False)
    try:
        get_cache_client().set(cache_key(question), payload, ex=CACHE_TTL)
    except redis.RedisError as exc:
        logger.warning("缓存写入失败，本次结果未缓存: %s", exc)