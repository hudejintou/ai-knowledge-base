from django.db import models


class Document(models.Model):
    """知识库的一条文档片段。文本与向量一起入库，检索时不再依赖 corpus.py。"""

    # 文档正文，对应 corpus.py 里 DOCS 的一个元素
    content = models.TextField()

    # 向量以 JSON 列表形式存储（SQLite 无原生数组类型）。
    # 为空表示尚未计算向量，入库流程会补上。
    embedding = models.JSONField(null=True, blank=True)

    # 记录生成向量所用的模型名。不同模型的向量不能直接比较，
    # 所以换模型时可以通过这个字段找出需要重算的文档。
    embedding_model = models.CharField(max_length=128, blank=True, default="")

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        # 后台和调试时显示前 30 个字符，避免整段正文刷屏
        return self.content[:30]