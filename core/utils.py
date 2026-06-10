from core.models import Term, Session


def normalize_choice_answers(raw_value):
    if raw_value in (None, ''):
        return []

    if isinstance(raw_value, (list, tuple, set)):
        candidates = raw_value
    else:
        candidates = str(raw_value).split(',')

    normalized = []
    for candidate in candidates:
        value = str(candidate).strip()
        if value and value not in normalized:
            normalized.append(value)
    return normalized


def extract_submission_answer(request, question_id, question_type):
    answer_key = f'answer_{question_id}'
    if question_type == 'MCQ':
        return request.POST.getlist(answer_key)
    return request.POST.get(answer_key)


def format_answer_for_display(answer):
    if answer in (None, ''):
        return 'Not Answered'

    if isinstance(answer, (list, tuple, set)):
        values = [str(item).strip() for item in answer if str(item).strip()]
        return ', '.join(values) if values else 'Not Answered'

    return str(answer)


def question_answer_is_correct(question, submitted_answer):
    question_type = getattr(question, 'question_type', '')
    if question_type == 'ES':
        return None

    if hasattr(question, 'is_option_correct'):
        return question.is_option_correct(submitted_answer)

    correct_answer = getattr(question, 'correct_answer', None)
    if question_type == 'MCQ':
        submitted_values = {value.lower() for value in normalize_choice_answers(submitted_answer)}
        correct_values = {value.lower() for value in normalize_choice_answers(correct_answer)}
        return bool(correct_values) and submitted_values == correct_values

    return str(submitted_answer or '').strip().lower() == str(correct_answer or '').strip().lower()


def question_correct_answer_display(question):
    if hasattr(question, 'correct_answer_list'):
        answers = question.correct_answer_list()
        if answers:
            return ', '.join(answers)
    return str(getattr(question, 'correct_answer', '') or '').strip()


def build_question_result(question, submitted_answer):
    return {
        'question_text': question.question_text,
        'question_type': question.question_type,
        'student_answer_display': format_answer_for_display(submitted_answer),
        'correct_answer_display': question_correct_answer_display(question),
        'is_correct': question_answer_is_correct(question, submitted_answer),
    }


def log_activity(user, activity_type, description='', related_model='', related_id=None, request=None):
    """
    Log user activity for analytics and monitoring.
    
    Args:
        user: The user performing the activity
        activity_type: Type of activity (must match ActivityLog.ACTIVITY_TYPES)
        description: Optional description of the activity
        related_model: Optional model name the activity is related to
        related_id: Optional ID of the related object
        request: Optional Django request object to extract IP and user agent
    """
    from core.models import ActivityLog
    
    ip_address = None
    user_agent = ''
    
    if request:
        # Get client IP
        x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
        if x_forwarded_for:
            ip_address = x_forwarded_for.split(',')[0]
        else:
            ip_address = request.META.get('REMOTE_ADDR')
        
        # Get user agent
        user_agent = request.META.get('HTTP_USER_AGENT', '')
    
    ActivityLog.objects.create(
        user=user,
        activity_type=activity_type,
        description=description,
        related_model=related_model,
        related_id=related_id,
        ip_address=ip_address,
        user_agent=user_agent
    )


def get_current_term():
    """Gets the currently active term, or the latest term if none are active."""
    current = Term.objects.filter(is_active=True).first()
    if not current:
        current = Term.objects.order_by('-session__name', '-order').first()
    return current
    

def get_next_term(current_term):
    """Gets the next term in sequence, handling session boundaries."""
    if not current_term:
        return None

    next_term = Term.objects.filter(
        session=current_term.session,
        order__gt=current_term.order
    ).order_by('order').first()

    if next_term:
        return next_term
    else:
        next_session = Session.objects.filter(
            name__gt=current_term.session.name
        ).order_by('name').first() 

        if next_session:
            return Term.objects.filter(session=next_session).order_by('order').first()

    return None 