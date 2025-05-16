from core.models import Term, Session


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