# 启动 Django 时加载 Celery，确保 @shared_task 装饰器绑定到这个 app
from .celery import app as celery_app

__all__ = ('celery_app',)