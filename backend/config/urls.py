from django.contrib import admin
from django.urls import path

from qa.document_views import DocumentCreateView
from qa.views import AskView

urlpatterns = [
    path("admin/", admin.site.urls),
    path("api/ask/", AskView.as_view(), name="ask"),
    path("api/documents/", DocumentCreateView.as_view(), name="document-create"),
]