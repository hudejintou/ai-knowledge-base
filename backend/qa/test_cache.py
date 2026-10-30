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