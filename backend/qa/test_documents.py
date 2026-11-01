"""文档相关测试：切块、文档提交接口、Celery 入库任务、文档状态查询接口。

测试策略：
- 所有外部依赖（Celery 任务投递、Embedding 客户端、缓存清理）都用 mock 替换，
  测试不需要 Redis、LM Studio 或智谱 API，运行快且结果确定。
- 每个测试类对应一个被测对象：ChunkerTests 测切块函数，
  DocumentCreateViewTests 测提交接口，EmbedDocumentTaskTests 测入库任务，
  DocumentDetailViewTests 测状态查询接口。
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
        # 用循环的字母序列构造文本，便于检查相邻块的重叠是否正确：
        # 前一块的末尾 overlap 个字符，应等于后一块的开头 overlap 个字符
        text = "abcdefghij" * 10  # 共 100 字
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
    """测试 POST /api/documents/ 接口：校验、切块、投递任务、错误处理。"""

    def _post(self, payload):
        """辅助方法：以 JSON 形式向文档接口发送 POST 请求。"""
        return self.client.post("/api/documents/", payload, content_type="application/json")

    def test_empty_content_returns_400(self):
        # 空白内容应返回 400，并且不能写入任何数据
        resp = self._post({"content": "   "})
        self.assertEqual(resp.status_code, 400)
        self.assertEqual(Document.objects.count(), 0)

    def test_non_string_content_returns_400(self):
        # content 不是字符串（这里是数字）时应返回 400
        resp = self._post({"content": 123})
        self.assertEqual(resp.status_code, 400)

    @patch("qa.document_views.embed_document_task.delay")
    def test_short_content_returns_one_id(self, mock_delay):
        # 短文本不需要切块：只生成一条 Document，返回一个 id
        resp = self._post({"content": "  Redis 是内存数据库  "})
        self.assertEqual(resp.status_code, 202)
        doc = Document.objects.get()
        # 首尾空白应已被去掉
        self.assertEqual(doc.content, "Redis 是内存数据库")
        # 入库时还没有向量，向量由后台任务计算
        self.assertIsNone(doc.embedding)
        self.assertEqual(resp.json(), {"ids": [doc.id], "chunks": 1, "status": "pending"})
        # 确认对这一条文档投递了任务
        mock_delay.assert_called_once_with(doc.id)

    @patch("qa.document_views.embed_document_task.delay")
    def test_long_content_is_split_and_every_chunk_enqueued(self, mock_delay):
        # 长文本（约 3 个块的长度）应被切成多块，每一块都是一条 Document，并且都投递了任务
        resp = self._post({"content": "甲" * (CHUNK_SIZE * 3)})
        self.assertEqual(resp.status_code, 202)

        body = resp.json()
        ids = body["ids"]
        self.assertGreater(len(ids), 1)
        # chunks 字段应与 ids 的长度一致
        self.assertEqual(body["chunks"], len(ids))
        self.assertEqual(Document.objects.count(), len(ids))
        # 投递的任务 id 集合应与返回的 ids 完全一致（不遗漏、不重复）
        enqueued = sorted(c.args[0] for c in mock_delay.call_args_list)
        self.assertEqual(enqueued, sorted(ids))

    @patch("qa.document_views.embed_document_task.delay", side_effect=BrokerError("redis down"))
    def test_broker_down_returns_503_but_keeps_chunks(self, _mock):
        # 任务队列不可用时应返回 503，但已经保存的文档块必须保留，并且响应中带上 ids，便于之后补算
        resp = self._post({"content": "一段文档"})
        self.assertEqual(resp.status_code, 503)
        body = resp.json()
        self.assertIn("ids", body)
        self.assertEqual(Document.objects.count(), len(body["ids"]))


class EmbedDocumentTaskTests(TestCase):
    """测试 Celery 入库任务 embed_document_task（直接调用函数，不经过 worker）。"""

    def setUp(self):
        # 每个测试前创建一条没有向量的文档
        self.doc = Document.objects.create(content="Redis 是内存数据库")

    @patch("qa.tasks.clear_answer_cache", return_value=0)
    @patch("qa.tasks._embed_client")
    def test_task_writes_embedding_and_model(self, mock_client, _clear):
        # 模拟 Embedding 服务返回一个三维向量，检查任务是否把向量和模型名写回数据库
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
        # 文档已有向量时，任务应直接跳过，不再调用 Embedding 服务（幂等，避免重复计费和重复计算）
        self.doc.embedding = [1.0, 0.0]
        self.doc.save()
        embed_document_task(self.doc.id)
        mock_client.embeddings.create.assert_not_called()

    @patch("qa.tasks._embed_client")
    def test_missing_document_is_skipped(self, mock_client):
        # 文档在任务执行前被删除：任务应返回 None 并跳过，不调用 Embedding 服务
        self.assertIsNone(embed_document_task(999999))
        mock_client.embeddings.create.assert_not_called()

    def test_retry_policy_is_configured(self):
        # 检查重试参数确实挂在任务上（最多 3 次，启用指数退避），防止以后改动时意外丢失
        self.assertEqual(embed_document_task.max_retries, 3)
        self.assertTrue(embed_document_task.retry_backoff)


class DocumentDetailViewTests(TestCase):
    """测试 GET /api/documents/<id>/ 接口：待处理、已完成、不存在、不泄露内容。"""

    def test_pending_document_returns_pending(self):
        # 没有向量的文档状态为 pending，并返回正文长度
        doc = Document.objects.create(content="还没有向量的文档")
        resp = self.client.get(f"/api/documents/{doc.id}/")
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json(), {
            "id": doc.id,
            "status": "pending",
            "content_length": len("还没有向量的文档"),
        })

    def test_ready_document_returns_ready(self):
        # 有向量的文档状态为 ready
        doc = Document.objects.create(content="已有向量", embedding=[0.1, 0.2])
        resp = self.client.get(f"/api/documents/{doc.id}/")
        self.assertEqual(resp.json()["status"], "ready")

    def test_missing_document_returns_404(self):
        # 不存在的 id 返回 404，并带有 error 字段
        resp = self.client.get("/api/documents/999999/")
        self.assertEqual(resp.status_code, 404)
        self.assertIn("error", resp.json())

    def test_response_does_not_leak_content_or_embedding(self):
        # 状态接口不应返回正文和向量，只返回状态信息，避免响应过大或泄露文档内容
        doc = Document.objects.create(content="秘密正文", embedding=[0.5])
        body = self.client.get(f"/api/documents/{doc.id}/").json()
        self.assertNotIn("content", body)
        self.assertNotIn("embedding", body)