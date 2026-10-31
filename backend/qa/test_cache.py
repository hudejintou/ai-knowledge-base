from unittest.mock import patch

import fakeredis
import redis
from django.test import TestCase

from qa import cache


class CacheTests(TestCase):
    def setUp(self):
        # 测试用 fakeredis，不依赖真实 Redis；每个测试一个新实例，天然互不干扰
        self.fake = fakeredis.FakeRedis()
        patcher = patch("qa.cache.get_cache_client", return_value=self.fake)
        patcher.start()
        self.addCleanup(patcher.stop)

    def test_miss_returns_none(self):
        self.assertIsNone(cache.get_cached_answer("没有缓存过的问题"))

    def test_set_then_get(self):
        cache.set_cached_answer("怎么做缓存？", False, "测试回答")
        self.assertEqual(cache.get_cached_answer("怎么做缓存？"), (False, "测试回答"))

    def test_refused_result_is_cached(self):
        cache.set_cached_answer("今天股市怎么样？", True, "[NO_ANSWER]")
        self.assertEqual(cache.get_cached_answer("今天股市怎么样？"), (True, "[NO_ANSWER]"))

    def test_ttl_is_set(self):
        cache.set_cached_answer("怎么做缓存？", False, "测试回答")
        ttl = self.fake.ttl(cache.cache_key("怎么做缓存？"))
        self.assertGreater(ttl, 0)
        self.assertLessEqual(ttl, cache.CACHE_TTL)

    def test_redis_down_degrades_gracefully(self):
        # 模拟 Redis 连接失败：读和写都不应抛异常
        broken = patch("qa.cache.get_cache_client")
        mock_client = broken.start()
        self.addCleanup(broken.stop)
        mock_client.return_value.get.side_effect = redis.ConnectionError("down")
        mock_client.return_value.set.side_effect = redis.ConnectionError("down")

        self.assertIsNone(cache.get_cached_answer("怎么做缓存？"))
        cache.set_cached_answer("怎么做缓存？", False, "测试回答")  # 不抛异常即通过
class ClearCacheTests(TestCase):
    """测试缓存清理：只删问答缓存，不误删其他键。"""

    def setUp(self):
        self.fake = fakeredis.FakeRedis()
        patcher = patch("qa.cache.get_cache_client", return_value=self.fake)
        patcher.start()
        self.addCleanup(patcher.stop)

    def test_clear_removes_only_answer_keys(self):
        cache.set_cached_answer("问题一", False, "回答一")
        cache.set_cached_answer("问题二", True, "[NO_ANSWER]")
        # 模拟其他业务键，它们不应被清除
        self.fake.set("other:key", "keep-me")

        deleted = cache.clear_answer_cache()

        self.assertEqual(deleted, 2)
        self.assertIsNone(cache.get_cached_answer("问题一"))
        self.assertIsNone(cache.get_cached_answer("问题二"))
        self.assertEqual(self.fake.get("other:key"), b"keep-me")

    def test_clear_when_redis_down_returns_zero(self):
        broken = patch("qa.cache.get_cache_client")
        mock_client = broken.start()
        self.addCleanup(broken.stop)
        mock_client.return_value.scan_iter.side_effect = redis.ConnectionError("down")

        # 不抛异常，返回 0
        self.assertEqual(cache.clear_answer_cache(), 0)