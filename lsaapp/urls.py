"""
URL configuration for lsaapp project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/4.2/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""
from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static

from core.views import home
from core.auth.views import register
from core.auth.views import CustomLoginView, CustomLogoutView
from core.auth.views import PasswordResetView, PasswordResetDoneView, PasswordResetConfirmView, PasswordResetCompleteView
from core.auth.views import teacher_dashboard, student_dashboard, guardian_dashboard
from core.views import AdminDashboardView, PromoteStudentView
from core.views import CreateNotificationView, NotificationListView
from core.views import SessionListView, SessionDetailView, SessionCreateView, SessionUpdateView, SessionDeleteView
from core.views import TermListView, TermDetailView, TermCreateView, TermUpdateView, TermDeleteView
from core.views import promote_student, repeat_student, demote_student, mark_dormant_student, mark_left_student, mark_active
from core.student.views import StudentListView, StudentCreateView, StudentUpdateView, StudentDetailView, StudentDeleteView, BulkUpdateStudentsView, export_students, student_reports
from core.student.views import submit_assignment
from core.teacher.views import TeacherListView, TeacherCreateView, TeacherUpdateView, TeacherDetailView, TeacherDeleteView, TeacherBulkActionView, export_teachers, teacher_reports
from core.teacher.views import input_scores, broadsheet, mark_attendance, attendance_log, message_guardian, update_result, view_na_result, grade_essay_questions
from core.teacher.views import create_assignment, add_question, grade_assignment, view_submitted_assignments, update_assignment, delete_assignment, assignment_detail, assignment_list
from core.guardian.views import GuardianListView, GuardianCreateView, GuardianUpdateView, GuardianDetailView, GuardianDeleteView, GuardianBulkActionView
from core.guardian.views import financial_record_detail, view_student_result, export_guardians, guardian_reports
from core.classes.views import ClassListView, ClassCreateView, ClassUpdateView, ClassDetailView, ClassDeleteView, EnrollStudentView
from core.views import SubjectCreateView, SubjectListView, SubjectUpdateView, SubjectDetailView, SubjectDeleteView
from core.results.views import ResultCreateView, ResultListView, ResultUpdateView, ResultDetailView, ResultDeleteView
from core.views import FeeAssignmentCreateView, FeeAssignmentListView, FeeAssignmentUpdateView, FeeAssignmentDetailView, FeeAssignmentDeleteView, StudentFeeRecordListView
from core.views import PaymentCreateView, PaymentListView, PaymentUpdateView, PaymentDetailView, PaymentDeleteView, FinancialRecordListView
from core.views import StudentClassEnrollmentView, StudentEnrollmentsView
from core.views import AssignSubjectView, AssignTeacherView, AssignClassSubjectView, DeleteClassSubjectAssignmentView
from core.views import TeacherAssignmentListView, TeacherAssignmentUpdateView, TeacherAssignmentDetailView, TeacherAssignmentDeleteView
from core.subject_assignment.views import SubjectAssignmentListView, SubjectAssignmentCreateView, SubjectAssignmentUpdateView, SubjectAssignmentDetailView, SubjectAssignmentDeleteView

urlpatterns = [

    # Admin URL 
    path('admin/', admin.site.urls),
   
    # Home and Auth URLs
    path('', home, name='home'),
    path('register/', register, name='register'),
    path('login/', CustomLoginView.as_view(template_name='auth/login.html'), name='login'),
    path('logout/', CustomLogoutView.as_view(template_name='auth/logout.html', next_page='home'), name='logout'),
    path('password_reset/', PasswordResetView.as_view(), name='password_reset'),
    path('password_reset/done/', PasswordResetDoneView.as_view(), name='password_reset_done'),
    path('reset/<uidb64>/<token>/', PasswordResetConfirmView.as_view(), name='password_reset_confirm'),
    path('reset/done/', PasswordResetCompleteView.as_view(), name='password_reset_complete'),
    
    # School Setup URLs
    path('setup/', AdminDashboardView.as_view(), name='school_setup'),

    path('create/', CreateNotificationView.as_view(), name='create_notification'),
    path('list/', NotificationListView.as_view(), name='notification_list'),

    path('sessions/', SessionListView.as_view(), name='session_list'),
    path('sessions/create/', SessionCreateView.as_view(), name='session_create'),
    path('sessions/update/<int:pk>/', SessionUpdateView.as_view(), name='session_update'),
    path('sessions/<int:pk>/', SessionDetailView.as_view(), name='session_detail'),
    path('sessions/<int:pk>/delete/', SessionDeleteView.as_view(), name='session_delete'),

    path('terms/', TermListView.as_view(), name='term_list'),
    path('terms/create/', TermCreateView.as_view(), name='term_create'),
    path('terms/update/<int:pk>/', TermUpdateView.as_view(), name='term_update'),
    path('terms/<int:pk>', TermDetailView.as_view(), name='term_detail'),
    path('terms/<int:pk>/delete/', TermDeleteView.as_view(), name='term_delete'),

    # Enrollment URLs
    path('setup/enrol_student/', StudentClassEnrollmentView, name='enrol_student'),
    path('student/<int:student_id>/enrollments/', StudentEnrollmentsView, name='view_enrollments'),
    path('setup/promote_students', PromoteStudentView.as_view(), name='promote_students'),

    # Subject & Teacher Assignment URLs
    path('assign_teacher/', AssignTeacherView, name='assign_teacher'),
    path('teacher_assignments/', TeacherAssignmentListView.as_view(), name='teacher_assignment_list'),
    path('teacher_assignments/update/<int:pk>', TeacherAssignmentUpdateView.as_view(), name='teacher_assignment_update'),
    path('teacher_assignments/<int:pk>/', TeacherAssignmentDetailView.as_view(), name='teacher_assignment_detail'),
    path('teacher_assignments/<int:pk>/delete/', TeacherAssignmentDeleteView.as_view(), name='teacher_assignment_delete'),
    
    path('assign_subject/', AssignSubjectView, name='assign_subject'),
    path('subject_assignments/', SubjectAssignmentListView.as_view(), name='subject_assignment_list'),
    path('subject_assignments/update/<int:pk>', SubjectAssignmentUpdateView.as_view(), name='subject_assignment_update'),
    path('subject_assignments/<int:pk>/', SubjectAssignmentDetailView.as_view(), name='subject_assignment_detail'),
    path('subject_assignments/<int:pk>/delete/', SubjectAssignmentDeleteView.as_view(), name='subject_assignment_delete'),
    
    # Student URLs
    path('students/', StudentListView.as_view(), name='student_list'),
    path('students/bulk-update/', BulkUpdateStudentsView.as_view(), name='bulk_update_students'),
    path('students/create/', StudentCreateView.as_view(), name='student_create'),
    path('students/update/<int:pk>/', StudentUpdateView.as_view(), name='student_update'),
    path('students/<int:pk>/', StudentDetailView.as_view(), name='student_detail'),
    path('students/<int:pk>/delete/', StudentDeleteView.as_view(), name='student_delete'),
    path('student/dashboard/', student_dashboard, name='student_dashboard'),
    path('students/export/', export_students, name='export_students'),
    path('students/reports/', student_reports, name='student_reports'),
    path('promote/<int:pk>/', promote_student, name='promote_student'),
    path('repeat/<int:pk>/', repeat_student, name='repeat_student'),
    path('demote/<int:pk>/', demote_student, name='demote_student'),
    path('dormant/<int:pk>/', mark_dormant_student, name='mark_dormant_student'),
    path('left/<int:pk>/', mark_left_student, name='mark_left_student'),
    path('mark_active/<int:pk>/', mark_active, name='mark_active'),

    # Teacher URLs
    path('teachers/', TeacherListView.as_view(), name='teacher_list'),
    path('teachers/bulk-update/', TeacherBulkActionView.as_view(), name='bulk_update_teachers'),
    path('teachers/create/', TeacherCreateView.as_view(), name='teacher_create'),
    path('teachers/<int:pk>/update/', TeacherUpdateView.as_view(), name='teacher_update'),
    path('teachers/<int:pk>/', TeacherDetailView.as_view(), name='teacher_detail'),
    path('teachers/<int:pk>/delete/', TeacherDeleteView.as_view(), name='teacher_delete'),
    path('teacher/dashboard/', teacher_dashboard, name='teacher_dashboard'),
    path('mark_attendance/<int:class_id>/', mark_attendance, name='mark_attendance'),
    path('attendance_log/<int:class_id>', attendance_log, name='attendance_log'),
    path('input_scores/<int:class_id>/<int:subject_id>/<int:term_id>/', input_scores, name='input_scores'),
    path('update_result/student/<int:student_id>/result/<int:term_id>/update/', update_result, name='update_result'),
    path('view_na_result/<int:student_id>/<int:term_id>/', view_na_result, name='view_na_result'),
    path('broadsheet/<int:class_id>/<int:term_id>/', broadsheet, name='broadsheet'),
    path('message_guardian/<int:guardian_id>/', message_guardian, name='message_guardian'),
    path('teachers/export/', export_teachers, name='export_teachers'),
    path('teachers/reports/', teacher_reports, name='teacher_reports'),
    path('assignments/create/', create_assignment, name='create_assignment'),
    path('assignments/<int:assignment_id>/questions/add/', add_question, name='add_question'),
    path('assignments/<int:assignment_id>/submit/', submit_assignment, name='submit_assignment'),
    path('assignments/', assignment_list, name='assignment_list'),
    path('assignments/<int:assignment_id>/', assignment_detail, name='assignment_detail'),
    path('assignments/<int:assignment_id>/delete/', delete_assignment, name='delete_assignment'),
    path('submissions/<int:submission_id>/grade/', grade_assignment, name='grade_assignment'),
    path('submissions/<int:submission_id>/grade/', grade_essay_questions, name='grade_essay_questions'),
    path('assignments/submitted/', view_submitted_assignments, name='view_submitted_assignments'),
    path('assignments/<int:assignment_id>/edit/', update_assignment, name='update_assignment'),
    path('assignments/<int:assignment_id>/delete/', delete_assignment, name='delete_assignment'),

    # Guardian URLs
    path('guardians/', GuardianListView.as_view(), name='guardian_list'),
    path('guardians/bulk-update/', GuardianBulkActionView.as_view(), name='bulk_update_guardians'),
    path('guardians/create/', GuardianCreateView.as_view(), name='guardian_create'),
    path('guardians/<int:pk>/update/', GuardianUpdateView.as_view(), name='guardian_update'),
    path('guardians/<int:pk>/', GuardianDetailView.as_view(), name='guardian_detail'),
    path('guardians/<int:pk>/delete/', GuardianDeleteView.as_view(), name='guardian_delete'),
    path('guardian/dashboard/', guardian_dashboard, name='guardian_dashboard'),
    path('guardians/export/', export_guardians, name='export_guardians'),
    path('guardians/reports/', guardian_reports, name='guardian_reports'),
    path('guardian/financial_record/<int:student_id>/', financial_record_detail, name='financial_record_detail'),
    path('guardian/student/<int:student_id>/result/<int:term_id>/', view_student_result, name='view_student_result'), 
    
    # Class URLs
    path('classes/', ClassListView.as_view(), name='class_list'),
    path('classes/create/', ClassCreateView.as_view(), name='class_create'),
    path('classes/<int:pk>/update/', ClassUpdateView.as_view(), name='class_update'),
    path('classes/<int:pk>/', ClassDetailView.as_view(), name='class_detail'),
    path('classes/<int:pk>/delete/', ClassDeleteView.as_view(), name='class_delete'),
    path('classes/<int:pk>/enrol/', EnrollStudentView.as_view(), name='enrol_student'),
    path('assign_class_subjects/<int:pk>/', AssignClassSubjectView.as_view(), name='assign_class_subject'),
    path('class/subject-assignment/<int:pk>/delete/', DeleteClassSubjectAssignmentView.as_view(), name='delete_class_subject_assignment'),


    # Subject URLs
    path('subjects/', SubjectListView.as_view(), name='subject_list'),
    path('subjects/create/', SubjectCreateView.as_view(), name='subject_create'),
    path('subjects/<int:pk>/update/', SubjectUpdateView.as_view(), name='subject_update'),
    path('subjects/<int:pk>/', SubjectDetailView.as_view(), name='subject_detail'),
    path('subjects/<int:pk>/delete/', SubjectDeleteView.as_view(), name='subject_delete'),

    # FeeAssignment URLs
    path('fee_assignments/', FeeAssignmentListView.as_view(), name='fee_assignment_list'),
    path('fee_assignments/create/', FeeAssignmentCreateView.as_view(), name='create_fee_assignment'),
    path('fee_assignments/<int:pk>/update/', FeeAssignmentUpdateView.as_view(), name='update_fee_assignment'),
    path('fee_assignments/<int:pk>/', FeeAssignmentDetailView.as_view(), name='fee_assignment_detail'),
    path('fee_assignments/<int:pk>/delete/', FeeAssignmentDeleteView.as_view(), name='delete_fee_assignment'),
    path('student_fee_records/', StudentFeeRecordListView.as_view(), name='student_fee_record_list'),

    # Result URLs
    path('results/', ResultListView.as_view(), name='result_list'),
    path('results/create/', ResultCreateView.as_view(), name='result_create'),
    path('results/<int:pk>/update/', ResultUpdateView.as_view(), name='result_update'),
    path('results/<int:pk>/', ResultDetailView.as_view(), name='result_detail'),
    path('results/<int:pk>/delete/', ResultDeleteView.as_view(), name='result_delete'),

    # Payment URLs
    path('payments/', PaymentListView.as_view(), name='payment_list'),
    path('payments/create/', PaymentCreateView.as_view(), name='create_payment'),
    path('payments/update/<int:pk>/', PaymentUpdateView.as_view(), name='update_payment'),
    path('payments/<int:pk>/', PaymentDetailView.as_view(), name='payment_detail'),
    path('payments/delete/<int:pk>/', PaymentDeleteView.as_view(), name='delete_payment'),
    path('financial-records/', FinancialRecordListView.as_view(), name='financial_record_list'),

]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)