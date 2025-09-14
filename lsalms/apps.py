from django.apps import AppConfig


class LsalmsConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'lsalms'

    def ready(self):
        import lsalms.signals
