# lsalms/management/commands/backfill_graded_activities.py

from django.core.management.base import BaseCommand
from django.contrib.contenttypes.models import ContentType
from lsalms.models import ContentBlock, GradedActivity, Assignment, Assessment, Exam

class Command(BaseCommand):
    help = 'Scans all ContentBlocks and creates any missing GradedActivity records.'

    def handle(self, *args, **kwargs):
        self.stdout.write("Starting to backfill GradedActivity records...")
        
        created_count = 0
        
        # Find all content blocks that have a link to a graded activity
        content_blocks_with_activities = ContentBlock.objects.filter(
            linked_assignment__isnull=False
        ) | ContentBlock.objects.filter(
            linked_assessment__isnull=False
        ) | ContentBlock.objects.filter(
            linked_exam__isnull=False
        )
        
        self.stdout.write(f"Found {content_blocks_with_activities.count()} content blocks with linked activities to process.")

        for block in content_blocks_with_activities.select_related('lesson__module__course'):
            course = block.lesson.module.course
            activity = block.linked_assignment or block.linked_assessment or block.linked_exam
            
            if not activity:
                continue

            activity_type = ContentType.objects.get_for_model(activity)
            max_score_value = getattr(activity, 'total_marks', 100) # Simplified for command

            _, created = GradedActivity.objects.get_or_create(
                course=course,
                content_type=activity_type,
                object_id=activity.id,
                defaults={'max_score': max_score_value}
            )

            if created:
                created_count += 1
                self.stdout.write(f"  + Created GradedActivity for '{activity.title}' in course '{course.title}'")

        self.stdout.write(self.style.SUCCESS(f"Backfill complete. Created {created_count} new GradedActivity records."))