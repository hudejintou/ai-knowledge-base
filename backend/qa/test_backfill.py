from io import StringIO
from unittest.mock import patch

from django.core.management import call_command
from django.test import TestCase

from qa.models import Document


class BackfillEmbeddingsTests(TestCase):
    def setUp(self):
        # 三条文档：两条缺向量，一条已有向量
        self.pending1 = Document.objects.create(content="待补算 A")
        self.pending2 = Document.objects.create(content="待补算 B")
        self.done = Document.objects.create(content="已完成", embedding=[1.0, 0.0])

    @patch("qa.management.commands.backfill_embeddings.embed_document_task.delay")
    def test_enqueues_only_documents_without_embedding(self, mock_delay):
        out = StringIO()
        call_command("backfill_embeddings", stdout=out)

        enqueued = sorted(c.args[0] for c in mock_delay.call_args_list)
        self.assertEqual(enqueued, sorted([self.pending1.id, self.pending2.id]))
        self.assertNotIn(self.done.id, enqueued)
        self.assertIn("已投递 2 条", out.getvalue())

    @patch("qa.management.commands.backfill_embeddings.embed_document_task.delay")
    def test_dry_run_does_not_enqueue(self, mock_delay):
        out = StringIO()
        call_command("backfill_embeddings", "--dry-run", stdout=out)

        mock_delay.assert_not_called()
        self.assertIn("[dry-run] 共 2 条", out.getvalue())

    @patch("qa.management.commands.backfill_embeddings.embed_document_task.delay")
    def test_no_pending_documents(self, mock_delay):
        Document.objects.filter(embedding__isnull=True).update(embedding=[0.5, 0.5])
        out = StringIO()
        call_command("backfill_embeddings", stdout=out)

        mock_delay.assert_not_called()
        self.assertIn("没有需要补算向量的文档", out.getvalue())