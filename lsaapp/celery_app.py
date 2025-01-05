from __future__ import absolute_import, unicode_literals
import os
from celery import Celery

# Set default Django settings module for 'celery'
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'lsaapp.settings')

app = Celery('lsaapp')

# Load custom configuration from Django settings
app.config_from_object('django.conf:settings', namespace='CELERY')

# Autodiscover tasks in installed apps
app.autodiscover_tasks()


@app.task(bind=True)
def debug_task(self):
    print(f'Request: {self.request!r}')
