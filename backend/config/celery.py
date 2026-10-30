import os

from celery import Celery

# 必须在创建 Celery 实例前设置 Django 配置模块
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')

app = Celery('config')

# namespace='CELERY' 表示只读取 settings 里以 CELERY_ 开头的配置
app.config_from_object('django.conf:settings', namespace='CELERY')

# 自动发现各 app 下的 tasks.py
app.autodiscover_tasks()