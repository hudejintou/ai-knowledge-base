from unittest.mock import MagicMock, patch

from django.test import TestCase
from kombu.exceptions import OperationalError as BrokerError

from qa.models import Document
from qa.tasks import embed_document_task


class DocumentCreateViewTests(TestCase):
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
    def test_valid_content_returns_202_and_enqueues(self, mock_delay):
        resp = self._post({"content": "  Redis 是内存数据库  "})
        self.assertEqual(resp.status_code, 202)
        doc = Document.objects.get()
        self.assertEqual(doc.content, "Redis 是内存数据库")  # 首尾空白已去掉
        self.assertIsNone(doc.embedding)                     # 此时还没有向量
        self.assertEqual(resp.json(), {"id": doc.id, "status": "pending"})
        mock_delay.assert_called_once_with(doc.id)

    @patch("qa.document_views.embed_document_task.delay", side_effect=BrokerError("redis down"))
    def test_broker_down_returns_503_but_keeps_document(self, _mock):
        resp = self._post({"content": "一段文档"})
        self.assertEqual(resp.status_code, 503)
        # 文档已保存，便于之后补算向量
        self.assertEqual(Document.objects.count(), 1)


class EmbedDocumentTaskTests(TestCase):
    def setUp(self):
        self.doc = Document.objects.create(content="Redis 是内存数据库")

    @patch("qa.tasks._embed_client")
    def test_task_writes_embedding_and_model(self, mock_client):
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
        self.doc.embedding = [1.0, 0.0]
        self.doc.save()
        embed_document_task(self.doc.id)
        mock_client.embeddings.create.assert_not_called()  # 已有向量，不重复调用模型

    @patch("qa.tasks._embed_client")
    def test_missing_document_is_skipped(self, mock_client):
        self.assertIsNone(embed_document_task(999999))
        mock_client.embeddings.create.assert_not_called()

    def test_retry_policy_is_configured(self):
        # 确认重试参数确实挂在任务上，防止以后改动时意外丢失
        self.assertEqual(embed_document_task.max_retries, 3)
        self.assertTrue(embed_document_task.retry_backoff)