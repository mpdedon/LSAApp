# lsalms/services.py

from django.contrib.contenttypes.models import ContentType
from .models import GradedActivity, CourseGrade, CourseEnrollment
from core.models import Assignment, Assessment, Exam, AssignmentSubmission, AssessmentSubmission, ExamSubmission


def update_course_grade_for_student(course, student):
    """
    Calculates and saves the final grade for a student using a true weighted
    average based on each activity's max score and its assigned course weight.
    """
    graded_activities = GradedActivity.objects.filter(course=course)
    if not graded_activities.exists():
        # Clean up old grade if it exists
        CourseGrade.objects.filter(enrollment__student=student, enrollment__course=course).delete()
        return None

    # Prefetch activity objects and submissions efficiently
    assignment_activities = {ga.object_id: ga for ga in graded_activities if ga.content_type.model == 'assignment'}
    assessment_activities = {ga.object_id: ga for ga in graded_activities if ga.content_type.model == 'assessment'}
    exam_activities = {ga.object_id: ga for ga in graded_activities if ga.content_type.model == 'exam'}

    assignment_subs = {s.assignment_id: s.grade for s in AssignmentSubmission.objects.filter(student=student, assignment_id__in=assignment_activities.keys())}
    assessment_subs = {s.assessment_id: s.score for s in AssessmentSubmission.objects.filter(student=student, assessment_id__in=assessment_activities.keys())}
    exam_subs = {s.exam_id: s.score for s in ExamSubmission.objects.filter(student=student, exam_id__in=exam_activities.keys())}

    total_weighted_percentage_score = 0
    total_weight_of_completed_activities = 0

    # --- THE CALCULATION LOGIC ---

    def process_activities(activities, submissions):
        nonlocal total_weighted_percentage_score, total_weight_of_completed_activities
        for activity_id, activity in activities.items():
            student_score = submissions.get(activity_id)
            if student_score is not None:
                # Use the max_score cached in our GradedActivity model
                max_score = activity.max_score if activity.max_score and activity.max_score > 0 else 100
                
                # 1. Calculate the student's percentage score FOR THIS ACTIVITY
                activity_percentage = (float(student_score) / max_score) * 100
                
                # 2. Apply the course weight to that percentage score
                total_weighted_percentage_score += activity_percentage * (activity.weight / 100.0)
                
                # 3. Keep track of the total weight of activities the student has actually completed
                total_weight_of_completed_activities += activity.weight

    process_activities(assignment_activities, assignment_subs)
    process_activities(assessment_activities, assessment_subs)
    process_activities(exam_activities, exam_subs)
    
    # The final score is the sum of all weighted percentages, normalized against the
    # weight of the activities that have actually been graded.
    final_score = (total_weighted_percentage_score / total_weight_of_completed_activities) * 100 if total_weight_of_completed_activities > 0 else 0
    
    enrollment, _ = CourseEnrollment.objects.get_or_create(student=student, course=course)
    
    # Save the result to our cache model
    grade, _ = CourseGrade.objects.update_or_create(
        enrollment=enrollment,
        defaults={'final_score': round(final_score, 2)}
    )
    return grade