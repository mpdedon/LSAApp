# lsaapp_core/templatetags/message_filters.py

from django import template

register = template.Library()

# ... (your other existing filters if any) ...

@register.filter(name='get_item')
def get_item(dictionary, key):
    """
    Allows accessing a dictionary item with a variable key in templates.
    This robust version handles potential key type mismatches (e.g., int vs. str).
    """
    # Ensure we're actually working with a dictionary
    if not isinstance(dictionary, dict):
        return None
    
    # Try the key as its original type first
    if key in dictionary:
        return dictionary.get(key)
    
    # If that fails, try converting the key to a string
    if str(key) in dictionary:
        return dictionary.get(str(key))
    
    # If that also fails, try converting the key to an integer (less common but safe)
    try:
        if int(key) in dictionary:
            return dictionary.get(int(key))
    except (ValueError, TypeError):
        pass # Ignore errors if the key can't be converted to an int

    # If all lookups fail, return None
    return None