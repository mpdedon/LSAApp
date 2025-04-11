from django import template
from urllib.parse import urlencode

register = template.Library()

@register.filter(name='exclude_query_params_starting_with')
def exclude_query_params_starting_with(query_dict, prefix):
    """
    Takes a QueryDict and a prefix string.
    Returns a URL-encoded string of query parameters
    excluding those whose keys start with the given prefix.
    """
    if not hasattr(query_dict, 'items'):
        return '' # Handle cases where input is not a QueryDict

    params_to_keep = {}
    for key, value_list in query_dict.lists(): # Use .lists() to handle multiple values for same key
        if not key.startswith(prefix):
            # urlencode expects list of values, not QueryDict value list directly sometimes
            params_to_keep[key] = value_list

    if not params_to_keep:
        return ''

    # urlencode handles list of values correctly
    return urlencode(params_to_keep, doseq=True)

# Optional: A tag to build the full query string including the new page param
@register.simple_tag(takes_context=True)
def build_paginated_query_string(context, page_param_key, page_num):
    """
    Builds the full query string for pagination links, preserving other parameters.
    Example usage: {% build_paginated_query_string page_param_key page_num %}
    where page_param_key is like 'page_classname'
    """
    request = context.get('request')
    if not request:
        return ''

    query_params = request.GET.copy() # Make a mutable copy

    # Remove any existing page parameters
    keys_to_remove = [key for key in query_params if key.startswith('page_')]
    for key in keys_to_remove:
        del query_params[key]

    # Add the new page parameter
    query_params[page_param_key] = page_num

    # Encode the parameters
    return query_params.urlencode()