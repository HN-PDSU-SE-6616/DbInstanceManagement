import os

from celery import Celery
from django.conf import settings

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "dbinstancemanagement.settings")

app = Celery("dbinstancemanagement")
app.config_from_object("django.conf:settings", namespace="CELERY")
app.conf.timezone = settings.TIME_ZONE
app.autodiscover_tasks()
