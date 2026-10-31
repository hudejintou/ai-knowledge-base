import json
from unittest.mock import patch

import fakeredis
import redis
from django.test import TestCase

from qa import cache

SAMPLE = {"refused": False, "answer": "测试回答", "sources": [{"n": 1, "text": "资料"}]}


class CacheTests(TestCase):
    def setUp(self):
        # 每个测试一个新的 fakeredis 实例，天然互不干扰
        self.fake = fakeredis.FakeRedis()
        patcher = patch("qa.cache.get_cache_client", return_value=self.fake)
        patcher.start()
        self.addCleanup(patcher.stop)

    def test_miss_returns_none(self):
        self.assertIsNone(cache.get_cached_answer("没有缓存过的问题"))

    def test_set_then_get_returns_full_result(self):
        cache.set_cached_answer("怎么做缓存？", SAMPLE)
        self.assertEqual(cache.get_cached_answer("怎么做缓存？"), SAMPLE)

    def test_refused_result_is_cached(self):
        refused = {"refused": True, "answer": "[NO_ANSWER]", "sources": []}
        cache.set_cached_answer("今天股市怎么样？", refused)
        self.assertEqual(cache.get_cached_answer("今天股市怎么样？"), refused)

    def test_ttl_is_set(self):
        cache.set_cached_answer("怎么做缓存？", SAMPLE)
        ttl = self.fake.ttl(cache.cache_key("怎么做缓存？"))
        self.assertGreater(ttl, 0)
        self.assertLessEqual(ttl, cache.CACHE_TTL)

    def test_legacy_format_is_treated_as_miss(self):
        # 旧格式（refused + text）不再识别，应视为未命中
        self.fake.set(cache.cache_key("旧问题"), json.dumps({"refused": False, "text": "旧"}))
        self.assertIsNone(cache.get_cached_answer("旧问题"))

    def test_redis_down_degrades_gracefully(self):
        broken = patch("qa.cache.get_cache_client")
        mock_client = broken.start()
        self.addCleanup(broken.stop)
        mock_client.return_value.get.side_effect = redis.ConnectionError("down")
        mock_client.return_value.set.side_effect = redis.ConnectionError("down")

        self.assertIsNone(cache.get_cached_answer("怎么做缓存？"))
        cache.set_cached_answer("怎么做缓存？", SAMPLE)  # 不抛异常即通过

    def test_clear_removes_only_answer_keys(self):
        cache.set_cached_answer("问题一", SAMPLE)
        cache.set_cached_answer("问题二", SAMPLE)
        self.fake.set("other:key", "keep-me")

        deleted = cache.clear_answer_cache()

        self.assertEqual(deleted, 2)
        self.assertIsNone(cache.get_cached_answer("问题一"))
        self.assertEqual(self.fake.get("other:key"), b"keep-me")

    def test_clear_when_redis_down_returns_zero(self):
        broken = patch("qa.cache.get_cache_client")
        mock_client = broken.start()
        self.addCleanup(broken.stop)
        mock_client.return_value.scan_iter.side_effect = redis.ConnectionError("down")
        self.assertEqual(cache.clear_answer_cache(), 0)