from core.models import Term, Session


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