import sys
from pathlib import Path

from django.core.management.base import BaseCommand

from qa.models import Document

# 把项目根加入路径，才能导入 rag 包（和 views.py 的做法一致）
PROJECT_ROOT = Path(__file__).resolve().parents[4]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

# 注意：这里只导入 DOCS 列表，不导入 rag_v1。
# rag_v1 导入时会连接 LM Studio，本命令不需要它，所以刻意避开。
from rag.corpus import DOCS  # noqa: E402


class Command(BaseCommand):
    """把 corpus.py 的 DOCS 写入 Document 表。重复运行会清空后重新写入，保证幂等。"""

    help = "从 rag/corpus.py 导入知识库文档（只写文本，不计算向量）"

    def handle(self, *args, **options):
        # 关键：先删后插，保证多次运行结果一致，不会产生重复数据
        Document.objects.all().delete()
        Document.objects.bulk_create(
            [Document(content=text) for text in DOCS]
        )
        self.stdout.write(self.style.SUCCESS(f"已导入 {len(DOCS)} 条文档"))