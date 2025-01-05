from __future__ import absolute_import, unicode_literals

# Import Celery application
from .celery_app import app as celery_app

__all__ = ('celery_app',)
