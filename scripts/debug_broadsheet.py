import os
import django
import sys
from decimal import Decimal
BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)
# Ensure any DATABASE_URL from .env or environment doesn't force SSL production config
# Set to empty so load_dotenv won't override it (load_dotenv doesn't overwrite existing env vars)
os.environ['DATABASE_URL'] = ''
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'lsaapp.settings')
django.setup()
from core.models import Class, Term, Subject, Student, Result, ClassSubjectAssignment

print('--- TERMS (id,name,is_active,start,end) ---')
for t in Term.objects.all().order_by('-start_date')[:10]:
    print(t.id, t.name, getattr(t, 'is_active', None), t.start_date, t.end_date)

classes = Class.objects.all()[:20]
print('\n--- CLASSES (id,name,count students) ---')
for c in classes:
    print(c.id, getattr(c, 'name', None), Student.objects.filter(current_class=c, status='active').count())

# choose class as first with students
class_obj = None
for c in classes:
    if Student.objects.filter(current_class=c, status='active').exists():
        class_obj = c
        break
if not class_obj:
    print('\nNo classes with active students found, aborting.')
    sys.exit(0)

# pick active term or most recent
term = Term.objects.filter(is_active=True).first() or Term.objects.order_by('-start_date').first()
print('\nSelected class:', class_obj.id, getattr(class_obj, 'name', None))
print('Selected term:', term.id, term.name)

print('\nClass.subjects (many-to-many):', class_obj.subjects.count())
for sub in class_obj.subjects.all():
    print('  M2M subject:', sub.id, sub.name)

subjects = Subject.objects.filter(class_assignments__class_assigned=class_obj, class_assignments__term=term).distinct().order_by('name')
print('\nSubjects for class/term:', subjects.count())
for s in subjects:
    print(' -', s.id, s.name)

csas = ClassSubjectAssignment.objects.filter(class_assigned=class_obj, term=term)
print('\nClassSubjectAssignment rows for class/term:', csas.count())
for csa in csas:
    print('  CSA:', csa.id, csa.subject_id, csa.subject.name, csa.session.name, csa.term.name)

students = Student.objects.filter(current_class=class_obj, status='active').select_related('user')[:20]
print('\nSample students count:', students.count())

for student in students:
    print('\nStudent:', student.user.get_full_name(), 'id', student.user.id)
    result = Result.objects.filter(student=student, term=term).first()
    print(' Result exists?', bool(result))
    if not result:
        continue
    srs = result.subject_results.filter(subject__in=subjects).select_related('subject')
    print(' Total subject_results for relevant subjects:', srs.count())
    print(' All subject_results:')
    for sr in srs:
        vals = {
            'subject_id': sr.subject.id,
            'subject_name': sr.subject.name,
            'ca1': sr.continuous_assessment_1,
            'ca2': sr.continuous_assessment_2,
            'ca3': sr.continuous_assessment_3,
            'assignment': sr.assignment,
            'oral_test': sr.oral_test,
            'exam_score': sr.exam_score,
            'total_score_method': float(sr.total_score()),
        }
        print('  ', vals)
    # replicate graded_subject_results filter from view
    graded = srs.exclude(
        continuous_assessment_1__isnull=True,
        continuous_assessment_2__isnull=True,
        continuous_assessment_3__isnull=True,
        assignment__isnull=True,
        oral_test__isnull=True,
        exam_score__isnull=True,
    )
    print(' Graded after exclude (should remove rows where ALL fields above are NULL):', graded.count())
    for sr in graded:
        print('   GR:', sr.subject.name, float(sr.total_score()))
    # dictionary built in view
    student_subject_results = {}
    total_score_sum = Decimal('0.0')
    graded_subject_count = 0
    total_weighted_points = Decimal('0.0')
    total_weights = Decimal('0.0')
    for sr in graded:
        student_subject_results[sr.subject.id] = sr
        total_score_sum += sr.total_score()
        try:
            weight = Decimal(getattr(sr.subject, 'subject_weight', 1))
        except Exception:
            weight = Decimal('1')
        total_weighted_points += sr.calculate_grade_point() * weight
        total_weights += weight
        graded_subject_count += 1
    print(' student_subject_results keys:', list(student_subject_results.keys()))
    print(' total_score_sum:', total_score_sum, 'avg:', (total_score_sum/graded_subject_count) if graded_subject_count else None)

print('\nDone checks')
