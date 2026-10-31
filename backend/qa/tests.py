from unittest.mock import patch

import fakeredis
from django.test import TestCase

from qa.models import Document
from qa.retrieval import retrieve_from_db


class AskViewTests(TestCase):
    def setUp(self):
        # 接口测试换成 fakeredis，不连真实 Redis，每个测试一个新实例
        cache_patcher = patch("qa.cache.get_cache_client", return_value=fakeredis.FakeRedis())
        cache_patcher.start()
        self.addCleanup(cache_patcher.stop)

    # patch 的路径写"被使用的地方"：视图里导入后的名字 qa.views.ask_with_tools
    @patch("qa.views.ask_with_tools", return_value={
        "refused": False,
        "answer": "测试回答",
        "sources": [{"n": 1, "text": "资料"}],
    })
    def test_answerable(self, _mock):
        resp = self.client.post("/api/ask/", {"question": "怎么做缓存？"}, content_type="application/json")
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json(), {
            "refused": False,
            "answer": "测试回答",
            "sources": [{"n": 1, "text": "资料"}],
        })

    @patch("qa.views.ask_with_tools", return_value={
        "refused": True,
        "answer": "[NO_ANSWER]",
        "sources": [],
    })
    def test_refused(self, _mock):
        resp = self.client.post("/api/ask/", {"question": "今天股市怎么样？"}, content_type="application/json")
        self.assertEqual(resp.json(), {"refused": True, "answer": None, "sources": []})

    def test_empty_question(self):
        resp = self.client.post("/api/ask/", {"question": "  "}, content_type="application/json")
        self.assertEqual(resp.status_code, 400)


class RetrieveFromDbTests(TestCase):
    def setUp(self):
        # 测试数据库是临时的，每个测试开始前都是空表，不会污染 db.sqlite3
        # 两条极简向量：[1,0] 与问题同向（分数 1.0），[0,1] 与问题正交
        Document.objects.create(content="与问题同向的文档", embedding=[1.0, 0.0])
        Document.objects.create(content="与问题正交的文档", embedding=[0.0, 1.0])

    def test_returns_most_similar_first(self):
        hits = retrieve_from_db([1.0, 0.0], top_k=2)
        self.assertEqual(hits[0][0], "与问题同向的文档")
        self.assertAlmostEqual(hits[0][1], 1.0, places=5)

    def test_skips_documents_without_embedding(self):
        # 没有向量的文档不参与检索，也不报错
        Document.objects.create(content="尚未计算向量的文档", embedding=None)
        hits = retrieve_from_db([1.0, 0.0], top_k=5)
        self.assertNotIn("尚未计算向量的文档", [text for text, _ in hits])