from django.contrib.admin.models import LogEntry

def get_recent_actions_ut(request, limit=10):
    """
    Fetch recent admin actions (CRUD operations) performed in the admin panel.
    """
    recent_actions = LogEntry.objects.select_related('content_type', 'user').order_by('-action_time')[:limit]
    return recent_actions
