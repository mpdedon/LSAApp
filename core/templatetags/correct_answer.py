from django import template

register = template.Library()

@register.filter
def is_correct_for_question(option_text, question):
    if hasattr(question, 'is_option_correct'):
        return question.is_option_correct(option_text)
    return False