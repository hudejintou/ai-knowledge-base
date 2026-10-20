from django.contrib import admin
from django.urls import path

from qa.views import AskView

urlpatterns = [
    path("admin/", admin.site.urls),
    # 完整路径为 /api/ask/，请求方法为 POST
    path("api/ask/", AskView.as_view(), name="ask"),
]