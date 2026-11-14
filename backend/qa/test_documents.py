"""文档相关测试：切块、提交接口、Celery 入库任务、状态查询、删除接口。

测试策略：外部依赖（Celery 投递、Embedding 客户端、缓存）全部 mock，
不需要 Redis、LM Studio 或智谱 API。
"""

from unittest.mock import MagicMock, patch

from django.test import TestCase
from kombu.exceptions import OperationalError as BrokerError

from qa.chunker import split_text
from qa.config import CHUNK_OVERLAP, CHUNK_SIZE
from qa.models import Document
from qa.tasks import embed_document_task


class ChunkerTests(TestCase):
    """测试 split_text 切块函数（纯函数，不需要数据库）。"""

    def test_empty_returns_empty_list(self):
        # 只有空白的文本应返回空列表，不产生空块
        self.assertEqual(split_text("   "), [])

    def test_short_text_is_one_chunk(self):
        # 长度不超过 size 的文本整体作为一块
        self.assertEqual(split_text("短文本", size=40, overlap=10), ["短文本"])

    def test_adjacent_chunks_overlap(self):
        # 前一块的末尾 overlap 个字符，应等于后一块的开头 overlap 个字符
        text = "abcdefghij" * 10
        chunks = split_text(text, size=40, overlap=10)
        self.assertGreater(len(chunks), 1)
        for prev, nxt in zip(chunks, chunks[1:]):
            self.assertEqual(prev[-10:], nxt[:10])

    def test_no_chunk_exceeds_size(self):
        # 无论文本多长，每一块都不能超过配置的块大小
        chunks = split_text("甲" * 1000, size=CHUNK_SIZE, overlap=CHUNK_OVERLAP)
        self.assertTrue(all(len(c) <= CHUNK_SIZE for c in chunks))

    def test_invalid_overlap_raises(self):
        # 重叠不小于块大小时步长会变成 0 或负数，函数必须拒绝
        with self.assertRaises(ValueError):
            split_text("abc", size=10, overlap=10)


class DocumentCreateViewTests(TestCase):
    """测试 POST /api/documents/：校验、切块、投递任务、错误处理。"""

    def _post(self, payload):
        return self.client.post("/api/documents/", payload, content_type="application/json")

    def test_empty_content_returns_400(self):
        resp = self._post({"content": "   "})
        self.assertEqual(resp.status_code, 400)
        self.assertEqual(Document.objects.count(), 0)

    def test_non_string_content_returns_400(self):
        resp = self._post({"content": 123})
        self.assertEqual(resp.status_code, 400)

    @patch("qa.document_views.embed_document_task.delay")
    def test_short_content_returns_one_id(self, mock_delay):
        resp = self._post({"content": "  Redis 是内存数据库  "})
        self.assertEqual(resp.status_code, 202)
        doc = Document.objects.get()
        self.assertEqual(doc.content, "Redis 是内存数据库")
        self.assertIsNone(doc.embedding)
        self.assertEqual(resp.json(), {"ids": [doc.id], "chunks": 1, "status": "pending"})
        mock_delay.assert_called_once_with(doc.id)

    @patch("qa.document_views.embed_document_task.delay")
    def test_long_content_is_split_and_every_chunk_enqueued(self, mock_delay):
        resp = self._post({"content": "甲" * (CHUNK_SIZE * 3)})
        self.assertEqual(resp.status_code, 202)
        body = resp.json()
        ids = body["ids"]
        self.assertGreater(len(ids), 1)
        self.assertEqual(body["chunks"], len(ids))
        self.assertEqual(Document.objects.count(), len(ids))
        enqueued = sorted(c.args[0] for c in mock_delay.call_args_list)
        self.assertEqual(enqueued, sorted(ids))

    @patch("qa.document_views.embed_document_task.delay", side_effect=BrokerError("redis down"))
    def test_broker_down_returns_503_but_keeps_chunks(self, _mock):
        resp = self._post({"content": "一段文档"})
        self.assertEqual(resp.status_code, 503)
        body = resp.json()
        self.assertIn("ids", body)
        self.assertEqual(Document.objects.count(), len(body["ids"]))


class EmbedDocumentTaskTests(TestCase):
    """测试 Celery 入库任务 embed_document_task（直接调用函数，不经过 worker）。"""

    def setUp(self):
        self.doc = Document.objects.create(content="Redis 是内存数据库")

    @patch("qa.tasks.clear_answer_cache", return_value=0)
    @patch("qa.tasks._embed_client")
    def test_task_writes_embedding_and_model(self, mock_client, _clear):
        mock_client.embeddings.create.return_value = MagicMock(
            data=[MagicMock(embedding=[0.1, 0.2, 0.3])]
        )
        result = embed_document_task(self.doc.id)
        self.assertEqual(result, self.doc.id)
        self.doc.refresh_from_db()
        self.assertEqual(self.doc.embedding, [0.1, 0.2, 0.3])
        self.assertEqual(self.doc.embedding_model, "text-embedding-qwen3-embedding-0.6b")

    @patch("qa.tasks._embed_client")
    def test_task_is_idempotent_when_embedding_exists(self, mock_client):
        # 已有向量时直接跳过，不重复调用 Embedding 服务
        self.doc.embedding = [1.0, 0.0]
        self.doc.save()
        embed_document_task(self.doc.id)
        mock_client.embeddings.create.assert_not_called()

    @patch("qa.tasks._embed_client")
    def test_missing_document_is_skipped(self, mock_client):
        self.assertIsNone(embed_document_task(999999))
        mock_client.embeddings.create.assert_not_called()

    def test_retry_policy_is_configured(self):
        self.assertEqual(embed_document_task.max_retries, 3)
        self.assertTrue(embed_document_task.retry_backoff)


class DocumentDetailViewTests(TestCase):
    """测试 GET /api/documents/<id>/：待处理、已完成、不存在、不泄露内容。"""

    def test_pending_document_returns_pending(self):
        doc = Document.objects.create(content="还没有向量的文档")
        resp = self.client.get(f"/api/documents/{doc.id}/")
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json(), {
            "id": doc.id,
            "status": "pending",
            "content_length": len("还没有向量的文档"),
        })

    def test_ready_document_returns_ready(self):
        doc = Document.objects.create(content="已有向量", embedding=[0.1, 0.2])
        resp = self.client.get(f"/api/documents/{doc.id}/")
        self.assertEqual(resp.json()["status"], "ready")

    def test_missing_document_returns_404(self):
        resp = self.client.get("/api/documents/999999/")
        self.assertEqual(resp.status_code, 404)
        self.assertIn("error", resp.json())

    def test_response_does_not_leak_content_or_embedding(self):
        doc = Document.objects.create(content="秘密正文", embedding=[0.5])
        body = self.client.get(f"/api/documents/{doc.id}/").json()
        self.assertNotIn("content", body)
        self.assertNotIn("embedding", body)


class DocumentDeleteTests(TestCase):
    """测试 DELETE 单块与批量删除：成功、404、400、缓存清理。"""

    def _delete_one(self, doc_id):
        return self.client.delete(f"/api/documents/{doc_id}/")

    def _delete_batch(self, payload):
        # 注意：Django 测试客户端的 delete 支持 data + content_type，用于 DELETE 带请求体
        return self.client.delete(
            "/api/documents/batch/",
            data=payload,
            content_type="application/json",
        )

    @patch("qa.document_views.clear_answer_cache", return_value=0)
    def test_delete_one_returns_204_and_clears_cache(self, mock_clear):
        doc = Document.objects.create(content="待删除")
        resp = self._delete_one(doc.id)
        self.assertEqual(resp.status_code, 204)
        self.assertFalse(Document.objects.filter(id=doc.id).exists())
        mock_clear.assert_called_once()

    def test_delete_missing_one_returns_404(self):
        resp = self._delete_one(999999)
        self.assertEqual(resp.status_code, 404)
        self.assertIn("error", resp.json())

    @patch("qa.document_views.clear_answer_cache", return_value=0)
    def test_batch_delete_removes_all_and_reports_not_found(self, mock_clear):
        a = Document.objects.create(content="块A")
        b = Document.objects.create(content="块B")
        resp = self._delete_batch({"ids": [a.id, b.id, 999999]})
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json(), {"deleted": 2, "not_found": [999999]})
        self.assertEqual(Document.objects.count(), 0)
        # 批量删除只清一次缓存
        mock_clear.assert_called_once()

    @patch("qa.document_views.clear_answer_cache", return_value=0)
    def test_batch_delete_dedups_ids(self, _mock):
        a = Document.objects.create(content="块A")
        resp = self._delete_batch({"ids": [a.id, a.id]})
        self.assertEqual(resp.json(), {"deleted": 1, "not_found": []})

    def test_batch_delete_invalid_payload_returns_400(self):
        for payload in [{}, {"ids": []}, {"ids": "1,2"}, {"ids": [1, "2"]}, {"ids": [True]}]:
            with self.subTest(payload=payload):
                resp = self._delete_batch(payload)
                self.assertEqual(resp.status_code, 400)