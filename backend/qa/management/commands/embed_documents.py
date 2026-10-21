import sys
from pathlib import Path

from django.core.management.base import BaseCommand

from qa.models import Document

# 把项目根加入路径，才能导入 rag 包（与 load_corpus.py 的做法一致）
PROJECT_ROOT = Path(__file__).resolve().parents[4]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

# 注意：这里导入 embed 函数和模型名，但 rag_v1 导入时会连接 LM Studio 并计算 DOC_VECS。
# 为了避免这一副作用，我们直接用 OpenAI 客户端调用 LM Studio，不导入 rag_v1。
import os  # noqa: E402
from openai import OpenAI  # noqa: E402

LMSTUDIO_BASE_URL = os.getenv("LMSTUDIO_BASE_URL", "http://127.0.0.1:1234/v1")
EMB_MODEL = "text-embedding-qwen3-embedding-0.6b"  # 必须与 rag_v1.py 中的模型一致
client = OpenAI(api_key=os.getenv("LMSTUDIO_API_KEY", "lm-studio"), base_url=LMSTUDIO_BASE_URL)


class Command(BaseCommand):
    """给 embedding 为空的文档计算向量并写回数据库，同时记录所用模型名。"""

    help = "为 Document 计算本地 embedding（只处理 embedding 为空的记录）"

    def handle(self, *args, **options):
        # 只取还没有向量的文档，重复运行不会重复计算，节省时间
        pending = list(Document.objects.filter(embedding__isnull=True))
        if not pending:
            self.stdout.write("没有需要计算向量的文档")
            return

        # 关键：批量请求 embedding，比逐条调用快。输入是文本列表，返回顺序与输入一致
        response = client.embeddings.create(
            model=EMB_MODEL,
            input=[doc.content for doc in pending],
        )

        for doc, item in zip(pending, response.data):
            doc.embedding = item.embedding
            doc.embedding_model = EMB_MODEL
            doc.save(update_fields=["embedding", "embedding_model", "updated_at"])

        self.stdout.write(self.style.SUCCESS(f"已计算 {len(pending)} 条文档的向量"))