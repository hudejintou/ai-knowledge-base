"""导入知识库语料：把 rag.corpus.ALL_DOCS 写入 Document 表。

作用：初始化数据库时使用。注意它会先清空 Document 表，
所以不要在已有通过 API 新增文档的库上执行。
运行：python manage.py load_corpus
"""

import sys
from pathlib import Path

from django.core.management.base import BaseCommand

from qa.models import Document

# 把项目根加入路径，才能导入 rag 包（与 views.py 的做法一致）
PROJECT_ROOT = Path(__file__).resolve().parents[4]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

# 注意：只导入语料，不导入 rag_v1，避免连接 LM Studio
from rag.corpus import ALL_DOCS  # noqa: E402


class Command(BaseCommand):
    """先清空，再把 ALL_DOCS 逐条写入。重复运行结果一致（幂等）。"""

    help = "从 rag/corpus.py 导入完整知识库语料（只写文本，不计算向量）"

    def handle(self, *args, **options):
        # 先删后插，保证多次运行不会产生重复数据
        Document.objects.all().delete()
        Document.objects.bulk_create([Document(content=text) for text in ALL_DOCS])
        self.stdout.write(self.style.SUCCESS(f"已导入 {len(ALL_DOCS)} 条文档"))