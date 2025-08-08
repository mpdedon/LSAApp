# In your new empty migration file (e.g., core/migrations/0019_auto_....py)

from django.db import migrations, models
from django.db.models import F, Sum, Avg, Q
from django.db.models.functions import Coalesce
from decimal import Decimal

def calculate_and_migrate_results_data(apps, schema_editor):
    """
    One-time migration to populate summary fields and models from existing data.
    """
    # We must use apps.get_model to get the historical version of the models for the migration
    Result = apps.get_model('core', 'Result')
    SessionalResult = apps.get_model('core', 'SessionalResult')
    CumulativeRecord = apps.get_model('core', 'CumulativeRecord')
    Student = apps.get_model('core', 'Student')
    Session = apps.get_model('core', 'Session')
    Term = apps.get_model('core', 'Term')
    SubjectResult = apps.get_model('core', 'SubjectResult')
    Subject = apps.get_model('core', 'Subject') # Needed for subject_weight

    print("\nStarting results data migration...")

    # 1. Calculate and populate term summaries for all existing Result objects
    print("  - Calculating term summaries (including performance change)...")
    
    all_results_to_process = Result.objects.order_by('student_id', 'term__start_date')
    
    for result in all_results_to_process:
        subject_results = SubjectResult.objects.filter(result=result)
        
        # Use annotate and aggregate for efficiency where possible
        scored_subjects_qs = subject_results.annotate(
            total= (
                Coalesce(F('continuous_assessment_1'), Decimal(0)) +
                Coalesce(F('continuous_assessment_2'), Decimal(0)) +
                Coalesce(F('continuous_assessment_3'), Decimal(0)) +
                Coalesce(F('assignment'), Decimal(0)) +
                Coalesce(F('oral_test'), Decimal(0)) +
                Coalesce(F('exam_score'), Decimal(0))
            )
        ).filter(total__gt=0)
        
        if not scored_subjects_qs.exists():
            result.total_score, result.average_score, result.term_gpa = Decimal('0.00'), Decimal('0.00'), Decimal('0.00')
        else:
            summary = scored_subjects_qs.aggregate(
                total_score_sum=Sum('total'),
                average_score_val=Avg('total')
            )
            result.total_score = summary['total_score_sum']
            result.average_score = summary['average_score_val']
            
            total_weighted_grade_points, total_weights = Decimal('0.0'), Decimal('0.0')
            for sr in scored_subjects_qs:
                # We can't call model methods like calculate_grade_point() in a migration. Re-implement logic.
                score = sr.total
                grade_point = 0.0
                if score >= 80: grade_point = 5.0
                elif score >= 65: grade_point = 4.0
                elif score >= 55: grade_point = 3.0
                elif score >= 45: grade_point = 2.0
                elif score >= 40: grade_point = 1.0

                weight = Decimal(getattr(sr.subject, 'subject_weight', 1))
                total_weighted_grade_points += Decimal(grade_point) * weight
                total_weights += weight
            result.term_gpa = (total_weighted_grade_points / total_weights) if total_weights > 0 else Decimal('0.00')

        # Calculate performance change
        previous_terms_qs = Term.objects.filter(start_date__lt=result.term.start_date).order_by('-start_date')
        previous_result = None
        for prev_term in previous_terms_qs:
            prev_res_candidate = Result.objects.filter(student_id=result.student_id, term=prev_term).first()
            if prev_res_candidate:
                previous_result = prev_res_candidate
                break

        if previous_result and previous_result.average_score is not None and result.average_score is not None:
            if previous_result.average_score > 0:
                change = ((result.average_score - previous_result.average_score) / previous_result.average_score) * 100
                result.performance_change = change
            else:
                result.performance_change = Decimal('100.00') if result.average_score > 0 else Decimal('0.00')
        else:
            result.performance_change = None

        result.save(update_fields=['total_score', 'average_score', 'term_gpa', 'performance_change'])

    print(f"    ... Done calculating for {all_results_to_process.count()} term results.")

    # 2. Create/populate SessionalResult and CumulativeRecord for each student
    all_students = Student.objects.all()
    print(f"  - Creating/updating sessional and cumulative records for {all_students.count()} students...")
    for student in all_students:
        student_sessions = Session.objects.filter(terms__result__student=student).distinct()        
        
        for session in student_sessions:
            sessional_result, _ = SessionalResult.objects.get_or_create(student=student, session=session)
            term_results = Result.objects.filter(student=student, term__session=session, term_gpa__isnull=False)
            term_gpas = [res.term_gpa for res in term_results if res.term_gpa is not None]
            sessional_result.sessional_gpa = sum(term_gpas) / len(term_gpas) if term_gpas else Decimal('0.00')
            sessional_result.save()

        cumulative_record, _ = CumulativeRecord.objects.get_or_create(student=student)
        all_sessional_results = SessionalResult.objects.filter(student=student, is_approved=True, sessional_gpa__isnull=False)
        all_sessional_gpas = [res.sessional_gpa for res in all_sessional_results]
        cumulative_record.cumulative_gpa = sum(all_sessional_gpas) / len(all_sessional_gpas) if all_sessional_gpas else Decimal('0.00')
        cumulative_record.save()
        
    print("Data migration complete.")

class Migration(migrations.Migration):

    dependencies = [
        ('core', '0018_cumulativerecord_alter_result_options_and_more'), # IMPORTANT: Use the filename from Step 1
    ]

    operations = [
        # This runs our function. RunPython.noop means it does nothing on reverse migration.
        migrations.RunPython(calculate_and_migrate_results_data, migrations.RunPython.noop),
    ]