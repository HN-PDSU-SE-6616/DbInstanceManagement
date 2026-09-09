"""Celery 应用入口"""
import os

from celery import Celery
from django.conf import settings

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "dbinstancemanagement.settings")

# 实例化 Celery 应用
app = Celery("dbinstancemanagement")
app.config_from_object("django.conf:settings", namespace="CELERY")
app.conf.timezone = settings.TIME_ZONE

# 注册 @shared_task 任务。
app.autodiscover_tasks()
