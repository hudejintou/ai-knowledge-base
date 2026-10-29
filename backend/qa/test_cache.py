from django.test import SimpleTestCase
import fakeredis

from qa.cache import cache_key, get_cached_answer, set_cached_answer


class CacheTests(SimpleTestCase):
    def setUp(self):
        # 关键：每个测试用新的 FakeRedis，互不污染
        self.client_r = fakeredis.FakeRedis(decode_responses=True)

    def test_miss_returns_none(self):
        self.assertIsNone(get_cached_answer(self.client_r, "没有缓存的问题"))

    def test_set_then_get(self):
        set_cached_answer(self.client_r, "怎么做缓存？", False, "使用 Redis")
        self.assertEqual(
            get_cached_answer(self.client_r, "怎么做缓存？"),
            {"refused": False, "answer": "使用 Redis"},
        )

    def test_refused_is_cached_too(self):
        # 拒答也应被缓存，否则同一拒答问题会重复调用模型
        set_cached_answer(self.client_r, "今天股市怎么样？", True, None)
        self.assertEqual(
            get_cached_answer(self.client_r, "今天股市怎么样？"),
            {"refused": True, "answer": None},
        )

    def test_ttl_is_set(self):
        set_cached_answer(self.client_r, "怎么做缓存？", False, "使用 Redis")
        self.assertGreater(self.client_r.ttl(cache_key("怎么做缓存？")), 0)
