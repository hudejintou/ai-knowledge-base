from django.contrib import admin
from django.urls import path

from qa.document_views import (
    DocumentBatchDeleteView,
    DocumentCreateView,
    DocumentDetailView,
)
from qa.views import AskView

urlpatterns = [
    path("admin/", admin.site.urls),
    # POST：问答，见 qa/views.py
    path("api/ask/", AskView.as_view(), name="ask"),
    # POST：提交文档并异步计算向量，返回 202
    path("api/documents/", DocumentCreateView.as_view(), name="document-create"),
    # DELETE：批量删除，必须写在单块路由之前，语义上更明确
    path("api/documents/batch/", DocumentBatchDeleteView.as_view(), name="document-batch-delete"),
    # GET 查询状态 / DELETE 删除单块。<int:doc_id> 只匹配整数，因此不会与 batch 冲突
    path("api/documents/<int:doc_id>/", DocumentDetailView.as_view(), name="document-detail"),
]