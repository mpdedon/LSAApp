from django.core.management.base import BaseCommand
from core.models import EmailCampaign
from core.tasks import send_email_task

class Command(BaseCommand):
    help = "Send bulk emails"

    def handle(self, *args, **kwargs):
        campaigns = EmailCampaign.objects.filter(sent_at__isnull=True)
        for campaign in campaigns:
            for recipient in campaign.recipients.all():
                send_email_task.delay(
                    subject=campaign.title,
                    to_email=recipient.email,
                    template='emails/bulk_email.html',
                    context={'campaign': campaign}
                )
            campaign.sent_at = now()
            campaign.save()
        self.stdout.write(self.style.SUCCESS("Bulk emails sent successfully."))
