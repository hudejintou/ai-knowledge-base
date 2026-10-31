from django.core.management.base import BaseCommand

from qa.models import Document
from qa.tasks import embed_document_task


class Command(BaseCommand):
    """找出 embedding 为空的文档，逐条投递到 Celery 补算向量。

    适用场景：LM Studio 关闭或 worker 重试耗尽后，文档停留在 embedding=None。
    任务本身是幂等的，重复运行不会重复计算已有向量的文档。
    """

    help = "为 embedding 为空的 Document 重新投递向量计算任务"

    def add_arguments(self, parser):
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="只列出待处理的文档 id，不投递任务",
        )

    def handle(self, *args, **options):
        # 只取待处理的 id。values_list 避免把整段 content 和 embedding 读进内存
        pending_ids = list(
            Document.objects.filter(embedding__isnull=True)
            .order_by("id")
            .values_list("id", flat=True)
        )

        if not pending_ids:
            self.stdout.write("没有需要补算向量的文档")
            return

        if options["dry_run"]:
            self.stdout.write(f"[dry-run] 共 {len(pending_ids)} 条待补算：{pending_ids}")
            return

        # 逐条投递。任务内部是幂等的，即使 id 重复投递也不会重复调用模型
        for doc_id in pending_ids:
            embed_document_task.delay(doc_id)

        self.stdout.write(self.style.SUCCESS(f"已投递 {len(pending_ids)} 条补算任务：{pending_ids}"))