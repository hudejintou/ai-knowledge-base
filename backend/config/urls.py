from django.contrib import admin
from django.urls import path

from qa.document_views import DocumentCreateView, DocumentDetailView
from qa.views import AskView

urlpatterns = [
    path("admin/", admin.site.urls),
    # POST：问答，见 qa/views.py
    path("api/ask/", AskView.as_view(), name="ask"),
    # POST：提交文档并异步计算向量，返回 202
    path("api/documents/", DocumentCreateView.as_view(), name="document-create"),
    # GET：查询单条文档的入库状态。<int:doc_id> 只匹配整数，其他路径会返回 404
    path("api/documents/<int:doc_id>/", DocumentDetailView.as_view(), name="document-detail"),
]