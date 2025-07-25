"""
WSGI config for lsaapp project.

It exposes the WSGI callable as a module-level variable named ``application``.

For more information on this file, see
https://docs.djangoproject.com/en/4.2/howto/deployment/wsgi/
"""

import os

from django.core.wsgi import get_wsgi_application
from whitenoise import WhiteNoise

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'lsaapp.settings')

application = get_wsgi_application()

application = WhiteNoise(application, root=os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'staticfiles'))
application.add_files(os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'media'), prefix='/media/')